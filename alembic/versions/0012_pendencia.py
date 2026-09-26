"""pendência — o quadro de pendências do Pablo

Uma tabela: cada linha é um cartão de `/pendencias`, com tópico, o gatilho
(`quando`, texto livre) e, quando houver, um `prazo` de verdade. As pendências
que moravam em `docs/PENDENCIAS.md` entram por `scripts/importar_pendencias.py`.

Revision ID: 0012_pendencia
Revises: 0011_prospeccao
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_pendencia"
down_revision: str | None = "0011_prospeccao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pendencia",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("topico", sa.String(length=80), nullable=False),
        sa.Column("quando", sa.String(length=160), nullable=True),
        sa.Column("prazo", sa.Date(), nullable=True),
        sa.Column("onde", sa.Text(), nullable=True),
        sa.Column("coluna", sa.String(length=20), server_default="a_fazer", nullable=False),
        sa.Column("ordem", sa.Integer(), server_default="0", nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "coluna IN ('a_fazer', 'fazendo', 'feito')", name="ck_pendencia_coluna"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pendencia_coluna_ordem", "pendencia", ["coluna", "ordem"])
    op.create_index("ix_pendencia_topico", "pendencia", ["topico"])


def downgrade() -> None:
    op.drop_index("ix_pendencia_topico", table_name="pendencia")
    op.drop_index("ix_pendencia_coluna_ordem", table_name="pendencia")
    op.drop_table("pendencia")
