"""A sessão de gravação — o que o botão do painel liga e desliga.

`scripts/transcrever.py` faz isto pelo terminal. Este módulo faz o mesmo pela
tela, e a diferença não é enfeite: **eu ligo a gravação quando o vídeo começa**,
e nesse momento eu estou no navegador, não num terminal. Um passo a mais entre
"vou assistir" e "estou gravando" é o passo que faz não gravar.

## A máquina de estados

    ocioso ──iniciar──► gravando ──parar──► processando ──► revisar ──salvar──► ocioso
                            │                                   │
                            └──────────── descartar ────────────┘

`processando` existe separado porque é onde o LLM ficha a transcrição. Se isso
acontecesse dentro do `parar`, a requisição estouraria o timeout e eu perderia a
gravação por causa da etapa cosmética.

## A GPU trabalha durante a aula, não depois

Os blocos da reescrita **são independentes**: um bloco de ~600 palavras é ~4 min
de fala, e o primeiro está completo no minuto 5 de uma aula de 26. Antes, os seis
blocos e o fichamento rodavam todos depois do `parar` — 3 min 30 de tela muda,
com a GPU tendo ficado ociosa os 26 minutos anteriores.

Agora cada bloco vai para o LLM **no instante em que fecha**, com o vídeo ainda
rodando. Ao apertar parar sobra um bloco (o último, incompleto) e o fichamento:
~1 min em vez de 3 min 30. Ver docs/fase-transcricao.md §P1.

São duas tarefas, e a separação é o ponto: `_consumir` transcreve
(faster-whisper) e `_reescrever_ao_vivo` reescreve (Ollama). Se a inferência
rodasse dentro do laço de transcrição, o texto na tela congelaria 30 s a cada 4
minutos — justo o retorno que me faz notar que a fonte de áudio está errada.

As duas dividem a mesma placa desde que o Whisper saiu da CPU, e é por isso que
a gravação carrega o modelo pequeno (`turbo` quantizado, 1.217 MiB medidos) e o
caminho de arquivo carrega o `large-v3` inteiro (3.905 MiB, que só cabem quando
ninguém mais está lá) — ver `app/conhecimento/whisper.py`.

## Uma sessão por vez

É deliberado. A GPU é uma só — e agora o Whisper também está nela —, e não
existe caso real de gravar duas reuniões ao mesmo tempo. Estado em memória de processo, sem tabela:
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
from app.conhecimento import whisper
from app.utils.logger import get_logger

logger = get_logger()

# Pedaço de 20 s: menos que isso e o Whisper perde contexto e erra mais no fim
# de cada trecho; mais que isso e o texto na tela atrasa a ponto de eu não
# conseguir acompanhar o que está sendo dito.
SEGUNDOS_POR_PEDACO = 20

PASTA_BRUTOS = DATA_DIR / "transcricoes"

# O assunto da aula não é conhecido quando a gravação começa — é o motivo de o
# título ser perguntado no fim. Os dois pontos que chamam o LLM usam o mesmo
# valor, para o bloco reescrito ao vivo e o reescrito depois saírem iguais.
TEMA = "transcrição"


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
    # Já entrou num bloco que foi reescrito. A partir daí o ✕ não corta mais:
    # cortar obrigaria a refazer a reescrita do bloco, e o corte existe para o
    # anúncio — que eu vejo em 20 s, não em 5 min.
    processado: bool = False

    @property
    def relogio(self) -> str:
        return f"{self.segundo // 60:02d}:{self.segundo % 60:02d}"


@dataclass
class Sessao:
    estado: str = "ocioso"          # ocioso | gravando | processando | revisar
    # O que o servidor está fazendo agora, para a tela poder dizer em vez de
    # ficar 3 minutos em "organizando…": transcrevendo | reescrevendo | fichando.
    etapa: str | None = None
    fonte: str = "sistema"
    trechos: list[Trecho] = field(default_factory=list)
    comecou_em: float | None = None
    # Congelado no `parar`. Sem isto o cronômetro corria durante o
    # `processando` e o tempo do LLM entrava na duração do vídeo (26 min → 30).
    parou_em: float | None = None
    erro: str | None = None

    # ── a reescrita que acontece durante a aula (§P1) ──
    # `[(segundo, texto)]` dos blocos que o LLM já devolveu, na ordem.
    blocos: list[tuple[int, str]] = field(default_factory=list)
    # Quantos blocos já foram fechados e mandados para a fila. Junto com
    # `len(blocos)` é o "bloco 3 de 6" da tela: fechados é o total conhecido.
    blocos_fechados: int = 0
    # O texto limpo, bloco a bloco. É dele que sai a vizinhança no fim — e
    # guardá-lo aqui evita reaplicar as 256 regras do glossário no texto inteiro.
    limpo: list[str] = field(default_factory=list)
    corrigidos: list[str] = field(default_factory=list)
    ruido: list[str] = field(default_factory=list)
    # A medida que decide se o P1 fica: a inferência agora divide RAM e barramento
    # com o Whisper, e se o Whisper começar a perder pedaço, o P1 sai.
    pedacos_falhos: int = 0

    # Preenchidos na etapa `processando`.
    nota: tr.Nota | None = None
    bruto_em: Path | None = None

    ffmpeg: subprocess.Popen | None = None
    pasta_audio: Path | None = None
    tarefa: asyncio.Task | None = None
    # A fila entre as duas tarefas, e a tarefa que a drena. `None` fora de uma
    # gravação — o caminho do arquivo não tem reescrita ao vivo.
    fila: asyncio.Queue | None = None
    tarefa_llm: asyncio.Task | None = None

    @property
    def segundos(self) -> int:
        if not self.comecou_em:
            return 0
        return int((self.parou_em or time.monotonic()) - self.comecou_em)

    @property
    def texto(self) -> str:
        return " ".join(t.texto for t in self.trechos).strip()

    @property
    def pendentes(self) -> list[Trecho]:
        """Os pedaços que ainda não entraram em bloco nenhum."""
        return [t for t in self.trechos if not t.processado]

    @property
    def blocos_previstos(self) -> int:
        """Quantos blocos a nota vai ter — o denominador do "bloco 3 de 6".

        Durante a gravação é uma previsão que cresce: o que já fechou, mais o que
        está acumulando. Depois do `parar` não sobra pendente, e o número é exato.
        """
        return self.blocos_fechados + (1 if self.pendentes else 0)


# Estado de módulo, e não tabela: uma gravação não sobrevive a restart do
# servidor de propósito — o áudio já teria ido junto. O lock protege só o
# `iniciar`, que é o único ponto onde duas requisições poderiam abrir sessão
# ao mesmo tempo.
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
    """Carrega o Whisper uma vez, na configuração de gravação ao vivo.

    `folgado=False` porque aqui a GPU é dividida: o `_reescrever_ao_vivo` está
    mandando bloco para o Ollama enquanto este laço transcreve. Ver
    `app/conhecimento/whisper.py`.
    """
    global _modelo
    if _modelo is None:
        try:
            _modelo = whisper.carregar(folgado=False)
        except RuntimeError as e:
            raise GravacaoErro(str(e)) from e
    return _modelo


def _transcrever(caminho: Path) -> str:
    modelo = _carregar_whisper()
    segmentos, _ = modelo.transcribe(
        str(caminho),
        language=whisper.idioma(),
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
                sessao.pedacos_falhos += 1
                logger.warning(f"Pedaço {i} falhou: {type(e).__name__}: {e}")
            atual.unlink(missing_ok=True)
            i += 1
            # Fora do `try` de propósito: um erro daqui não é pedaço perdido, e
            # contá-lo como tal falsearia justo a medida que decide o §P1.
            await _fechar_bloco_se_cheio(sessao)
        # Parando e o pedaço `i` nem existe: o ffmpeg já fechou tudo e não vem
        # mais nada. É a única saída do laço — sem ela ele giraria para sempre.
        elif parando and not atual.exists():
            return
        else:
            await asyncio.sleep(0.4)


def _palavras_pendentes(sessao: Sessao) -> int:
    return sum(len(t.texto.split()) for t in sessao.pendentes)


async def _fechar_bloco_se_cheio(sessao: Sessao) -> None:
    """O gatilho do §P1: ~600 palavras acumuladas já são um bloco.

    O mesmo corte da reescrita em lote (`tr.PALAVRAS_POR_BLOCO`), porque o bloco
    que nasce aqui é o mesmo — só nasce durante a aula em vez de depois dela.
    """
    if _palavras_pendentes(sessao) >= tr.PALAVRAS_POR_BLOCO:
        await _fechar_bloco(sessao)


async def _fechar_bloco(sessao: Sessao) -> None:
    """Fecha o bloco acumulado e o entrega à reescrita. Não espera o LLM.

    Marcar os pedaços como processados **aqui**, e não quando o LLM responde, é o
    que garante que o ✕ pare de cortar antes de a reescrita começar — cortar no
    meio dela deixaria o bloco reescrito contendo um trecho que já não existe.
    """
    pendentes = sessao.pendentes
    if not pendentes or sessao.fila is None:
        return
    for t in pendentes:
        t.processado = True
    sessao.blocos_fechados += 1
    await sessao.fila.put([(t.segundo, t.texto) for t in pendentes])
    logger.info(
        f"Bloco {sessao.blocos_fechados} fechado aos {pendentes[0].relogio} "
        f"({sum(len(t.texto.split()) for t in pendentes)} palavras) — vai reescrever"
    )


async def _reescrever_ao_vivo(sessao: Sessao) -> None:
    """Drena a fila de blocos fechados e reescreve cada um, na ordem.

    Um por vez, e sem paralelismo: o semáforo do gateway é 1 por causa dos 6 GB
    de VRAM, e isso continua certo. O ganho do §P1 não é paralelismo — é
    **quando**: o trabalho acontece enquanto eu assisto, não depois.

    A sentinela `None` é o fim da fila, posta pelo `_organizar` quando o último
    bloco já entrou. Sem ela esta tarefa esperaria para sempre.
    """
    glossario = tr.carregar_glossario()
    while True:
        pedacos = await sessao.fila.get()
        if pedacos is None:
            return

        indice = len(sessao.blocos) + 1
        segundo = pedacos[0][0]
        # O glossário e o filtro de ruído rodam aqui, no bloco de ~600 palavras,
        # em vez de no texto inteiro depois. `limpar_ruido` trabalha frase a
        # frase, então o resultado é o mesmo — só chega antes.
        texto, corrigidos, ruido = tr.limpar(" ".join(t for _, t in pedacos), glossario)
        sessao.corrigidos = sorted({*sessao.corrigidos, *corrigidos})
        sessao.ruido += ruido
        if not texto.strip():
            continue      # bloco que era só saudação e pedido de inscrição

        sessao.limpo.append(texto)
        try:
            reescrito = await tr.reescrever_um(texto, tema=TEMA, indice=indice)
        except Exception as e:  # noqa: BLE001 — um bloco cru é melhor que a sessão morta
            logger.warning(f"Bloco {indice} não foi reescrito ({type(e).__name__}: {e}).")
            reescrito = texto
        sessao.blocos.append((segundo, reescrito))
        logger.info(f"  bloco {indice}/{sessao.blocos_previstos} pronto")


def _encerrar_tarefas(sessao: Sessao) -> None:
    """Cancela as duas tarefas de fundo, se ainda estiverem em pé.

    **Obrigatório antes de qualquer `__init__()` de reset.** `_reescrever_ao_vivo`
    fica bloqueada em `fila.get()` esperando a sentinela, e o reset é feito na
    própria instância (para as referências espalhadas pelo módulo continuarem
    válidas) — uma tarefa esquecida acordaria depois e escreveria bloco na
    **sessão seguinte**.
    """
    for tarefa in (sessao.tarefa, sessao.tarefa_llm):
        if tarefa and not tarefa.done():
            tarefa.cancel()


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

        # Sessão anterior que morreu sem passar pelo `descartar` (o `parar` que
        # não achou texto, por exemplo) pode ter deixado a reescrita esperando.
        _encerrar_tarefas(_sessao)

        # `__init__` na instância existente zera todos os campos de uma vez e
        # mantém o mesmo objeto — que é o que os `_sessao.` espalhados pelo
        # módulo referenciam. Reatribuir `_sessao = Sessao()` funcionaria aqui,
        # mas deixaria a tarefa em voo apontando para a sessão velha.
        _sessao.__init__()
        _sessao.estado = "gravando"
        _sessao.etapa = "transcrevendo"
        _sessao.fonte = fonte
        _sessao.comecou_em = time.monotonic()
        _sessao.ffmpeg = ffmpeg
        _sessao.pasta_audio = pasta
        _sessao.fila = asyncio.Queue()
        _sessao.tarefa = asyncio.create_task(_consumir(_sessao))
        _sessao.tarefa_llm = asyncio.create_task(_reescrever_ao_vivo(_sessao))

        logger.info(f"Gravando de {fonte} ({device})")
        return _sessao


async def parar() -> Sessao:
    """Encerra a captura e devolve o texto bruto. **Não espera o LLM.**

    Os blocos fechados durante a aula já foram reescritos; o que fica para o
    segundo plano é o último bloco e o fichamento.
    """
    if _sessao.estado != "gravando":
        raise GravacaoErro("Não há gravação em andamento.")

    _sessao.estado = "processando"
    _sessao.etapa = "reescrevendo"
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
        # A reescrita nunca vai receber a sentinela: quem a põe é o `_organizar`,
        # que não vai rodar. Sem este cancelamento ela esperaria para sempre.
        _encerrar_tarefas(_sessao)
        _sessao.estado = "ocioso"
        _sessao.etapa = None
        raise GravacaoErro("Nada foi transcrito — confira a fonte de áudio.")

    # Rede de segurança: o bruto no disco antes de qualquer LLM. Se o Ollama
    # estiver fora ou eu fechar a aba, a gravação não se perde.
    PASTA_BRUTOS.mkdir(parents=True, exist_ok=True)
    _sessao.bruto_em = PASTA_BRUTOS / f"bruto-{datetime.now(UTC):%Y-%m-%d-%H%M}.txt"
    _sessao.bruto_em.write_text(_sessao.texto, encoding="utf-8")
    logger.info(
        f"Bruto salvo: {_sessao.bruto_em} ({len(_sessao.texto.split())} palavras, "
        f"{_sessao.blocos_fechados} bloco(s) já reescrito(s), "
        f"{_sessao.pedacos_falhos} pedaço(s) falho(s))"
    )

    _sessao.tarefa = asyncio.create_task(_organizar(_sessao))
    return _sessao


async def _organizar(sessao: Sessao) -> None:
    """O que sobrou para depois do `parar`: o último bloco e o fichamento.

    Roda em segundo plano. Antes do §P1 esta função era a transcrição inteira —
    seis blocos e o fichamento, 3 min 30 de espera. Hoje os blocos já estão
    prontos e ela costura.
    """
    corpo = ""
    try:
        # O resto que não completou 600 palavras vira o último bloco, e a
        # sentinela avisa a tarefa da reescrita que não vem mais nada.
        await _fechar_bloco(sessao)
        await sessao.fila.put(None)
        if sessao.tarefa_llm:
            await sessao.tarefa_llm

        corpo = tr.juntar_blocos(sessao.blocos)
        sessao.etapa = "fichando"
        sessao.nota = await tr.catalogar(
            corpo,
            tema=TEMA,
            raiz_vault=vault(),
            # A vizinhança sai do texto limpo, não do reescrito — e ele já está
            # acumulado bloco a bloco desde o começo da aula.
            texto_da_busca=" ".join(sessao.limpo),
            corrigidos=sessao.corrigidos,
            ruido=sessao.ruido,
        )
        sessao.estado = "revisar"
        logger.info(f"Transcrição organizada: {sessao.nota.fichamento.titulo!r}")
    except Exception as e:  # noqa: BLE001 — a nota crua ainda vale
        logger.warning(f"Falhou ao organizar ({type(e).__name__}: {e}); vai o texto limpo.")
        sessao.erro = f"{type(e).__name__}: {e}"
        # `corpo` já tem os blocos que deram certo; se nem eles existem, o texto
        # limpo na hora. Perder a formatação é reversível — perder a aula não.
        limpo, corrigidos, ruido = tr.limpar(sessao.texto, tr.carregar_glossario())
        sessao.nota = tr.Nota(
            fichamento=tr.Fichamento(titulo="Transcrição sem título"),
            corpo=corpo or limpo,
            corrigidos=sessao.corrigidos or corrigidos,
            ruido=sessao.ruido or ruido,
        )
        sessao.estado = "revisar"
    finally:
        sessao.etapa = None


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

    _encerrar_tarefas(_sessao)
    _sessao.__init__()
    return destino


async def descartar() -> None:
    """Joga fora a sessão — inclusive uma gravação em andamento."""
    if _sessao.ffmpeg and _sessao.ffmpeg.poll() is None:
        _sessao.ffmpeg.kill()
    _encerrar_tarefas(_sessao)
    if _sessao.pasta_audio:
        shutil.rmtree(_sessao.pasta_audio, ignore_errors=True)
    if _sessao.bruto_em:
        _sessao.bruto_em.unlink(missing_ok=True)
    _sessao.__init__()


# Anúncio entra na nota, vai para o índice e volta como resposta depois. Estas
# marcas **acendem** o trecho na tela; não apagam. Auto-remover apostaria que a
# frase nunca é conteúdo — e "assine o curso completo" aparece em aula de
# marketing.
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

    **Trecho que já entrou num bloco reescrito não corta mais.** Desde o §P1 o
    bloco vai para o LLM no minuto 5 da aula, e cortar depois obrigaria a pagar a
    reescrita de novo. O ✕ existe para o anúncio, que eu vejo em 20 s.
    """
    if _sessao.estado not in ("gravando", "processando", "revisar"):
        raise GravacaoErro("Não há transcrição aberta.")

    alvo = next((t for t in _sessao.trechos if t.indice == indice), None)
    if alvo is None:
        raise GravacaoErro(f"Trecho {indice} não existe (já foi descartado?).")
    if alvo.processado:
        raise GravacaoErro(
            f"O trecho de {alvo.relogio} já foi organizado num bloco — corte o "
            "texto na revisão, antes de salvar."
        )

    _sessao.trechos.remove(alvo)
    logger.info(f"Trecho {indice} descartado da gravação")
    return _sessao


def estado() -> dict:
    """O que a tela pinta. Chamado de segundo em segundo durante a gravação.

    `etapa`, `bloco` e `blocos` são o §U1: o servidor sempre soube em que bloco
    estava — `logger.info("bloco 3/6 pronto")` — e a tela dizia "organizando…"
    por três minutos, que é onde eu penso que travou.
    """
    ficha = _sessao.nota.fichamento if _sessao.nota else None
    return {
        "estado": _sessao.estado,
        "etapa": _sessao.etapa,
        "fonte": _sessao.fonte,
        "segundos": _sessao.segundos,
        "palavras": len(_sessao.texto.split()),
        "bloco": len(_sessao.blocos),
        "blocos": _sessao.blocos_previstos,
        "trechos": [
            {
                "indice": t.indice,
                "segundo": t.segundo,
                "relogio": t.relogio,
                "texto": t.texto,
                "anuncio": parece_anuncio(t.texto),
                "processado": t.processado,
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
