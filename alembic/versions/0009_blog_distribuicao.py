"""blog — o post do LinkedIn que sai de cada post publicado

Três colunas em `blog_post`: o texto do LinkedIn (gerado e depois editado por
mim), o dia em que ele vai ser postado e quando eu disse que postei — sem esse
último, o painel cobraria o mesmo post para sempre. Na linha do post e não em tabela
própria: é um texto por post, sem histórico que valha guardar — a versão que
importa é a que eu colei no LinkedIn.

Revision ID: 0009_blog_distribuicao
Revises: 0008_blog_publicacao
Create Date: 2026-09-23
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0009_blog_distribuicao"
down_revision: str | None = "0008_blog_publicacao"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("blog_post", sa.Column("linkedin_texto", sa.Text(), nullable=True))
    op.add_column("blog_post", sa.Column("linkedin_em", sa.Date(), nullable=True))
    op.add_column(
        "blog_post",
        sa.Column("linkedin_postado_em", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blog_post", "linkedin_postado_em")
    op.drop_column("blog_post", "linkedin_em")
    op.drop_column("blog_post", "linkedin_texto")
