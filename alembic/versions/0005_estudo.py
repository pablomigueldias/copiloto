"""estudo — questões de prova, agendamento e histórico de respostas

Cinco tabelas. A divisão que importa é entre `estudo_questao` (o conteúdo, que
vem de PDF e vai ser re-importado) e `estudo_agenda` + `estudo_tentativa` (o meu
desempenho, que não pode se perder num re-import).

`estudo_tentativa` guarda a data e o acerto de cada resposta, e é dela que sai
a recomendação: questão errada volta em dois dias, questão acertada volta em
sete e o intervalo cresce.

Revision ID: 0005_estudo
Revises: 0004_candidatura_evento
Create Date: 2026-08-21
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0005_estudo"
down_revision: str | None = "0004_candidatura_evento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estudo_modulo",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("trilha", sa.String(length=40), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome"),
    )

    op.create_table(
        "estudo_topico",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("modulo_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["modulo_id"], ["estudo_modulo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_estudo_topico_modulo_nome", "estudo_topico", ["modulo_id", "nome"], unique=True
    )

    op.create_table(
        "estudo_questao",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("topico_id", sa.UUID(), nullable=False),
        sa.Column("formato", sa.String(length=30), nullable=False),
        sa.Column("comando", sa.Text(), nullable=True),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column("texto_base", sa.Text(), nullable=True),
        sa.Column("texto_base_fonte", sa.Text(), nullable=True),
        sa.Column("codigo", sa.Text(), nullable=True),
        sa.Column("linguagem", sa.String(length=30), nullable=True),
        sa.Column("alternativas", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("afirmacoes", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("gabarito", sa.String(length=1), nullable=False),
        sa.Column("explicacao", sa.Text(), nullable=True),
        sa.Column("origem", sa.Text(), nullable=True),
        sa.Column("fonte", sa.Text(), nullable=True),
        sa.Column("dificuldade", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("dificuldade between 1 and 3", name="ck_estudo_questao_dificuldade"),
        sa.ForeignKeyConstraint(["topico_id"], ["estudo_topico.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estudo_questao_topico", "estudo_questao", ["topico_id"])
    op.create_index("ix_estudo_questao_formato", "estudo_questao", ["formato"])

    op.create_table(
        "estudo_agenda",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("questao_id", sa.UUID(), nullable=False),
        sa.Column("proxima_em", sa.Date(), nullable=False),
        sa.Column("ultima_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("intervalo_dias", sa.Integer(), nullable=False),
        sa.Column("acertos_seguidos", sa.Integer(), nullable=False),
        sa.Column("total_acertos", sa.Integer(), nullable=False),
        sa.Column("total_erros", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="nova", nullable=False),
        sa.ForeignKeyConstraint(["questao_id"], ["estudo_questao.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("questao_id"),
    )
    op.create_index("ix_estudo_agenda_proxima", "estudo_agenda", ["proxima_em", "estado"])

    op.create_table(
        "estudo_tentativa",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("questao_id", sa.UUID(), nullable=False),
        sa.Column(
            "respondida_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("acertou", sa.Boolean(), nullable=False),
        sa.Column("resposta", sa.String(length=1), nullable=True),
        sa.Column("tentativa_n", sa.Integer(), nullable=False),
        sa.Column("segundos", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["questao_id"], ["estudo_questao.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estudo_tentativa_questao", "estudo_tentativa", ["questao_id", "respondida_em"])
    op.create_index("ix_estudo_tentativa_data", "estudo_tentativa", ["respondida_em"])


def downgrade() -> None:
    op.drop_index("ix_estudo_tentativa_data", table_name="estudo_tentativa")
    op.drop_index("ix_estudo_tentativa_questao", table_name="estudo_tentativa")
    op.drop_table("estudo_tentativa")
    op.drop_index("ix_estudo_agenda_proxima", table_name="estudo_agenda")
    op.drop_table("estudo_agenda")
    op.drop_index("ix_estudo_questao_formato", table_name="estudo_questao")
    op.drop_index("ix_estudo_questao_topico", table_name="estudo_questao")
    op.drop_table("estudo_questao")
    op.drop_index("ux_estudo_topico_modulo_nome", table_name="estudo_topico")
    op.drop_table("estudo_topico")
    op.drop_table("estudo_modulo")
