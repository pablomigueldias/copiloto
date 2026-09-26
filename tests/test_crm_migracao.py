"""A migration do CRM desce e sobe de novo, num banco próprio.

Mesmo desenho do teste da prospecção: banco separado, para não derrubar as
tabelas que o resto da suíte está usando.
"""
from __future__ import annotations

from tests.test_prospeccao_migracao import BANCO, _alembic, _psql


def _tabelas() -> set[str]:
    saida = _psql("SELECT tablename FROM pg_tables WHERE tablename LIKE 'comercial_%'", BANCO)
    return set(saida.split())


def test_downgrade_remove_e_upgrade_recria():
    _psql(f"DROP DATABASE IF EXISTS {BANCO}")
    _psql(f"CREATE DATABASE {BANCO}")
    try:
        _alembic("upgrade", "head")
        assert _tabelas() == {
            "comercial_lead",
            "comercial_transicao",
            "comercial_interacao",
            "comercial_tarefa",
        }
        _alembic("downgrade", "0012_pendencia")
        assert _tabelas() == set()
        assert _psql("SELECT count(*) FROM prospeccao_fonte", BANCO) == "2"  # a base fica
        _alembic("upgrade", "head")
        assert len(_tabelas()) == 4
    finally:
        _psql(f"DROP DATABASE IF EXISTS {BANCO}")
