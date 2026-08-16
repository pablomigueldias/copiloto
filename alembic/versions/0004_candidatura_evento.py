"""candidatura_evento — o histórico de cada candidatura

`pessoal_vagas.status` diz onde a candidatura está; esta tabela diz quanto tempo
levou para chegar lá e quantas viraram entrevista. Métrica sem histórico é foto,
e o que interessa é o filme.

Revision ID: 0004_candidatura_evento
Revises: 0003_fila
Create Date: 2026-08-16
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0004_candidatura_evento"
down_revision: str | None = "0003_fila"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidatura_evento",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("vaga_id", sa.UUID(), nullable=False),
        sa.Column("evento", sa.String(length=30), nullable=False),
        sa.Column("detalhe", sa.Text(), nullable=True),
        sa.Column(
            "ocorreu_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vaga_id"], ["pessoal_vagas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidatura_evento_vaga", "candidatura_evento", ["vaga_id", "ocorreu_em"])
    op.create_index("ix_candidatura_evento_evento", "candidatura_evento", ["evento"])


def downgrade() -> None:
    op.drop_index("ix_candidatura_evento_evento", table_name="candidatura_evento")
    op.drop_index("ix_candidatura_evento_vaga", table_name="candidatura_evento")
    op.drop_table("candidatura_evento")
