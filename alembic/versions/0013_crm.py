"""crm — o lead, a linha do tempo, as transições e as tarefas (Fase 1, passo 1)

Quatro tabelas `comercial_*`. O lead aponta para `prospeccao_estabelecimento`
com `ON DELETE SET NULL`: a base pode apagar o estabelecimento (retenção,
supressão) sem apagar a conversa que já aconteceu.

Plano: `docs/motor-comercial/fase-1/00-visao-geral.md`.

Revision ID: 0013_crm
Revises: 0012_pendencia
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_crm"
down_revision: str | None = "0012_pendencia"
branch_labels = None
depends_on = None


def _em(coluna: str, *valores: str) -> str:
    return f"{coluna} IN ({', '.join(repr(v) for v in valores)})"


def _agora() -> sa.Column:
    return sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "comercial_lead",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("origem", sa.String(12), nullable=False),
        sa.Column(
            "estabelecimento_id",
            sa.BigInteger(),
            sa.ForeignKey("prospeccao_estabelecimento.id", ondelete="SET NULL"),
        ),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("contato_nome", sa.Text()),
        sa.Column("cargo", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("telefone", sa.String(20)),
        sa.Column("site", sa.Text()),
        sa.Column("estagio", sa.String(12), nullable=False),
        sa.Column("proxima_acao", sa.Text()),
        sa.Column("proxima_em", sa.Date()),
        sa.Column("volta_em", sa.Date()),
        sa.Column("motivo_perda", sa.Text()),
        _agora(),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            _em("origem", "prospeccao", "whatsapp", "site", "indicacao", "newsletter"),
            name="ck_comercial_lead_origem",
        ),
        sa.CheckConstraint(
            _em(
                "estagio",
                "prospect", "contatado", "respondeu", "reuniao",
                "proposta", "ganho", "perdido", "nao_agora",
            ),
            name="ck_comercial_lead_estagio",
        ),
    )
    op.create_index("ix_comercial_lead_estagio", "comercial_lead", ["estagio", "proxima_em"])
    op.create_index("ix_comercial_lead_estabelecimento", "comercial_lead", ["estabelecimento_id"])

    op.create_table(
        "comercial_transicao",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.BigInteger(),
            sa.ForeignKey("comercial_lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("de", sa.String(12)),
        sa.Column("para", sa.String(12), nullable=False),
        sa.Column("motivo", sa.Text()),
        _agora(),
    )
    op.create_index("ix_comercial_transicao_lead_id", "comercial_transicao", ["lead_id"])

    op.create_table(
        "comercial_interacao",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.BigInteger(),
            sa.ForeignKey("comercial_lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("direcao", sa.String(8), nullable=False),
        sa.Column("tipo", sa.String(30)),
        sa.Column("texto", sa.Text()),
        sa.Column(
            "ai_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_calls.id", ondelete="SET NULL"),
        ),
        _agora(),
        sa.CheckConstraint(
            _em("canal", "email", "linkedin", "whatsapp", "reuniao", "nota"),
            name="ck_comercial_interacao_canal",
        ),
        sa.CheckConstraint(
            _em("direcao", "saida", "entrada", "interna"), name="ck_comercial_interacao_direcao"
        ),
    )
    op.create_index("ix_comercial_interacao_lead", "comercial_interacao", ["lead_id", "criado_em"])

    op.create_table(
        "comercial_tarefa",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "lead_id",
            sa.BigInteger(),
            sa.ForeignKey("comercial_lead.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(16), nullable=False),
        sa.Column("vence_em", sa.Date(), nullable=False),
        sa.Column("feita_em", sa.DateTime(timezone=True)),
        _agora(),
        sa.CheckConstraint(
            _em(
                "tipo",
                "pesquisar", "escrever_email", "enviar_email", "lembrete",
                "linkedin", "responder", "marcar_raiox",
            ),
            name="ck_comercial_tarefa_tipo",
        ),
    )
    op.create_index("ix_comercial_tarefa_lead_id", "comercial_tarefa", ["lead_id"])
    op.create_index(
        "ix_comercial_tarefa_aberta",
        "comercial_tarefa",
        ["vence_em"],
        postgresql_where=sa.text("feita_em IS NULL"),
    )


def downgrade() -> None:
    for tabela in ("comercial_tarefa", "comercial_interacao", "comercial_transicao", "comercial_lead"):
        op.drop_table(tabela)
