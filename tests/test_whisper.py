"""Onde o Whisper roda — a decisão, não a transcrição.

Transcrever de verdade exige placa, modelo baixado e áudio; nada disso cabe numa
suíte. O que cabe — e é o que quebrou de verdade — é a **escolha**: qual modelo,
em qual dispositivo, com qual precisão. O defeito que motivou este arquivo foi
silencioso: `WhisperModel(device="cuda")` constrói sem erro numa máquina sem
cuBLAS e só estoura na primeira inferência, minutos depois, com a aula rodando.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.conhecimento import whisper


@pytest.fixture
def sem_gpu(monkeypatch):
    monkeypatch.setattr(whisper, "_tem_gpu", lambda: False)


@pytest.fixture
def com_gpu(monkeypatch):
    monkeypatch.setattr(whisper, "_tem_gpu", lambda: True)


# ── a escolha de modelo ───────────────────────────────────────────


def test_ao_vivo_e_arquivo_usam_modelos_diferentes(com_gpu):
    """A razão de existirem duas chaves: ao vivo divide a GPU, arquivo não."""
    ao_vivo, _, _ = whisper.escolher(folgado=False)
    arquivo, _, _ = whisper.escolher(folgado=True)

    assert ao_vivo == settings.whisper_modelo
    assert arquivo == settings.whisper_modelo_arquivo
    assert ao_vivo != arquivo


def test_arquivo_ganha_precisao_cheia_e_ao_vivo_nao(com_gpu):
    """`float16` só onde ninguém mais está na placa.

    Medido em 17/08/2026: `large-v3`/float16 reserva 3.905 MiB e o
    `large-v3-turbo`/int8_float16 reserva 1.217 MiB. Ao vivo o `gemma4:e4b` já
    ocupa ~4 dos 6 GB, então só o segundo cabe junto — e o OOM do primeiro
    apareceria como erro 500 do Ollama no meio da aula.
    """
    assert whisper.escolher(folgado=True)[2] == "float16"
    assert whisper.escolher(folgado=False)[2] == "int8_float16"


# ── o dispositivo ─────────────────────────────────────────────────


def test_sem_gpu_cai_para_cpu_sozinho(sem_gpu, monkeypatch):
    """Máquina sem NVIDIA (ou sem as libs) continua transcrevendo."""
    monkeypatch.setattr(settings, "whisper_dispositivo", "auto")
    _, dispositivo, precisao = whisper.escolher()
    assert (dispositivo, precisao) == ("cpu", "int8")


def test_cuda_explicito_sem_gpu_falha_alto(sem_gpu, monkeypatch):
    """Quem pediu `cuda` no .env quer saber que não deu — não quer o silêncio.

    É a diferença entre "a aula saiu ruim e não sei por quê" e uma mensagem.
    """
    monkeypatch.setattr(settings, "whisper_dispositivo", "cuda")
    with pytest.raises(RuntimeError, match="não está utilizável"):
        whisper.escolher()


def test_cpu_explicito_nem_consulta_a_gpu(monkeypatch):
    monkeypatch.setattr(settings, "whisper_dispositivo", "cpu")
    monkeypatch.setattr(
        whisper, "_tem_gpu", lambda: pytest.fail("não devia consultar a GPU")
    )
    assert whisper.escolher()[1] == "cpu"


# ── as flags da CLI ───────────────────────────────────────────────


def test_flags_mandam_mais_que_o_env(com_gpu, monkeypatch):
    """Medir `turbo` contra `large-v3` na mesma aula, sem editar o .env."""
    monkeypatch.setattr(settings, "whisper_dispositivo", "cuda")
    modelo, dispositivo, _ = whisper.escolher(modelo="medium", dispositivo="cpu")
    assert (modelo, dispositivo) == ("medium", "cpu")


def test_flag_de_modelo_nao_mexe_no_dispositivo(com_gpu, monkeypatch):
    monkeypatch.setattr(settings, "whisper_dispositivo", "auto")
    assert whisper.escolher(modelo="large-v3")[1] == "cuda"


# ── o preload das bibliotecas ─────────────────────────────────────


def test_sem_bibliotecas_na_venv_nao_promete_gpu(monkeypatch, tmp_path):
    """O `_preparar_cuda` é o que impede o erro tardio de `libcublas.so.12`.

    Sem os pacotes `nvidia-*` ele responde `False`, e a escolha cai para a CPU
    **antes** de o modelo carregar — em vez de quebrar na primeira inferência.
    """
    import sysconfig

    whisper._preparar_cuda.cache_clear()
    monkeypatch.setattr(
        sysconfig, "get_paths", lambda: {"purelib": str(tmp_path)}
    )
    try:
        assert whisper._preparar_cuda() is False
    finally:
        whisper._preparar_cuda.cache_clear()
