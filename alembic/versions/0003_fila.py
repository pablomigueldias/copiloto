"""acao_pendente e exemplo_estilo — a fila de aprovação e o dataset

Duas tabelas que só fazem sentido juntas: a fila é onde eu decido, e a decisão
é o que produz o material da camada 2 (few-shot) e da F9 (fine-tune). Sem elas,
o uso normal do sistema não deixa dataset nenhum.

`exemplo_estilo.acao_id` é ON DELETE SET NULL de propósito: apagar uma ação não
pode levar junto um exemplo já aprovado.

Revision ID: 0003_fila
Revises: 0002_conhecimento
Create Date: 2026-08-15
"""
from __future__ import annotations

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_fila"
down_revision: str | None = "0002_conhecimento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acao_pendente",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agente", sa.String(length=50), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("contexto", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default="pendente", nullable=False
        ),
        sa.Column("texto_gerado", sa.Text(), nullable=True),
        sa.Column("texto_final", sa.Text(), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("ai_call_id", sa.UUID(), nullable=True),
        sa.Column("alvo_ref", sa.String(length=120), nullable=True),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decidida_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ai_call_id"], ["ai_calls.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_acao_pendente_status_criada", "acao_pendente", ["status", "criada_em"]
    )
    op.create_index("ix_acao_pendente_agente_tipo", "acao_pendente", ["agente", "tipo"])
    op.create_index("ix_acao_pendente_alvo_ref", "acao_pendente", ["alvo_ref"])

    op.create_table(
        "exemplo_estilo",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tarefa", sa.String(length=50), nullable=False),
        sa.Column("contexto", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1024), nullable=True),
        sa.Column("acao_id", sa.UUID(), nullable=True),
        sa.Column(
            "aprovado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["acao_id"], ["acao_pendente.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exemplo_estilo_embedding",
        "exemplo_estilo",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_exemplo_estilo_tarefa", "exemplo_estilo", ["tarefa"])


def downgrade() -> None:
    op.drop_index("ix_exemplo_estilo_tarefa", table_name="exemplo_estilo")
    op.drop_index("ix_exemplo_estilo_embedding", table_name="exemplo_estilo")
    op.drop_table("exemplo_estilo")
    op.drop_index("ix_acao_pendente_alvo_ref", table_name="acao_pendente")
    op.drop_index("ix_acao_pendente_agente_tipo", table_name="acao_pendente")
    op.drop_index("ix_acao_pendente_status_criada", table_name="acao_pendente")
    op.drop_table("acao_pendente")
