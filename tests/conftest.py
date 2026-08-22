"""Fixtures da suíte.

Os testes rodam contra um **Postgres de verdade** (banco `copiloto_test`),
migrado por `alembic upgrade head`. Não é SQLite nem mock: metade do que este
projeto faz é JSONB, schema `auth`, `timestamptz` e, em breve, pgvector — nada
disso existe em SQLite, e um teste que passa no fake mente sobre a produção.

Rodar a migration (em vez de `create_all`) faz a suíte validar de quebra que a
migration escrita à mão está completa.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parent.parent

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://copiloto:copiloto_dev@localhost:5434/copiloto_test",
)
# Precisa estar no ambiente ANTES de importar app.config (Settings lê no import).
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["SESSION_COOKIE_SECURE"] = "false"

TABELAS_DE_DADOS = (
    "auth.sessoes",
    "auth.tentativas_login",
    "auth.usuarios",
    "ai_calls",
    "pipeline_events",
    "agente_eventos",
    "candidatura_evento",
    "pessoal_candidatura_emails",
    "pessoal_vagas",
    "pessoal_perfil_mestre",
    "conhecimento_chunk",
    "exemplo_estilo",
    "acao_pendente",
    # Ordem importa: a limpeza é feita nesta sequência e o FK aponta para trás.
    "estudo_tentativa",
    "estudo_agenda",
    "estudo_questao",
    "estudo_topico",
    "estudo_modulo",
)


def _psql(sql: str, *, db: str = "postgres") -> None:
    subprocess.run(
        ["docker", "exec", "copiloto-db", "psql", "-U", "copiloto", "-d", db, "-c", sql],
        check=True,
        capture_output=True,
    )


def _expulsar(db: str) -> None:
    """Derruba as conexões abertas ao banco antes de dropá-lo.

    `DROP DATABASE` falha com uma única conexão viva, e a suíte de navegador
    deixa uma sempre que o `uvicorn` de teste morre sem fechar — um Ctrl-C, um
    timeout do pytest. O erro que chegava era `CalledProcessError: exit 1` no
    setup de **todos** os testes, que não diz nada sobre a causa.
    """
    _psql(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{db}' AND pid <> pg_backend_pid()"
    )


@pytest.fixture(scope="session", autouse=True)
def banco_de_teste():
    """Recria o banco de teste do zero e aplica a migration."""
    _expulsar("copiloto_test")
    _psql("DROP DATABASE IF EXISTS copiloto_test")
    _psql("CREATE DATABASE copiloto_test")

    env = {**os.environ, "ALEMBIC_DATABASE_URL": TEST_DB_URL}
    # Via `-m` para não depender do venv estar ativado no PATH.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_DIR,
        env=env,
        check=True,
        capture_output=True,
    )
    yield


@pytest.fixture(autouse=True)
async def limpar_tabelas():
    """Cada teste começa com o banco vazio (TRUNCATE é mais rápido que recriar).

    Com `lock_timeout` e retry por causa da suíte de navegador: o painel faz
    polling, e uma consulta em voo no `uvicorn` de teste ainda segura
    `AccessShareLock` quando o teste seguinte pede o `AccessExclusiveLock` do
    TRUNCATE. Sem o timeout isso vira `deadlock detected` — os dois esperando
    um pelo outro — e o teste morre por uma corrida que não é sobre ele.
    """
    import asyncio

    from sqlalchemy import text

    from app.db.session import get_session

    comando = text(f"TRUNCATE {', '.join(TABELAS_DE_DADOS)} RESTART IDENTITY CASCADE")
    for tentativa in range(5):
        try:
            async with get_session() as session:
                await session.execute(text("SET lock_timeout = '3s'"))
                await session.execute(comando)
                await session.commit()
            break
        except Exception:  # noqa: BLE001 — lock ou deadlock: espera e tenta de novo
            if tentativa == 4:
                raise
            await asyncio.sleep(0.5 * (tentativa + 1))
    yield


@pytest.fixture
async def client():
    """Cliente HTTP falando com o app em processo (sem subir servidor)."""
    from httpx import ASGITransport, AsyncClient

    from app.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
async def usuario():
    """Um usuário ativo com senha conhecida."""
    from app.api.services.auth import senha_service
    from app.db.models.auth.usuario import Usuario
    from app.db.session import get_session

    senha = "senha-de-teste-forte-2026"
    async with get_session() as session:
        u = Usuario(
            email="teste@copiloto.local",
            nome="Teste",
            senha_hash=senha_service.hash_senha(senha),
        )
        session.add(u)
        await session.commit()
        await session.refresh(u)
    return u, senha
