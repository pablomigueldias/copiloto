"""Aperta o botão, assiste o vídeo, e no fim tem uma nota de estudo pronta.

    python scripts/transcrever.py                    # grava o áudio do sistema
    python scripts/transcrever.py --fonte mic        # grava o microfone (aula)
    python scripts/transcrever.py --arquivo aula.mp4 # transcreve um arquivo
    python scripts/transcrever.py --fontes           # lista os dispositivos

O que acontece, na ordem:

1. o `ffmpeg` grava o que está tocando em pedaços de 20 s;
2. o Whisper transcreve cada pedaço **enquanto o vídeo continua** e o texto vai
   aparecendo na tela;
3. `Ctrl+C` (ou Enter) encerra;
4. **aí** vem a tela perguntando o título, a pasta e as tags — com o que o
   modelo local sugeriu já preenchido, bastando `Enter` para aceitar;
5. a nota vai para o vault, formatada, e entra no índice do Copiloto.

## Por que perguntar o nome só no fim

Porque no começo eu não sei. Ligo a gravação quando o vídeo começa; o assunto
de verdade aparece no meio. Pedir o título antes é pedir um chute que eu nunca
volto para corrigir — e nome ruim de nota é o que faz a busca não achar depois.

## Por que Whisper local e não uma API

Reunião de trabalho e aula com dados de cliente não saem desta máquina. O
`small` num Ryzen 5600 roda em ~4× tempo real com 12 threads, o que sobra para
transcrever ao vivo sem atrasar. `--modelo medium` fica melhor em português e
ainda acompanha; a GPU fica livre para o Ollama, que é quem reescreve depois.
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.conhecimento import transcricao as tr
from app.conhecimento.varredura import ingerir
from app.db.session import dispose_engine

# Pedaço de 20 s: menos que isso e o Whisper perde contexto e erra mais no fim
# de cada trecho; mais que isso e o texto na tela fica atrasado a ponto de eu
# não conseguir acompanhar.
SEGUNDOS_POR_PEDACO = 20

VERDE, AMARELO, CINZA, NEGRITO, FIM = "\033[32m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"


def _vault() -> Path:
    """A primeira pasta `nota:` do .env — o vault que o Copiloto já indexa."""
    for tipo, caminho in settings.conhecimento_fontes_list:
        if tipo == "nota":
            return Path(caminho).expanduser()
    return Path.home() / "Documentos" / "Notas"


def _exige(programa: str) -> None:
    if not shutil.which(programa):
        sys.exit(f"'{programa}' não está instalado. Rode: sudo apt install {programa}")


# ── captura ───────────────────────────────────────────────────────


def dispositivo(fonte: str) -> str:
    """`sistema` = o monitor da saída (o que eu estou ouvindo). `mic` = a entrada."""
    if fonte == "sistema":
        sink = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
        return f"{sink}.monitor"
    return subprocess.check_output(["pactl", "get-default-source"], text=True).strip()


def listar_fontes() -> None:
    print(f"{NEGRITO}saídas (o `.monitor` de cada uma grava o som do sistema){FIM}")
    subprocess.run(["pactl", "list", "short", "sinks"], check=False)
    print(f"\n{NEGRITO}entradas (microfones){FIM}")
    subprocess.run(["pactl", "list", "short", "sources"], check=False)
    for rotulo, fonte in (("sistema", "sistema"), ("mic", "mic")):
        print(f"\n{rotulo:<8} → {dispositivo(fonte)}")


class Whisper:
    """O modelo, carregado uma vez. Import tardio: `faster_whisper` custa 3 s."""

    def __init__(self, nome: str, *, idioma: str | None, dispositivo: str = "cpu") -> None:
        from faster_whisper import WhisperModel

        print(f"{CINZA}carregando Whisper '{nome}' ({dispositivo})…{FIM}", flush=True)
        # int8 na CPU: metade da RAM e praticamente a mesma qualidade num modelo
        # deste tamanho. `cpu_threads=0` deixa o ctranslate2 usar todos os núcleos.
        self.modelo = WhisperModel(
            nome,
            device=dispositivo,
            compute_type="int8" if dispositivo == "cpu" else "float16",
            cpu_threads=0,
        )
        self.idioma = idioma

    def transcrever(self, caminho: Path) -> str:
        segmentos, _ = self.modelo.transcribe(
            str(caminho),
            language=self.idioma,
            vad_filter=True,      # corta silêncio: menos alucinação em pausa longa
            beam_size=5,
        )
        return " ".join(s.text.strip() for s in segmentos).strip()


def gravar_ao_vivo(whisper: Whisper, fonte: str, pasta: Path) -> tuple[str, float]:
    """Grava e transcreve em paralelo até eu mandar parar. Devolve texto e minutos."""
    _exige("ffmpeg")
    _exige("pactl")
    device = dispositivo(fonte)
    pasta.mkdir(parents=True, exist_ok=True)

    rotulo = "áudio do sistema (vídeo/reunião)" if fonte == "sistema" else "microfone"
    print(f"\n{NEGRITO}🎙  gravando: {rotulo}{FIM}  {CINZA}[{device}]{FIM}")
    print(f"{CINZA}o texto aparece aqui a cada {SEGUNDOS_POR_PEDACO}s{FIM}")
    print(f"{AMARELO}▶ pode dar play. Enter (ou Ctrl+C) encerra.{FIM}\n")

    # 16 kHz mono é exatamente o que o Whisper consome; converter aqui evita
    # que ele reamostre cada pedaço depois.
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-f", "pulse", "-i", device,
         "-ac", "1", "-ar", "16000",
         "-f", "segment", "-segment_time", str(SEGUNDOS_POR_PEDACO),
         "-reset_timestamps", "1", str(pasta / "p%05d.wav")],
        stdin=subprocess.DEVNULL,
    )

    parar = threading.Event()
    trechos: list[str] = []
    comeco = time.monotonic()

    def consumir() -> None:
        """Um pedaço só é transcrito quando o seguinte já começou (= está fechado)."""
        i = 0
        while True:
            atual, proximo = pasta / f"p{i:05d}.wav", pasta / f"p{i + 1:05d}.wav"
            if atual.exists() and (proximo.exists() or parar.is_set()):
                try:
                    texto = whisper.transcrever(atual)
                    if texto:
                        trechos.append(texto)
                        print(f"{VERDE}▸{FIM} {texto}\n", flush=True)
                except Exception as e:  # noqa: BLE001 — um pedaço ruim não perde a sessão
                    print(f"{AMARELO}(pedaço {i} falhou: {e}){FIM}")
                atual.unlink(missing_ok=True)
                i += 1
            elif parar.is_set() and not atual.exists():
                return
            else:
                time.sleep(0.4)

    thread = threading.Thread(target=consumir, daemon=True)
    thread.start()

    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        print(f"\n{CINZA}encerrando e transcrevendo o que sobrou…{FIM}")
        ffmpeg.send_signal(signal.SIGINT)
        try:
            ffmpeg.wait(timeout=10)
        except subprocess.TimeoutExpired:
            ffmpeg.kill()
        time.sleep(1.0)          # o último segmento ainda está fechando
        parar.set()
        thread.join(timeout=300)

    shutil.rmtree(pasta, ignore_errors=True)
    return " ".join(trechos).strip(), (time.monotonic() - comeco) / 60


# ── a tela do fim ─────────────────────────────────────────────────


def _perguntar(rotulo: str, sugestao: str) -> str:
    """Sugestão entre colchetes; `Enter` aceita. É o que torna a tela rápida."""
    resposta = input(f"{NEGRITO}{rotulo}{FIM} [{CINZA}{sugestao}{FIM}]: ").strip()
    return resposta or sugestao


def revisar(nota: tr.Nota, pastas: list[str]) -> str:
    """A tela final: confirmo título, pasta e tags. Devolve o nome do arquivo.

    Edita o fichamento no lugar; o nome do arquivo volta separado porque é a
    única escolha que não pertence ao fichamento — é onde o arquivo mora, não o
    que ele é.
    """
    f = nota.fichamento
    print(f"\n{NEGRITO}{'─' * 62}{FIM}")
    print(f"{NEGRITO}transcrição pronta{FIM} · {len(nota.corpo.split())} palavras")
    if nota.corrigidos:
        print(f"{CINZA}glossário corrigiu: {', '.join(nota.corrigidos[:6])}"
              f"{'…' if len(nota.corrigidos) > 6 else ''}{FIM}")
    if f.resumo:
        print(f"\n{CINZA}{f.resumo}{FIM}")
    print(f"{NEGRITO}{'─' * 62}{FIM}\n")

    f.titulo = _perguntar("título da nota", f.titulo)

    sugerida = f.pasta if f.pasta in pastas else (pastas[0] if pastas else "Inbox")
    print(f"{CINZA}pastas: {', '.join(pastas[:12])}{'…' if len(pastas) > 12 else ''}{FIM}")
    f.pasta = _perguntar("pasta", sugerida)

    f.tags = [t.strip() for t in _perguntar("tags (vírgula)", ", ".join(f.tags)).split(",") if t.strip()]

    arquivo = _perguntar("nome do arquivo", tr.nome_de_arquivo(f.titulo))
    return arquivo if arquivo.endswith(".md") else f"{arquivo}.md"


# ── caminho principal ─────────────────────────────────────────────


async def executar(args: argparse.Namespace) -> int:
    vault = Path(args.vault).expanduser() if args.vault else _vault()
    if not vault.is_dir():
        sys.exit(f"Vault não encontrado: {vault}. Use --vault.")

    idioma = None if args.idioma == "auto" else args.idioma
    whisper = Whisper(args.modelo, idioma=idioma, dispositivo=args.dispositivo)

    if args.arquivo:
        caminho = Path(args.arquivo).expanduser()
        if not caminho.exists():
            sys.exit(f"Arquivo não encontrado: {caminho}")
        print(f"{CINZA}transcrevendo {caminho.name}…{FIM}")
        bruto, minutos, fonte = whisper.transcrever(caminho), None, str(caminho)
    else:
        temp = Path("/tmp") / f"copiloto-audio-{datetime.now(UTC):%H%M%S}"
        bruto, minutos = gravar_ao_vivo(whisper, args.fonte, temp)
        fonte = f"gravação ({args.fonte})"

    if not bruto:
        sys.exit("Nada foi transcrito. Confira a fonte com --fontes.")

    # Rede de segurança: o bruto vai para o disco antes de qualquer LLM. Se o
    # Ollama estiver fora ou eu fechar o terminal, a transcrição não se perde.
    rascunho = vault / "_inbox" / f"bruto-{datetime.now(UTC):%Y-%m-%d-%H%M}.md"
    rascunho.parent.mkdir(parents=True, exist_ok=True)
    rascunho.write_text(bruto, encoding="utf-8")
    print(f"{CINZA}bruto salvo em {rascunho}{FIM}")

    print(f"{CINZA}o modelo local está organizando a transcrição…{FIM}")
    nota = await tr.processar(
        bruto,
        tema=args.tema or "transcrição",
        raiz_vault=vault,
        reescrever_com_llm=not args.sem_llm,
    )

    nome = revisar(nota, tr.pastas_do_vault(vault))
    destino = tr.salvar(nota, raiz=vault, fonte=fonte, duracao_min=minutos, nome=nome)

    rascunho.unlink(missing_ok=True)
    print(f"\n{VERDE}✓ nota salva{FIM}  {destino}")

    if not args.sem_indexar:
        print(f"{CINZA}indexando no Copiloto…{FIM}")
        resultado = await ingerir(tipos=["nota"], caminho=str(destino))
        for tipo, r in resultado.items():
            print(f"{CINZA}  {tipo}: {r}{FIM}")
        print(f"{CINZA}pergunte no painel: “o que eu estudei sobre …?”{FIM}")
    return 0


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    p.add_argument("--fonte", choices=["sistema", "mic"], default="sistema",
                   help="'sistema' grava o que está tocando; 'mic', o microfone.")
    p.add_argument("--arquivo", help="Transcreve um arquivo em vez de gravar.")
    p.add_argument("--tema", help="Uma pista do assunto (o título vem no fim).")
    p.add_argument("--modelo", default="small",
                   help="Modelo Whisper: tiny, base, small, medium, large-v3.")
    p.add_argument("--dispositivo", default="cpu", choices=["cpu", "cuda"],
                   help="'cpu' deixa a GPU livre para o Ollama (padrão).")
    p.add_argument("--idioma", default="pt", help="'pt', 'en' ou 'auto'.")
    p.add_argument("--vault", help="Raiz do vault (padrão: a fonte 'nota' do .env).")
    p.add_argument("--sem-llm", action="store_true",
                   help="Pula a reescrita; salva o texto limpo pelo glossário.")
    p.add_argument("--sem-indexar", action="store_true")
    p.add_argument("--fontes", action="store_true", help="Lista os dispositivos e sai.")
    return p.parse_args()


async def main() -> int:
    args = _argumentos()
    if args.fontes:
        listar_fontes()
        return 0
    try:
        return await executar(args)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
