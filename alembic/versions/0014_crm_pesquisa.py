"""crm — o que o Pesquisador grava (Fase 1, passo 3)

- `comercial_lead.email_fonte`: a URL onde a própria clínica publica o e-mail.
  Nulo quer dizer "não confirmado", e e-mail não confirmado não vira
  destinatário (`regras-prospeccao.md` §4).
- `comercial_lead.pesquisado_em`: quando a ficha foi feita.
- `comercial_interacao.dados`: a ficha estruturada, cada fato com a fonte.

Revision ID: 0014_crm_pesquisa
Revises: 0013_crm
Create Date: 2026-09-27
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_crm_pesquisa"
down_revision: str | None = "0013_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("comercial_lead", sa.Column("email_fonte", sa.Text(), nullable=True))
    op.add_column("comercial_lead", sa.Column("pesquisado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column("comercial_interacao", sa.Column("dados", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("comercial_interacao", "dados")
    op.drop_column("comercial_lead", "pesquisado_em")
    op.drop_column("comercial_lead", "email_fonte")
