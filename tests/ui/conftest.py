"""Fixtures dos testes de navegador.

**Por que estes testes existem.** A suíte tinha 375 testes verdes enquanto o
painel apagava, a cada 15 segundos, o texto que eu estava digitando na fila — e
enquanto o botão "colar vaga" simplesmente não aparecia para quem tinha a aba
aberta desde antes do último deploy. Nenhum teste que não abre um navegador ia
pegar qualquer um dos dois. Ver `docs/fase06.md` §2 e §E1.

**Por que dois processos agora.** O painel deixou de ser HTML servido pelo
próprio FastAPI e virou um app Next.js em `web/`. Então a sessão sobe os dois:
um `uvicorn` contra o **banco de teste** e um `next dev` apontado para ele pelo
`API_URL`. O navegador fala só com o Next — mesma origem, como em produção, que
é o que faz o cookie de sessão viajar.

Os `TRUNCATE` por teste do `conftest.py` de cima continuam valendo: os três
processos falam com o mesmo Postgres.

O navegador e os dois servidores são de escopo de sessão (o Next custa alguns
segundos para compilar a primeira rota); a página é por teste, para não vazar
estado de sessão entre um e outro.
"""
from __future__ import annotations

import os
import shutil
import signal
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

# O marcador separa esta suíte da de sempre: `-m "not ui"` roda os testes de
# unidade sem abrir navegador nenhum — é o `addopts` do pyproject.
pytestmark = pytest.mark.ui


def _matar(processo: subprocess.Popen, *, prazo: int) -> None:
    """O grupo inteiro, não só o processo.

    `npm run dev` gera um `next-server` filho; matar só o pai deixa o filho
    segurando a porta — e o lockfile que faz a rodada seguinte recusar-se a
    subir com "Another next dev server is already running".
    """
    try:
        os.killpg(os.getpgid(processo.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        processo.terminate()
    try:
        processo.wait(timeout=prazo)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(processo.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            processo.kill()


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def api(banco_de_teste) -> str:
    """Um `uvicorn` de verdade contra o banco de teste. Devolve a URL base."""
    porta = _porta_livre()
    processo = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app",
         "--host", "127.0.0.1", "--port", str(porta), "--log-level", "warning"],
        cwd=REPO_DIR,
        # A suíte fala HTTP puro: um cookie `Secure` seria emitido e nunca
        # guardado, e o login falharia sem dizer por quê.
        env={**os.environ, "SESSION_COOKIE_SECURE": "false"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
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

    _matar(processo, prazo=5)


@pytest.fixture(scope="session")
def servidor(api) -> str:
    """O `next dev`, apontado para a API de teste. É o que o navegador abre.

    `API_URL` é lido pelo `next.config.ts` no boot e vira a reescrita de
    `/api/*` — por isso o Next precisa subir **depois** do uvicorn, com a porta
    dele já conhecida.

    Modo dev e não `next build`: o build leva ~30 s e a suíte inteira leva
    menos que isso. O preço é a primeira visita a cada rota compilar sob
    demanda, e é por isso que os `wait_for_selector` daqui usam timeouts
    generosos.
    """
    web = REPO_DIR / "web"
    if not (web / "node_modules").is_dir():
        pytest.skip("web/node_modules ausente — rode `npm install` em web/")

    # Cache de compilação de uma rodada anterior serve página velha para a nova.
    shutil.rmtree(web / ".next-teste" / "dev", ignore_errors=True)

    porta = _porta_livre()
    processo = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(porta)],
        cwd=web,
        env={
            **os.environ,
            "API_URL": api,
            "NEXT_TELEMETRY_DISABLED": "1",
            # Diretório de build próprio: o Next 16 recusa um segundo servidor
            # sobre o mesmo `.next`, e eu deixo um `next dev` aberto enquanto
            # trabalho.
            "NEXT_DIST_DIR": ".next-teste",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    base = f"http://127.0.0.1:{porta}"

    for _ in range(300):
        if processo.poll() is not None:
            erro = (processo.stderr.read() or b"").decode()[-2000:]
            raise RuntimeError(f"next morreu ao subir:\n{erro}")
        try:
            if httpx.get(f"{base}/login", timeout=1.0).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        processo.kill()
        raise RuntimeError("next não respondeu em 60 s")

    yield base

    _matar(processo, prazo=10)


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
    await pagina.goto(f"{servidor}/login", wait_until="domcontentloaded")
    # `data-pronto` marca o fim da hidratação: antes dele, o React troca o HTML.
    await pagina.wait_for_selector("html[data-pronto]", timeout=60000)
    await pagina.fill("#email", u.email)
    await pagina.fill("#senha", senha)
    await pagina.click('button[type="submit"]')

    try:
        await pagina.wait_for_selector("aside nav", timeout=60000)
    except Exception:
        corpo = await pagina.inner_text("body")
        raise AssertionError(
            "login não abriu o painel.\n"
            f"url: {pagina.url}\n"
            f"tela: {corpo[:600]}\n"
            f"js: {pagina.erros_de_js}"
        ) from None
    return pagina


async def _ir_para(pagina, rotulo: str, marca: str):
    """Navega **pelo menu**, não pela URL.

    Assim o teste prova de graça que o link existe e que a sessão atravessa a
    navegação — a parte que quebraria se o cookie fosse por página.
    """
    await pagina.click(f'aside nav a:has-text("{rotulo}")')
    await pagina.wait_for_selector(marca, timeout=60000)
    return pagina


@pytest.fixture
async def candidaturas(painel):
    return await _ir_para(painel, "Candidaturas", 'h1:has-text("O que foi enviado")')


@pytest.fixture
async def fila(painel):
    return await _ir_para(painel, "Fila", 'h1:has-text("O que espera decisão")')


@pytest.fixture
async def modulos(painel):
    return await _ir_para(painel, "Módulos", 'h1:has-text("Módulos")')


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


@pytest.fixture
async def com_curriculo():
    """Grava um `curriculo_json` numa vaga, sem passar pelo LLM.

    Gerar de verdade custaria ~60 s de inferência e traria o humor do modelo
    para dentro do teste — a mesma razão do `acao_na_fila`. O que se testa aqui
    é o editor da gaveta, e ele só precisa que exista currículo.
    """
    from datetime import UTC, datetime
    from uuid import UUID

    from app.db.models.pessoal.perfil_mestre import PerfilMestre
    from app.db.models.pessoal.vaga import Vaga
    from app.db.session import get_session

    async def gravar(vaga_id: str) -> None:
        async with get_session() as s:
            s.add(
                PerfilMestre(
                    nome="Pablo",
                    resumo="Dev Python.",
                    contato={"localizacao": "Santo André, SP", "email": "p@x.dev"},
                    habilidades=[{"nome": "Python"}],
                    projetos=[],
                    experiencias=[],
                )
            )
            alvo = await s.get(Vaga, UUID(vaga_id))
            alvo.curriculo_json = {
                "titulo": "Desenvolvedor Python",
                "resumo": "RESUMO ORIGINAL DO MODELO.",
                "competencias": [{"categoria": "Backend", "itens": ["Python"]}],
                "experiencias": [],
                "projetos": [],
                "formacao": [],
                "certificacoes": [],
                "rejeitados": [],
                "avisos": [],
            }
            alvo.curriculo_gerado_em = datetime.now(UTC)
            await s.commit()

    return gravar
