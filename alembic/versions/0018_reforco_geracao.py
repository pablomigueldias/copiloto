"""estudo — o reforço gerado pelo botão da tela

O reforço nascia esperando eu escrever as questões numa conversa. Agora a tela
tem um botão que dispara a escrita (Claude Code sem cabeça, com as ferramentas
travadas no gerador e no importador do reforço), e este é o estado desse
processo: gerando, erro com o motivo, ou ok.

Revision ID: 0018_reforco_geracao
Revises: 0017_simulado
Create Date: 2026-10-07
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0018_reforco_geracao"
down_revision: str | None = "0017_simulado"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estudo_reforco", sa.Column("geracao_estado", sa.String(10)))
    op.add_column("estudo_reforco", sa.Column("geracao_em", sa.DateTime(timezone=True)))
    op.add_column("estudo_reforco", sa.Column("geracao_pid", sa.Integer()))
    op.add_column("estudo_reforco", sa.Column("geracao_erro", sa.String(2000)))


def downgrade() -> None:
    for c in ("geracao_erro", "geracao_pid", "geracao_em", "geracao_estado"):
        op.drop_column("estudo_reforco", c)
