"""blog — editar o post depois de publicado

Duas colunas em `blog_post`:

- `atualizado`: a data que vai no frontmatter quando uma correção vai ao ar. O
  blog mostra "atualizado em …" e usa no `dateModified` do JSON-LD.
- `publicado_hash`: a assinatura do que está no ar. É o que permite dizer "há
  alterações não publicadas" sem perguntar ao GitHub a cada tela.

Revision ID: 0010_blog_atualizacao
Revises: 0009_blog_distribuicao
Create Date: 2026-09-23
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0010_blog_atualizacao"
down_revision: str | None = "0009_blog_distribuicao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("blog_post", sa.Column("atualizado", sa.Date(), nullable=True))
    op.add_column("blog_post", sa.Column("publicado_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("blog_post", "publicado_hash")
    op.drop_column("blog_post", "atualizado")
