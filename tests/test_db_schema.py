"""O teste mais valioso da Fase 0.

A migration é escrita à mão. O jeito de isso não virar dívida silenciosa é
provar, a cada rodada, que o banco migrado tem exatamente as tabelas e colunas
que os modelos declaram. É o bug clássico de projeto com Alembic manual:
o modelo ganha uma coluna, a migration não, e só o deploy descobre.
"""
from sqlalchemy import text

from app.db import models  # noqa: F401 — registra os modelos no metadata
from app.db.base import Base
from app.db.session import get_session


async def _colunas_do_banco(session, schema: str, tabela: str) -> set[str]:
    res = await session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t"
        ),
        {"s": schema, "t": tabela},
    )
    return {r[0] for r in res}


async def test_migration_cria_todas_as_tabelas_dos_modelos():
    async with get_session() as session:
        for tabela in Base.metadata.tables.values():
            schema = tabela.schema or "public"
            do_banco = await _colunas_do_banco(session, schema, tabela.name)
            assert do_banco, f"tabela {schema}.{tabela.name} não existe no banco"

            do_modelo = {c.name for c in tabela.columns}
            assert do_modelo - do_banco == set(), (
                f"{schema}.{tabela.name}: colunas no modelo e não no banco: "
                f"{do_modelo - do_banco}"
            )
            assert do_banco - do_modelo == set(), (
                f"{schema}.{tabela.name}: colunas no banco e não no modelo: "
                f"{do_banco - do_modelo}"
            )


async def test_datas_sao_timestamptz():
    """`timestamp` sem fuso é o erro silencioso clássico do Postgres."""
    async with get_session() as session:
        res = await session.execute(
            text(
                "SELECT table_name, column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema IN ('public','auth') AND data_type LIKE 'timestamp%'"
            )
        )
        sem_fuso = [
            f"{t}.{c}" for t, c, tipo in res if tipo != "timestamp with time zone"
        ]
        assert not sem_fuso, f"colunas de data sem timezone: {sem_fuso}"


async def test_pgvector_habilitado():
    """A Fase 2 depende da extensão; falhar aqui é mais barato que lá."""
    async with get_session() as session:
        assert await session.scalar(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
