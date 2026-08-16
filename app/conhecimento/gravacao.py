"""A sessão de gravação — o que o botão do painel liga e desliga.

`scripts/transcrever.py` faz isto pelo terminal. Este módulo faz o mesmo pela
tela, e a diferença não é enfeite: **eu ligo a gravação quando o vídeo começa**,
e nesse momento eu estou no navegador, não num terminal. Um passo a mais entre
"vou assistir" e "estou gravando" é o passo que faz não gravar.

## A máquina de estados

    ocioso ──iniciar──► gravando ──parar──► processando ──► revisar ──salvar──► ocioso
                            │                                   │
                            └──────────── descartar ────────────┘

`processando` existe separado porque é onde o LLM reescreve e ficha a
transcrição — 30 s para um trecho curto, minutos para uma aula inteira. Se isso
acontecesse dentro do `parar`, a requisição estouraria o timeout e eu perderia a
gravação por causa da etapa cosmética.

## Uma sessão por vez

É deliberado. A GPU é uma só, o Whisper come CPU, e não existe caso real de
gravar duas reuniões ao mesmo tempo. Estado em memória de processo, sem tabela:
uma gravação não sobrevive a um restart do servidor de propósito — o áudio já
teria sido perdido junto.

**O bruto vai para o disco assim que a captura termina**, antes de qualquer
LLM. Se o Ollama estiver fora ou eu fechar a aba, a transcrição não se perde.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.config import DATA_DIR, settings
from app.conhecimento import transcricao as tr
from app.utils.logger import get_logger

logger = get_logger()

# Pedaço de 20 s: menos que isso e o Whisper perde contexto e erra mais no fim
# de cada trecho; mais que isso e o texto na tela atrasa a ponto de eu não
# conseguir acompanhar o que está sendo dito.
SEGUNDOS_POR_PEDACO = 20

PASTA_BRUTOS = DATA_DIR / "transcricoes"


class GravacaoErro(Exception):
    pass


@dataclass(slots=True)
class Trecho:
    """Um pedaço de 20 s transcrito, com o instante em que ele começou.

    O instante é o que permite duas coisas que só existem porque a captura é
    em pedaços: **cortar o anúncio** (basta descartar os trechos dele) e
    **carimbar a nota** com "esta parte veio dos 08:20 do vídeo", que é o que
    faz eu conseguir voltar na fonte depois.
    """

    indice: int
    segundo: int
    texto: str

    @property
    def relogio(self) -> str:
        return f"{self.segundo // 60:02d}:{self.segundo % 60:02d}"


@dataclass
class Sessao:
    estado: str = "ocioso"          # ocioso | gravando | processando | revisar
    fonte: str = "sistema"
    trechos: list[Trecho] = field(default_factory=list)
    comecou_em: float | None = None
    # Congelado quando a captura para. Sem isto o cronômetro continuava correndo
    # durante o `processando`, e uma aula de 26 min virava `duracao_min: 30` —
    # o tempo do LLM entrando na duração do vídeo.
    parou_em: float | None = None
    erro: str | None = None

    # Preenchidos na etapa `processando`.
    nota: tr.Nota | None = None
    bruto_em: Path | None = None

    ffmpeg: subprocess.Popen | None = None
    pasta_audio: Path | None = None
    tarefa: asyncio.Task | None = None

    @property
    def segundos(self) -> int:
        if not self.comecou_em:
            return 0
        return int((self.parou_em or time.monotonic()) - self.comecou_em)

    @property
    def texto(self) -> str:
        return " ".join(t.texto for t in self.trechos).strip()


_sessao = Sessao()
_modelo = None
_lock = asyncio.Lock()


# ── dispositivos de áudio ─────────────────────────────────────────


def dispositivo(fonte: str) -> str:
    """`sistema` = o monitor da saída (o que eu estou ouvindo). `mic` = a entrada."""
    try:
        if fonte == "sistema":
            sink = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
            return f"{sink}.monitor"
        return subprocess.check_output(["pactl", "get-default-source"], text=True).strip()
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise GravacaoErro(f"Não achei o dispositivo de áudio: {e}") from e


def _exige(programa: str) -> None:
    if not shutil.which(programa):
        raise GravacaoErro(f"'{programa}' não está instalado (sudo apt install {programa}).")


def _carregar_whisper():
    """Carrega o Whisper uma vez. Import tardio: `faster_whisper` custa ~3 s."""
    global _modelo
    if _modelo is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise GravacaoErro(
                "faster-whisper não instalado. Rode: pip install -e '.[transcricao]'"
            ) from e
        logger.info(f"Carregando Whisper '{settings.whisper_modelo}' (cpu/int8)...")
        # CPU de propósito: a GPU fica livre para o Ollama, que é quem reescreve
        # depois. Num Ryzen 5600 o `small` roda a ~6,6× tempo real — folga de
        # sobra para acompanhar ao vivo.
        _modelo = WhisperModel(
            settings.whisper_modelo, device="cpu", compute_type="int8", cpu_threads=0
        )
    return _modelo


def _transcrever(caminho: Path) -> str:
    modelo = _carregar_whisper()
    idioma = None if settings.whisper_idioma == "auto" else settings.whisper_idioma
    segmentos, _ = modelo.transcribe(
        str(caminho),
        language=idioma,
        vad_filter=True,      # corta silêncio: menos alucinação em pausa longa
        beam_size=5,
    )
    return " ".join(s.text.strip() for s in segmentos).strip()


# ── o laço que consome os pedaços ─────────────────────────────────


async def _consumir(sessao: Sessao) -> None:
    """Transcreve cada pedaço assim que o `ffmpeg` fecha o arquivo.

    Um pedaço só está fechado quando o seguinte começou a ser escrito — é o
    jeito de saber isso sem falar com o `ffmpeg`.
    """
    i = 0
    while True:
        atual = sessao.pasta_audio / f"p{i:05d}.wav"
        proximo = sessao.pasta_audio / f"p{i + 1:05d}.wav"
        parando = sessao.estado != "gravando"

        if atual.exists() and (proximo.exists() or parando):
            try:
                # `to_thread` porque o Whisper é C++ com GIL solto: sem isto, o
                # painel inteiro congela por 3 s a cada pedaço transcrito.
                texto = await asyncio.to_thread(_transcrever, atual)
                if texto:
                    sessao.trechos.append(
                        Trecho(indice=i, segundo=i * SEGUNDOS_POR_PEDACO, texto=texto)
                    )
            except Exception as e:  # noqa: BLE001 — um pedaço ruim não perde a sessão
                logger.warning(f"Pedaço {i} falhou: {type(e).__name__}: {e}")
            atual.unlink(missing_ok=True)
            i += 1
        elif parando and not atual.exists():
            return
        else:
            await asyncio.sleep(0.4)


# ── comandos ──────────────────────────────────────────────────────


async def iniciar(fonte: str = "sistema") -> Sessao:
    async with _lock:
        if _sessao.estado != "ocioso":
            raise GravacaoErro(f"Já existe uma sessão em '{_sessao.estado}'.")

        _exige("ffmpeg")
        _exige("pactl")
        device = dispositivo(fonte)

        pasta = Path("/tmp") / f"copiloto-gravacao-{datetime.now(UTC):%H%M%S}"
        pasta.mkdir(parents=True, exist_ok=True)

        # 16 kHz mono é exatamente o que o Whisper consome; converter aqui evita
        # que ele reamostre cada pedaço depois.
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-f", "pulse", "-i", device,
             "-ac", "1", "-ar", "16000",
             "-f", "segment", "-segment_time", str(SEGUNDOS_POR_PEDACO),
             "-reset_timestamps", "1", str(pasta / "p%05d.wav")],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        _sessao.__init__()  # zera tudo que sobrou da sessão anterior
        _sessao.estado = "gravando"
        _sessao.fonte = fonte
        _sessao.comecou_em = time.monotonic()
        _sessao.ffmpeg = ffmpeg
        _sessao.pasta_audio = pasta
        _sessao.tarefa = asyncio.create_task(_consumir(_sessao))

        logger.info(f"Gravando de {fonte} ({device})")
        return _sessao


async def parar() -> Sessao:
    """Encerra a captura e devolve o texto bruto. **Não chama o LLM.**"""
    if _sessao.estado != "gravando":
        raise GravacaoErro("Não há gravação em andamento.")

    _sessao.estado = "processando"
    _sessao.parou_em = time.monotonic()
    if _sessao.ffmpeg:
        _sessao.ffmpeg.send_signal(signal.SIGINT)
        try:
            _sessao.ffmpeg.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _sessao.ffmpeg.kill()
    await asyncio.sleep(1.0)      # o último segmento ainda está fechando

    if _sessao.tarefa:
        try:
            await asyncio.wait_for(_sessao.tarefa, timeout=300)
        except (TimeoutError, asyncio.CancelledError):
            logger.warning("Sobrou pedaço de áudio sem transcrever.")

    shutil.rmtree(_sessao.pasta_audio, ignore_errors=True)

    if not _sessao.texto:
        _sessao.estado = "ocioso"
        raise GravacaoErro("Nada foi transcrito — confira a fonte de áudio.")

    # Rede de segurança: o bruto no disco antes de qualquer LLM. Se o Ollama
    # estiver fora ou eu fechar a aba, a gravação não se perde.
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    _sessao.bruto_em = PASTA_BRUTOS / f"bruto-{datetime.now(UTC):%Y-%m-%d-%H%M}.txt"
    _sessao.bruto_em.write_text(_sessao.texto, encoding="utf-8")
    logger.info(f"Bruto salvo: {_sessao.bruto_em} ({len(_sessao.texto.split())} palavras)")

    _sessao.tarefa = asyncio.create_task(_organizar(_sessao))
    return _sessao


async def _organizar(sessao: Sessao) -> None:
    """Glossário + reescrita + fichamento. Roda em segundo plano."""
    try:
        sessao.nota = await tr.processar(
            sessao.texto,
            tema="transcrição",
            raiz_vault=vault(),
            # Os instantes de cada pedaço: é o que vira `⏱ 08:20` na nota.
            marcas=[(t.segundo, t.texto) for t in sessao.trechos],
        )
        sessao.estado = "revisar"
        logger.info(f"Transcrição organizada: {sessao.nota.fichamento.titulo!r}")
    except Exception as e:  # noqa: BLE001 — a nota crua ainda vale
        logger.warning(f"Falhou ao organizar ({type(e).__name__}: {e}); vai o texto limpo.")
        sessao.erro = f"{type(e).__name__}: {e}"
        texto, corrigidos = tr.aplicar_glossario(sessao.texto, tr.carregar_glossario())
        sessao.nota = tr.Nota(
            fichamento=tr.Fichamento(titulo="Transcrição sem título"),
            corpo=tr.limpar_fala(texto),
            corrigidos=corrigidos,
        )
        sessao.estado = "revisar"


def vault() -> Path:
    """A primeira pasta `nota:` do .env — o vault que o Copiloto já indexa."""
    for tipo, caminho in settings.conhecimento_fontes_list:
        if tipo == "nota":
            return Path(caminho).expanduser()
    return Path.home() / "Documentos" / "Notas"


async def salvar(*, titulo: str, pasta: str, tags: list[str], nome: str | None = None) -> Path:
    """Escreve a nota no vault com o que eu confirmei na tela."""
    if _sessao.estado != "revisar" or _sessao.nota is None:
        raise GravacaoErro("Não há transcrição esperando revisão.")

    ficha = _sessao.nota.fichamento
    ficha.titulo = titulo.strip()[:120] or ficha.titulo
    ficha.pasta = pasta.strip("/ ")
    if tags:
        ficha.tags = tr._tags_limpas(tags, ficha.titulo)

    destino = tr.salvar(
        _sessao.nota,
        raiz=vault(),
        fonte=f"gravação ({_sessao.fonte})",
        duracao_min=_sessao.segundos / 60 or None,
        nome=nome,
    )
    # O bruto já virou nota; guardá-lo seria manter duas cópias do mesmo texto.
    if _sessao.bruto_em:
        _sessao.bruto_em.unlink(missing_ok=True)

    _sessao.__init__()
    return destino


async def descartar() -> None:
    """Joga fora a sessão — inclusive uma gravação em andamento."""
    if _sessao.ffmpeg and _sessao.ffmpeg.poll() is None:
        _sessao.ffmpeg.kill()
    if _sessao.tarefa and not _sessao.tarefa.done():
        _sessao.tarefa.cancel()
    if _sessao.pasta_audio:
        shutil.rmtree(_sessao.pasta_audio, ignore_errors=True)
    if _sessao.bruto_em:
        _sessao.bruto_em.unlink(missing_ok=True)
    _sessao.__init__()


# Anúncio no meio da aula é ruído que entra na nota e no índice — e depois volta
# como resposta quando eu perguntar alguma coisa. Estas marcas **não apagam
# nada**: elas acendem o trecho na tela para eu decidir. Auto-remover seria
# apostar que a frase nunca aparece no conteúdo de verdade, e "assine o curso
# completo" aparece em aula sobre marketing.
_MARCAS_DE_ANUNCIO = re.compile(
    r"\b(patrocinad|publicidade|anúncio|propaganda|cupom|código de desconto|"
    r"link na descrição|link abaixo|primeiro link|use o código|"
    r"assine (o|a) (canal|curso|newsletter)|se inscrev|deixa o like|"
    r"ative o sininho|clique no link|oferta por tempo limitado|"
    r"parceir[oa] deste ví?deo|apoi(o|e) deste)\b",
    re.IGNORECASE,
)


def parece_anuncio(texto: str) -> bool:
    return bool(_MARCAS_DE_ANUNCIO.search(texto or ""))


async def descartar_trecho(indice: int) -> Sessao:
    """Tira um pedaço da transcrição — o corte do anúncio.

    Pelo `indice` do pedaço e não pela posição na lista: a lista muda enquanto
    eu leio (um trecho novo chega a cada 20 s), e clicar no ✕ do terceiro item
    tem que apagar o terceiro item, não o que estiver na terceira posição
    quando o clique chegar ao servidor.
    """
    if _sessao.estado not in ("gravando", "processando", "revisar"):
        raise GravacaoErro("Não há transcrição aberta.")

    antes = len(_sessao.trechos)
    _sessao.trechos = [t for t in _sessao.trechos if t.indice != indice]
    if len(_sessao.trechos) == antes:
        raise GravacaoErro(f"Trecho {indice} não existe (já foi descartado?).")

    logger.info(f"Trecho {indice} descartado da gravação")
    return _sessao


def estado() -> dict:
    """O que a tela pinta. Chamado de segundo em segundo durante a gravação."""
    ficha = _sessao.nota.fichamento if _sessao.nota else None
    return {
        "estado": _sessao.estado,
        "fonte": _sessao.fonte,
        "segundos": _sessao.segundos,
        "palavras": len(_sessao.texto.split()),
        # Os trechos na ordem em que saíram: é isto que aparece ao vivo, com o
        # ✕ para cortar anúncio e o instante para eu voltar no vídeo.
        "trechos": [
            {
                "indice": t.indice,
                "segundo": t.segundo,
                "relogio": t.relogio,
                "texto": t.texto,
                "anuncio": parece_anuncio(t.texto),
            }
            for t in _sessao.trechos
        ],
        "erro": _sessao.erro,
        "sugestao": (
            {
                "titulo": ficha.titulo,
                "resumo": ficha.resumo,
                "pasta": ficha.pasta,
                "tags": ficha.tags,
                "destaques": ficha.destaques,
                "conceitos": ficha.conceitos,
                "corrigidos": _sessao.nota.corrigidos,
                "nome_arquivo": tr.nome_de_arquivo(ficha.titulo),
                "relacionadas": ficha.relacionadas,
                "palavras": len(_sessao.nota.corpo.split()),
            }
            if ficha
            else None
        ),
    }
