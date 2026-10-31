"""estudo — o tópico também pausa, como a banca

A pausa por banca resolve trocar de concurso, e não resolve o que vem dentro
dele: a prova de Banco de Dados do Avança SP não cobra redes, programação nem
sistemas operacionais, mas essas questões são da mesma banca das de BD. Pausar
a banca tiraria as duas coisas da fila.

`estudo_topico.ativo` tem o mesmo contrato do `estudo_banca.ativa`: tira as
questões do tópico da fila do dia, do resumo e dos contadores, e não encosta em
questão, agenda nem tentativa. Retomar devolve no ponto em que parou.

Revision ID: 0016_topico_ativo
Revises: 0015_crm_empresa_contato
Create Date: 2026-10-02
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0016_topico_ativo"
down_revision: str | None = "0015_crm_empresa_contato"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "estudo_topico",
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("estudo_topico", "ativo")
