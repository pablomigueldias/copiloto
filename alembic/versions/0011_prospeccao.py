"""prospeccao — base de prospecção atômica, com proveniência e supressão (D9)

Oito tabelas, uma por tipo de fato: fonte, importação, estabelecimento,
identificador (CNES/CNPJ), atividade (CNAE), canal (telefone, e-mail, site),
origem (de onde veio cada linha) e supressão (quem pediu para sair, só o hash).
Especificação: `docs/motor-comercial/fase-0/base-prospeccao.md`.

As duas fontes aprovadas no 1.2.6 entram já cadastradas: CNES e a base aberta do
CNPJ, as duas CC-BY no dados.gov.br.

Revision ID: 0011_prospeccao
Revises: 0010_blog_atualizacao
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_prospeccao"
down_revision: str | None = "0010_blog_atualizacao"
branch_labels = None
depends_on = None

AGORA = sa.text("now()")


def _em(coluna: str, *valores: str) -> str:
    return f"{coluna} IN ({', '.join(repr(v) for v in valores)})"


def upgrade() -> None:
    op.create_table(
        "prospeccao_fonte",
        sa.Column("id", sa.SmallInteger(), sa.Identity(), primary_key=True),
        sa.Column("codigo", sa.String(40), nullable=False, unique=True),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("licenca", sa.Text(), nullable=False),
        sa.Column("observacao", sa.Text()),
    )

    op.create_table(
        "prospeccao_importacao",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("fonte_id", sa.SmallInteger(), sa.ForeignKey("prospeccao_fonte.id"), nullable=False),
        sa.Column("parametros", postgresql.JSONB(), nullable=False),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True)),
        sa.Column("lidos", sa.Integer(), nullable=False),
        sa.Column("inseridos", sa.Integer(), nullable=False),
        sa.Column("atualizados", sa.Integer(), nullable=False),
        sa.Column("sem_mudanca", sa.Integer(), nullable=False),
        sa.Column("marcados_inativos", sa.Integer(), nullable=False),
        sa.Column("suprimidos", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("erro", sa.Text()),
        sa.CheckConstraint(_em("status", "rodando", "ok", "falhou"), name="ck_prospeccao_importacao_status"),
    )

    op.create_table(
        "prospeccao_estabelecimento",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("nicho", sa.String(20), nullable=False),
        sa.Column("segmento", sa.String(40)),
        sa.Column("nome_fantasia", sa.Text()),
        sa.Column("razao_social", sa.Text()),
        sa.Column("pessoa_fisica", sa.Boolean(), nullable=False),
        sa.Column("situacao", sa.String(10), nullable=False),
        sa.Column("atende_sus", sa.Boolean()),
        sa.Column("municipio_ibge", sa.String(7)),
        sa.Column("uf", sa.String(2)),
        sa.Column("bairro", sa.Text()),
        sa.Column("cep", sa.String(8)),
        sa.Column("logradouro", sa.Text()),
        sa.Column("numero", sa.String(20)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("inativo_desde", sa.DateTime(timezone=True)),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.CheckConstraint(
            _em("nicho", "clinica", "advocacia", "imobiliaria"), name="ck_prospeccao_estabelecimento_nicho"
        ),
        sa.CheckConstraint(_em("situacao", "ativo", "inativo"), name="ck_prospeccao_estabelecimento_situacao"),
    )
    op.create_index(
        "ix_prospeccao_estabelecimento_busca",
        "prospeccao_estabelecimento",
        ["nicho", "situacao", "municipio_ibge"],
    )

    op.create_table(
        "prospeccao_identificador",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "estabelecimento_id",
            sa.BigInteger(),
            sa.ForeignKey("prospeccao_estabelecimento.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor", sa.String(20), nullable=False),
        sa.UniqueConstraint("tipo", "valor", name="ux_prospeccao_identificador_tipo_valor"),
        sa.CheckConstraint(_em("tipo", "cnes", "cnpj"), name="ck_prospeccao_identificador_tipo"),
    )
    op.create_index(
        "ix_prospeccao_identificador_estabelecimento_id", "prospeccao_identificador", ["estabelecimento_id"]
    )

    op.create_table(
        "prospeccao_atividade",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "estabelecimento_id",
            sa.BigInteger(),
            sa.ForeignKey("prospeccao_estabelecimento.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("cnae_subclasse", sa.String(7), nullable=False),
        sa.Column("principal", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("estabelecimento_id", "cnae_subclasse", name="ux_prospeccao_atividade"),
        sa.CheckConstraint("cnae_subclasse ~ '^[0-9]{7}$'", name="ck_prospeccao_atividade_cnae"),
    )

    op.create_table(
        "prospeccao_canal",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "estabelecimento_id",
            sa.BigInteger(),
            sa.ForeignKey("prospeccao_estabelecimento.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("valor_original", sa.Text(), nullable=False),
        sa.Column("valido", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("estabelecimento_id", "tipo", "valor", name="ux_prospeccao_canal"),
        sa.CheckConstraint(_em("tipo", "telefone", "celular", "email", "site"), name="ck_prospeccao_canal_tipo"),
    )

    op.create_table(
        "prospeccao_origem",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("entidade", sa.String(20), nullable=False),
        sa.Column("entidade_id", sa.BigInteger(), nullable=False),
        sa.Column("fonte_id", sa.SmallInteger(), sa.ForeignKey("prospeccao_fonte.id"), nullable=False),
        sa.Column("id_na_fonte", sa.String(20), nullable=False),
        sa.Column(
            "primeira_importacao_id", sa.BigInteger(), sa.ForeignKey("prospeccao_importacao.id"), nullable=False
        ),
        sa.Column(
            "ultima_importacao_id", sa.BigInteger(), sa.ForeignKey("prospeccao_importacao.id"), nullable=False
        ),
        sa.Column("visto_primeiro_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.Column("visto_ultimo_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.Column("hash_payload", sa.String(64)),
        sa.UniqueConstraint("entidade", "entidade_id", "fonte_id", name="ux_prospeccao_origem"),
        sa.CheckConstraint(
            _em("entidade", "estabelecimento", "canal", "atividade", "identificador"),
            name="ck_prospeccao_origem_entidade",
        ),
    )

    op.create_table(
        "prospeccao_supressao",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("valor_hash", sa.String(64), nullable=False),
        sa.Column("motivo", sa.String(20), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=AGORA, nullable=False),
        sa.UniqueConstraint("tipo", "valor_hash", name="ux_prospeccao_supressao"),
        sa.CheckConstraint(_em("tipo", "telefone", "email", "cnpj", "cnes"), name="ck_prospeccao_supressao_tipo"),
        sa.CheckConstraint(
            _em("motivo", "optout", "pedido_titular", "erro", "nao_e_alvo"), name="ck_prospeccao_supressao_motivo"
        ),
    )

    fonte = sa.table(
        "prospeccao_fonte",
        sa.column("codigo", sa.String),
        sa.column("nome", sa.Text),
        sa.column("url", sa.Text),
        sa.column("licenca", sa.Text),
        sa.column("observacao", sa.Text),
    )
    op.bulk_insert(
        fonte,
        [
            {
                "codigo": "cnes",
                "nome": "CNES — Cadastro Nacional de Estabelecimentos de Saúde (Ministério da Saúde)",
                "url": "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos",
                "licenca": "CC-BY (dados.gov.br, conferido em 2026-09-25)",
                "observacao": "máx. 20 registros por página; não informa o total",
            },
            {
                "codigo": "receita_cnpj",
                "nome": "Dados abertos do CNPJ (Receita Federal)",
                "url": "https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9",
                "licenca": "CC-BY (dados.gov.br, conferido em 2026-09-25)",
                "observacao": "arquivos mensais, ~5 GB de estabelecimentos; CPF no nome de empresário individual (1.2.6 §3)",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("prospeccao_supressao")
    op.drop_table("prospeccao_origem")
    op.drop_table("prospeccao_canal")
    op.drop_table("prospeccao_atividade")
    op.drop_index("ix_prospeccao_identificador_estabelecimento_id", table_name="prospeccao_identificador")
    op.drop_table("prospeccao_identificador")
    op.drop_index("ix_prospeccao_estabelecimento_busca", table_name="prospeccao_estabelecimento")
    op.drop_table("prospeccao_estabelecimento")
    op.drop_table("prospeccao_importacao")
    op.drop_table("prospeccao_fonte")
