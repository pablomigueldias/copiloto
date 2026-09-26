"""A migration da prospecção desce e sobe de novo.

Num banco próprio, para não derrubar as tabelas que o resto da suíte está usando.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BANCO = "copiloto_test_migracao"
URL = os.environ["DATABASE_URL"].rsplit("/", 1)[0] + f"/{BANCO}"


def _psql(sql: str, db: str = "postgres") -> str:
    r = subprocess.run(
        ["docker", "exec", "copiloto-db", "psql", "-U", "copiloto", "-d", db, "-tAc", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip()


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO,
        env={**os.environ, "ALEMBIC_DATABASE_URL": URL},
        check=True,
        capture_output=True,
    )


def _tabelas() -> set[str]:
    saida = _psql("SELECT tablename FROM pg_tables WHERE tablename LIKE 'prospeccao_%'", BANCO)
    return set(saida.split())


def test_downgrade_remove_e_upgrade_recria():
    _psql(f"DROP DATABASE IF EXISTS {BANCO}")
    _psql(f"CREATE DATABASE {BANCO}")
    try:
        _alembic("upgrade", "head")
        assert len(_tabelas()) == 8
        assert _psql("SELECT count(*) FROM prospeccao_fonte", BANCO) == "2"

        _alembic("downgrade", "0010_blog_atualizacao")
        assert _tabelas() == set()

        _alembic("upgrade", "head")
        assert len(_tabelas()) == 8
    finally:
        _psql(f"DROP DATABASE IF EXISTS {BANCO}")
