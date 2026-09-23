"""blog — o PR e a publicação do post

Quatro colunas em `blog_post`. O que elas guardam é o rastro do caminho entre
"pronto" e "no ar": a branch criada, o PR aberto e a hora em que ele entrou na
`main`.

Guardar em vez de perguntar ao GitHub a cada tela não é cache por preguiça: a
lista da redação precisa saber "este já foi?" sem gastar uma chamada de API por
card, e o número do PR continua ligando o post ao histórico do repo depois que
a branch é apagada no merge.

Revision ID: 0008_blog_publicacao
Revises: 0007_blog
Create Date: 2026-09-22
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0008_blog_publicacao"
down_revision: str | None = "0007_blog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("blog_post", sa.Column("pr_numero", sa.Integer(), nullable=True))
    op.add_column("blog_post", sa.Column("pr_url", sa.Text(), nullable=True))
    op.add_column("blog_post", sa.Column("branch", sa.String(length=160), nullable=True))
    op.add_column(
        "blog_post", sa.Column("publicado_em", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("blog_post", "publicado_em")
    op.drop_column("blog_post", "branch")
    op.drop_column("blog_post", "pr_url")
    op.drop_column("blog_post", "pr_numero")
