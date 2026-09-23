"""blog — a redação: o post antes de o git saber que ele existe

Duas tabelas. `blog_post` é o post inteiro (ideia, corpo, taxonomia do blog) e
`blog_post_versao` guarda o corpo de antes a cada mudança — autosave sem
histórico perde parágrafo, e perder parágrafo é o que faz não confiar no editor.

`slug` é único e **nulo até existir**: pauta nasce só com título, e um
`UNIQUE` em Postgres aceita vários nulos, que é exatamente o que se quer aqui.

Revision ID: 0007_blog
Revises: 0006_banca_e_imagem
Create Date: 2026-09-22
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_blog"
down_revision: str | None = "0006_banca_e_imagem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blog_post",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="pauta", nullable=False),
        sa.Column("pilar", sa.String(length=40), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("corpo", sa.Text(), server_default="", nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("origem", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("data_publicacao", sa.Date(), nullable=True),
        sa.Column("exportado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    # A consulta da lista: agrupada por estado, mexida mais recentemente no topo.
    op.create_index("ix_blog_post_estado", "blog_post", ["estado", "updated_at"])

    op.create_table(
        "blog_post_versao",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.Text(), nullable=False),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("palavras", sa.Integer(), server_default="0", nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["blog_post.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_blog_post_versao_numero", "blog_post_versao", ["post_id", "numero"], unique=True
    )
    op.create_index("ix_blog_post_versao_post", "blog_post_versao", ["post_id", "criada_em"])


def downgrade() -> None:
    op.drop_index("ix_blog_post_versao_post", table_name="blog_post_versao")
    op.drop_index("uq_blog_post_versao_numero", table_name="blog_post_versao")
    op.drop_table("blog_post_versao")
    op.drop_index("ix_blog_post_estado", table_name="blog_post")
    op.drop_table("blog_post")
