"""crm — empresa e contato por trás do lead, que passa a ser o negócio

O lead juntava três coisas numa linha: a clínica, a pessoa e a conversa. Isso
bastou para o e-mail frio, e não basta para um CRM que eu opero todo dia: a
clínica tem mais de uma pessoa, e volta com um segundo negócio depois do "não
agora".

- `comercial_empresa`: a clínica. Aponta para `prospeccao_estabelecimento`
  (`SET NULL`, como o lead) e cada estabelecimento vira no máximo uma empresa.
- `comercial_contato`: a pessoa. `CASCADE` na empresa: contato é cadastro dela.
- `comercial_lead.empresa_id` / `contato_id`: `SET NULL`, a conversa fica.
- `comercial_lead.valor_estimado` e `notas`: o que o kanban de negócios soma.
- `comercial_tarefa.descricao` e os tipos `ligar`, `reuniao`, `outro`: a
  tarefa que eu crio à mão, fora da cadência.

Os leads que já existem ganham a empresa deles (uma por estabelecimento).

Revision ID: 0015_crm_empresa_contato
Revises: 0014_crm_pesquisa
Create Date: 2026-09-27
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0015_crm_empresa_contato"
down_revision: str | None = "0014_crm_pesquisa"
branch_labels = None
depends_on = None


_TIPOS_TAREFA = (
    "pesquisar", "escrever_email", "enviar_email", "lembrete",
    "linkedin", "responder", "marcar_raiox",
)
_TIPOS_MANUAIS = ("ligar", "reuniao", "outro")


def _check_tarefa(tipos: tuple[str, ...]) -> None:
    op.drop_constraint("ck_comercial_tarefa_tipo", "comercial_tarefa", type_="check")
    op.create_check_constraint(
        "ck_comercial_tarefa_tipo", "comercial_tarefa", f"tipo IN ({', '.join(repr(t) for t in tipos)})"
    )


def _datas() -> list[sa.Column]:
    return [
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "comercial_empresa",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("razao_social", sa.Text()),
        sa.Column("cnpj", sa.String(18)),
        sa.Column(
            "estabelecimento_id",
            sa.BigInteger(),
            sa.ForeignKey("prospeccao_estabelecimento.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="prospect"),
        sa.Column("segmento", sa.Text()),
        sa.Column("site", sa.Text()),
        sa.Column("email", sa.Text()),
        sa.Column("telefone", sa.String(20)),
        sa.Column("instagram", sa.Text()),
        sa.Column("bairro", sa.Text()),
        sa.Column("cidade", sa.Text()),
        sa.Column("uf", sa.String(2)),
        sa.Column("notas", sa.Text()),
        *_datas(),
        sa.CheckConstraint(
            "status IN ('prospect', 'cliente', 'parceiro', 'inativa')", name="ck_comercial_empresa_status"
        ),
    )
    op.create_index(
        "ux_comercial_empresa_estabelecimento",
        "comercial_empresa",
        ["estabelecimento_id"],
        unique=True,
        postgresql_where=sa.text("estabelecimento_id IS NOT NULL"),
    )

    op.create_table(
        "comercial_contato",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "empresa_id",
            sa.BigInteger(),
            sa.ForeignKey("comercial_empresa.id", ondelete="CASCADE"),
        ),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("cargo", sa.Text()),
        sa.Column("decisor", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email", sa.Text()),
        sa.Column("telefone", sa.String(20)),
        sa.Column("linkedin", sa.Text()),
        sa.Column("notas", sa.Text()),
        *_datas(),
    )
    op.create_index("ix_comercial_contato_empresa_id", "comercial_contato", ["empresa_id"])

    op.add_column(
        "comercial_lead",
        sa.Column("empresa_id", sa.BigInteger(), sa.ForeignKey("comercial_empresa.id", ondelete="SET NULL")),
    )
    op.add_column(
        "comercial_lead",
        sa.Column("contato_id", sa.BigInteger(), sa.ForeignKey("comercial_contato.id", ondelete="SET NULL")),
    )
    op.add_column("comercial_lead", sa.Column("valor_estimado", sa.Numeric(12, 2)))
    op.add_column("comercial_lead", sa.Column("notas", sa.Text()))
    op.create_index("ix_comercial_lead_empresa", "comercial_lead", ["empresa_id"])

    op.add_column("comercial_tarefa", sa.Column("descricao", sa.Text()))
    _check_tarefa(_TIPOS_TAREFA + _TIPOS_MANUAIS)

    # Cada lead que já existe ganha a empresa dele. Um estabelecimento com dois
    # leads (um perdido, um aberto) dá uma empresa só: é o `DISTINCT ON`.
    op.execute(
        """
        INSERT INTO comercial_empresa
            (nome, razao_social, estabelecimento_id, segmento, site, email, telefone, bairro, uf)
        SELECT DISTINCT ON (COALESCE(l.estabelecimento_id, -l.id))
               l.nome, e.razao_social, l.estabelecimento_id, e.segmento, l.site, l.email,
               l.telefone, e.bairro, e.uf
          FROM comercial_lead l
          LEFT JOIN prospeccao_estabelecimento e ON e.id = l.estabelecimento_id
         ORDER BY COALESCE(l.estabelecimento_id, -l.id), l.id
        """
    )
    op.execute(
        """
        UPDATE comercial_lead l SET empresa_id = emp.id
          FROM comercial_empresa emp
         WHERE emp.estabelecimento_id = l.estabelecimento_id
            OR (l.estabelecimento_id IS NULL AND emp.estabelecimento_id IS NULL AND emp.nome = l.nome)
        """
    )
    # A pessoa que o lead já tinha vira o contato dele.
    op.execute(
        """
        WITH novos AS (
            INSERT INTO comercial_contato (empresa_id, nome, cargo, email, telefone)
            SELECT l.empresa_id, l.contato_nome, l.cargo, l.email, l.telefone
              FROM comercial_lead l
             WHERE l.contato_nome IS NOT NULL
            RETURNING id, empresa_id, nome
        )
        UPDATE comercial_lead l SET contato_id = novos.id
          FROM novos
         WHERE novos.empresa_id IS NOT DISTINCT FROM l.empresa_id AND novos.nome = l.contato_nome
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM comercial_tarefa WHERE tipo IN ({', '.join(repr(t) for t in _TIPOS_MANUAIS)})")
    _check_tarefa(_TIPOS_TAREFA)
    op.drop_column("comercial_tarefa", "descricao")
    op.drop_index("ix_comercial_lead_empresa", table_name="comercial_lead")
    for coluna in ("notas", "valor_estimado", "contato_id", "empresa_id"):
        op.drop_column("comercial_lead", coluna)
    op.drop_table("comercial_contato")
    op.drop_table("comercial_empresa")
