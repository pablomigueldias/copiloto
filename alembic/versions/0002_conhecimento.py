"""conhecimento_chunk — o índice do que o sistema sabe

A extensão `vector` já foi criada na 0001 (é infra e exige superusuário); aqui
só entra a tabela.

Três índices, cada um com um trabalho:
  - HNSW sobre `embedding` (cosseno)  → a metade semântica da busca
  - GIN sobre `tsv`                   → a metade lexical (sigla, nome próprio)
  - único (fonte_tipo, fonte_ref, ordem) → reindexar um arquivo sem tocar no resto

Revision ID: 0002_conhecimento
Revises: 0001_base
Create Date: 2026-08-14
"""
from __future__ import annotations

import pgvector.sqlalchemy
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_conhecimento"
down_revision: str | None = "0001_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conhecimento_chunk",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("fonte_tipo", sa.String(length=30), nullable=False),
        sa.Column("fonte_ref", sa.Text(), nullable=False),
        sa.Column("fonte_hash", sa.String(length=64), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=True),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=1024), nullable=True),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('portuguese', coalesce(titulo,'') || ' ' || conteudo)",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("metadados", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conhecimento_chunk_embedding",
        "conhecimento_chunk",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_conhecimento_chunk_tsv", "conhecimento_chunk", ["tsv"], postgresql_using="gin"
    )
    op.create_index(
        "uq_conhecimento_chunk_fonte_ordem",
        "conhecimento_chunk",
        ["fonte_tipo", "fonte_ref", "ordem"],
        unique=True,
    )
    op.create_index("ix_conhecimento_chunk_fonte_hash", "conhecimento_chunk", ["fonte_hash"])
    op.create_index("ix_conhecimento_chunk_fonte_tipo", "conhecimento_chunk", ["fonte_tipo"])


def downgrade() -> None:
    op.drop_index("ix_conhecimento_chunk_fonte_tipo", table_name="conhecimento_chunk")
    op.drop_index("ix_conhecimento_chunk_fonte_hash", table_name="conhecimento_chunk")
    op.drop_index("uq_conhecimento_chunk_fonte_ordem", table_name="conhecimento_chunk")
    op.drop_index("ix_conhecimento_chunk_tsv", table_name="conhecimento_chunk")
    op.drop_index("ix_conhecimento_chunk_embedding", table_name="conhecimento_chunk")
    op.drop_table("conhecimento_chunk")
