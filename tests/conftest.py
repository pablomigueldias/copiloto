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


@pytest.fixture(scope="session", autouse=True)
def banco_de_teste():
    """Recria o banco de teste do zero e aplica a migration."""
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
    """Cada teste começa com o banco vazio (TRUNCATE é mais rápido que recriar)."""
    from sqlalchemy import text

    from app.db.session import get_session

    async with get_session() as session:
        await session.execute(
            text(f"TRUNCATE {', '.join(TABELAS_DE_DADOS)} RESTART IDENTITY CASCADE")
        )
        await session.commit()
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
