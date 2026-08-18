"""Onde o Whisper roda, e com qual precisão.

Nasceu quando o Ollama deixou de ser o dono da placa. Antes, o Whisper estava na
CPU **de propósito** — a 2060 inteira era do modelo de reescrita, e o `small` a
6,6× tempo real acompanhava a aula ao vivo com folga. O preço era a qualidade da
transcrição bruta, que é a raiz de tudo que vem depois: o `small` ouviu
`Vera Ficha` no lugar de "V → F" e "15% de 30% é igual a 45%" no lugar de
"15% de 30 é 4,5" (fase-transcricao §6.6). Erro assim não tem conserto adiante —
o glossário substitui palavra, não reconstrói número.

## Dois modelos, porque são duas situações de VRAM

Durante a gravação a placa é **dividida**: o `gemma4:e4b` reescreve os blocos ao
vivo (§P1) e come ~4 GB dos 6. Depois do `parar` — e no caminho de arquivo — não
há mais nada na GPU, e o Whisper pode ocupar tudo.

Medido nesta máquina em 17/08/2026 (`nvidia-smi` depois da primeira inferência,
que é quando a reserva de fato acontece; 311 MiB já eram do desktop):

    ao vivo    large-v3-turbo · int8_float16  1.217 MiB   sobram ~4,6 GB de Ollama
    arquivo    large-v3       · float16       3.905 MiB   a placa é toda dele

O `turbo` é o `large-v3` destilado: mesma família, muito melhor que o `small` em
português, e pequeno o bastante para não brigar com o Ollama.

**O caminho de arquivo tem uma ressalva que a medida expôs.** Os 3.905 MiB só
cabem se o Ollama não estiver com modelo residente — e o `OLLAMA_KEEP_ALIVE=5m`
do `scripts/ollama-serve.sh` mantém o último carregado por cinco minutos depois
do uso. Transcrever um arquivo logo após uma gravação pode dar OOM. Se acontecer,
esperar os 5 min ou `WHISPER_MODELO_ARQUIVO=large-v3-turbo` resolve.

## Por que o preload de biblioteca existe

O `ctranslate2` abre o cuBLAS e o cuDNN com `dlopen` na primeira inferência — não
no `WhisperModel(...)`. O sintoma é cruel: o modelo **carrega** na GPU e só
quebra ao transcrever, com `Library libcublas.so.12 is not found`.

As bibliotecas vêm dos pacotes `nvidia-*-cu12` dentro da venv, que o carregador
dinâmico não procura sozinho. Exportar `LD_LIBRARY_PATH` resolveria, mas exigiria
lembrar disso em todo ponto de entrada (painel, CLI, worker, teste). Carregar com
`ctypes` no processo resolve de dentro: uma vez abertas, o `dlopen` seguinte
encontra pelo soname.
"""
from __future__ import annotations

import ctypes
import glob
import sysconfig
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger()

# Os dois pacotes que o ctranslate2 4.8 procura para falar com a CUDA 12.
_PACOTES_CUDA = ("cublas", "cudnn")


@lru_cache(maxsize=1)
def _preparar_cuda() -> bool:
    """Abre cuBLAS e cuDNN no processo. `False` = não dá para usar a GPU.

    O cuDNN 9 é dividido em sub-bibliotecas (`ops`, `cnn`, `engines_*`) que a
    principal abre por conta, então carregamos o diretório inteiro em vez de
    escolher arquivo — errar a lista dá o mesmo `dlopen` falhando, três camadas
    abaixo, na primeira inferência.
    """
    raiz = Path(sysconfig.get_paths()["purelib"]) / "nvidia"
    arquivos: list[str] = []
    for pacote in _PACOTES_CUDA:
        arquivos += sorted(glob.glob(str(raiz / pacote / "lib" / "lib*.so.*")))

    if not arquivos:
        logger.warning(
            "Bibliotecas CUDA ausentes na venv; o Whisper fica na CPU. "
            "Para a GPU: pip install -e '.[transcricao-gpu]'"
        )
        return False

    for caminho in arquivos:
        try:
            ctypes.CDLL(caminho, mode=ctypes.RTLD_GLOBAL)
        except OSError as e:
            logger.warning(f"CUDA: não abriu {Path(caminho).name} ({e}); o Whisper fica na CPU.")
            return False
    return True


def _tem_gpu() -> bool:
    try:
        import ctranslate2
    except ImportError:
        return False
    return ctranslate2.get_cuda_device_count() > 0 and _preparar_cuda()


def escolher(
    *, folgado: bool = False, modelo: str | None = None, dispositivo: str | None = None
) -> tuple[str, str, str]:
    """`(modelo, dispositivo, precisão)` para a situação.

    `folgado` = ninguém mais está na GPU (arquivo, reprocessamento). Ao vivo ela
    é dividida com o Ollama, e é isso que decide tanto o modelo quanto a
    precisão — ver o cabeçalho do módulo.

    `modelo` e `dispositivo` existem para as flags da CLI mandarem mais que o
    `.env` numa rodada — medir `turbo` contra `large-v3` na mesma aula é
    exatamente o que o §P3 do plano pede, e editar o `.env` entre as duas
    medidas é o tipo de atrito que faz não medir.
    """
    modelo = modelo or (
        settings.whisper_modelo_arquivo if folgado else settings.whisper_modelo
    )
    pedido = dispositivo or settings.whisper_dispositivo

    if pedido == "cpu" or (pedido == "auto" and not _tem_gpu()):
        # `int8` na CPU: metade da RAM e praticamente a mesma qualidade.
        return modelo, "cpu", "int8"
    if pedido == "cuda" and not _tem_gpu():
        raise RuntimeError(
            "WHISPER_DISPOSITIVO=cuda mas a GPU não está utilizável "
            "(sem placa, ou sem as bibliotecas de '.[transcricao-gpu]')."
        )
    return modelo, "cuda", "float16" if folgado else "int8_float16"


def carregar(
    *, folgado: bool = False, modelo: str | None = None, dispositivo: str | None = None
):
    """O `WhisperModel` pronto. Import tardio: `faster_whisper` custa ~3 s."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError(
            "faster-whisper não instalado. Rode: pip install -e '.[transcricao]'"
        ) from e

    modelo, dispositivo, precisao = escolher(
        folgado=folgado, modelo=modelo, dispositivo=dispositivo
    )
    logger.info(f"Carregando Whisper '{modelo}' ({dispositivo}/{precisao})...")
    # `cpu_threads=0` deixa o ctranslate2 usar todos os núcleos; na GPU o
    # parâmetro é ignorado, e passá-lo sempre evita dois caminhos de construção.
    return WhisperModel(modelo, device=dispositivo, compute_type=precisao, cpu_threads=0)


def idioma() -> str | None:
    """`None` = o Whisper detecta sozinho."""
    return None if settings.whisper_idioma == "auto" else settings.whisper_idioma
