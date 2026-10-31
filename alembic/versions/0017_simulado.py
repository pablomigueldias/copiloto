"""estudo — o simulado da prova e o reforço por assunto

A revisão espaçada sozinha não estava dizendo o que estudar. O simulado monta a
prova no quadro do edital (PT 10, MAT 10, Inglês 10, Específicos 30), dá a nota
pela fórmula do edital e transforma cada assunto errado num reforço de 5
questões, que precisa de 75% para liberar o simulado seguinte.

`estudo_questao.assunto` é o rótulo fino ("Triggers", "Crase") que põe a
questão no simulado e nomeia o erro. Nulo = fora do simulado.

Revision ID: 0017_simulado
Revises: 0016_topico_ativo
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_simulado"
down_revision: str | None = "0016_topico_ativo"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
PK = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.add_column("estudo_questao", sa.Column("assunto", sa.String(160), nullable=True))
    op.create_index("ix_estudo_questao_assunto", "estudo_questao", ["assunto"])

    op.create_table(
        "estudo_simulado",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("numero", sa.Integer(), nullable=False, unique=True),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finalizado_em", sa.DateTime(timezone=True)),
        sa.Column("acertos", sa.Integer()),
        sa.Column("total", sa.Integer()),
        sa.Column("nota", sa.Numeric(5, 2)),
    )
    op.create_table(
        "estudo_simulado_item",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("simulado_id", UUID, sa.ForeignKey("estudo_simulado.id", ondelete="CASCADE"), nullable=False),
        sa.Column("questao_id", UUID, sa.ForeignKey("estudo_questao.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("materia", sa.String(10), nullable=False),
        sa.Column("assunto", sa.String(160), nullable=False),
        sa.Column("revisao", sa.Boolean(), nullable=False),
        sa.Column("resposta", sa.String(1)),
        sa.Column("respondida_em", sa.DateTime(timezone=True)),
        sa.Column("acertou", sa.Boolean()),
    )
    op.create_index("ux_estudo_simulado_item_ordem", "estudo_simulado_item", ["simulado_id", "ordem"], unique=True)
    op.create_index("ix_estudo_simulado_item_questao", "estudo_simulado_item", ["questao_id"])

    op.create_table(
        "estudo_reforco",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("simulado_id", UUID, sa.ForeignKey("estudo_simulado.id", ondelete="CASCADE"), nullable=False),
        sa.Column("materia", sa.String(10), nullable=False),
        sa.Column("assunto", sa.String(160), nullable=False),
        sa.Column("rodada", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(24), nullable=False),
        sa.Column("erros_no_simulado", sa.Integer(), nullable=False),
        sa.Column("acertos", sa.Integer()),
        sa.Column("total", sa.Integer()),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True)),
    )
    op.create_index("ux_estudo_reforco_rodada", "estudo_reforco", ["simulado_id", "assunto", "rodada"], unique=True)
    op.create_index("ix_estudo_reforco_estado", "estudo_reforco", ["estado"])

    op.create_table(
        "estudo_reforco_item",
        sa.Column("id", UUID, primary_key=True, server_default=PK),
        sa.Column("reforco_id", UUID, sa.ForeignKey("estudo_reforco.id", ondelete="CASCADE"), nullable=False),
        sa.Column("questao_id", UUID, sa.ForeignKey("estudo_questao.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("resposta", sa.String(1)),
        sa.Column("acertou", sa.Boolean()),
        sa.Column("respondida_em", sa.DateTime(timezone=True)),
    )
    op.create_index("ux_estudo_reforco_item_ordem", "estudo_reforco_item", ["reforco_id", "ordem"], unique=True)


def downgrade() -> None:
    op.drop_table("estudo_reforco_item")
    op.drop_table("estudo_reforco")
    op.drop_table("estudo_simulado_item")
    op.drop_table("estudo_simulado")
    op.drop_index("ix_estudo_questao_assunto", table_name="estudo_questao")
    op.drop_column("estudo_questao", "assunto")
