"""Fixtures dos testes de navegador.

**Por que estes testes existem.** A suíte tinha 375 testes verdes enquanto o
painel apagava, a cada 15 segundos, o texto que eu estava digitando na fila — e
enquanto o botão "colar vaga" simplesmente não aparecia para quem tinha a aba
aberta desde antes do último deploy. Nenhum teste que não abre um navegador ia
pegar qualquer um dos dois. Ver `docs/fase06.md` §2 e §E1.

**Por que um servidor de verdade.** O resto da suíte fala com o app em processo
(`ASGITransport`), que é rápido e suficiente para contrato de API. Aqui não
serve: o que está sendo testado é o JavaScript rodando num navegador, e ele
precisa de um socket. Sobe-se um `uvicorn` apontado para o **banco de teste** —
os mesmos `TRUNCATE` por teste do `conftest.py` de cima valem, porque os dois
processos falam com o mesmo Postgres.

O navegador é de escopo de sessão (subir Chromium custa ~1 s); a página é por
teste, para não vazar estado de sessão entre um e outro.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_DIR = Path(__file__).resolve().parent.parent.parent

pytest.importorskip("playwright", reason="instale com: pip install -e '.[ui]'")

from playwright.async_api import async_playwright  # noqa: E402

# Todo teste deste diretório é `ui`: lento, precisa de navegador, e fica fora do
# `pytest` padrão (ver o `-m 'not ui'` no pyproject).
pytestmark = pytest.mark.ui


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor(banco_de_teste) -> str:
    """Um `uvicorn` de verdade contra o banco de teste. Devolve a URL base."""
    porta = _porta_livre()
    processo = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app",
         "--host", "127.0.0.1", "--port", str(porta), "--log-level", "warning"],
        cwd=REPO_DIR,
        # `os.environ` já vem com DATABASE_URL apontando para o banco de teste:
        # o conftest de cima o define no import, antes de `app.config` carregar.
        env={**os.environ, "SESSION_COOKIE_SECURE": "false"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{porta}"

    for _ in range(100):
        if processo.poll() is not None:
            erro = (processo.stderr.read() or b"").decode()[-2000:]
            raise RuntimeError(f"uvicorn morreu ao subir:\n{erro}")
        try:
            if httpx.get(f"{base}/api/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        processo.kill()
        raise RuntimeError("uvicorn não respondeu em 10 s")

    yield base

    processo.terminate()
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()


@pytest.fixture(scope="session")
async def navegador():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        yield b
        await b.close()


@pytest.fixture
async def pagina(navegador, servidor):
    """Uma aba limpa, com os erros de JS transformados em falha de teste.

    `erros_de_js` é o detalhe que faz estes testes valerem: uma exceção não
    tratada no painel não quebra nada visível, e sem isto passaria batida.
    """
    contexto = await navegador.new_context(viewport={"width": 1280, "height": 900})
    p = await contexto.new_page()
    p.erros_de_js = []
    p.on("pageerror", lambda e: p.erros_de_js.append(str(e)))
    p.on(
        "console",
        lambda m: p.erros_de_js.append(f"console.error: {m.text}")
        if m.type == "error" and "401" not in m.text
        else None,
    )
    yield p
    await contexto.close()


@pytest.fixture
async def painel(pagina, servidor, usuario):
    """Painel aberto e autenticado — o ponto de partida de quase todo teste."""
    u, senha = usuario
    await pagina.goto(servidor, wait_until="networkidle")
    await pagina.fill("#email", u.email)
    await pagina.fill("#senha", senha)
    await pagina.click("#form-login button")
    await pagina.wait_for_selector("#painel:not([hidden])", timeout=15_000)
    return pagina


@pytest.fixture
async def acao_na_fila():
    """Uma ação pendente com texto — sem passar pelo LLM.

    Gerar um currículo de verdade custaria ~60 s de inferência e traria o humor
    do modelo para dentro do teste. O que se testa aqui é a tela.
    """
    from app.fila import servico as fila

    async def criar(texto: str = "TEXTO ORIGINAL DO MODELO") -> str:
        acao = await fila.criar(
            agente="candidatura",
            tipo="curriculo",
            titulo="Currículo para Analista de Automação",
            texto_gerado=texto,
            contexto="vaga de teste",
            payload={},
        )
        return str(acao.id)

    return criar
