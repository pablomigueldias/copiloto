"""base — squash das 43 migrations do repo de origem

Migration inicial escrita à mão. As 43 migrations do `prospector` documentavam
a evolução de um produto que não existe mais; para uma base nova de usuário
único, uma inicial limpa é mais honesta. O repo antigo fica como referência —
esta decisão é irreversível.

Ordem: extensões e schema → auth → observabilidade → pessoal.
`downgrade()` é completo e reverso: em base nova é barato, e é o que impede a
migration "só de ida" que trava rollback mais tarde.

Revision ID: 0001_base
Revises:
Create Date: 2026-08-14
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_base"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Infra ─────────────────────────────────────────────────────
    # pgvector já vem na imagem do compose mas nunca foi habilitado. CREATE
    # EXTENSION exige superusuário e é infra, não modelo — fica aqui para a
    # Fase 2 só precisar criar a tabela.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")

    # ── auth ──────────────────────────────────────────────────────
    op.create_table(
        "usuarios",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ultimo_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        schema="auth",
    )

    op.create_table(
        "sessoes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("usuario_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultimo_uso", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revogada", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["auth.usuarios.id"],
            name="fk_auth_sessoes_usuario", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        # UNIQUE já cria o índice de busca por token — não há índice extra.
        sa.UniqueConstraint("token_hash"),
        schema="auth",
    )
    op.create_index("ix_auth_sessoes_usuario_id", "sessoes", ["usuario_id"], schema="auth")

    op.create_table(
        "tentativas_login",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_tentativas_email_created", "tentativas_login",
        ["email", "created_at"], schema="auth",
    )
    op.create_index(
        "ix_auth_tentativas_ip_created", "tentativas_login",
        ["ip", "created_at"], schema="auth",
    )

    # ── Observabilidade ───────────────────────────────────────────
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agente", sa.String(length=50), server_default="desconhecido", nullable=False),
        sa.Column("tarefa", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("resposta", sa.Text(), nullable=True),
        sa.Column("prompt_chars", sa.Integer(), nullable=True),
        sa.Column("resposta_chars", sa.Integer(), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("tokens_total", sa.Integer(), nullable=True),
        sa.Column("custo_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("latencia_ms", sa.Integer(), nullable=True),
        sa.Column("sucesso", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("finish_reason", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("alvo_ref", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_calls_agente", "ai_calls", ["agente"])
    op.create_index("ix_ai_calls_created_at", "ai_calls", ["created_at"])
    op.create_index("ix_ai_calls_sucesso", "ai_calls", ["sucesso"])
    op.create_index("ix_ai_calls_alvo_ref", "ai_calls", ["alvo_ref"])

    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("evento", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ok", nullable=False),
        sa.Column("detalhe", sa.Text(), nullable=True),
        sa.Column("alvo_ref", sa.String(length=120), nullable=True),
        sa.Column("duracao_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_events_evento", "pipeline_events", ["evento"])
    op.create_index("ix_pipeline_events_created_at", "pipeline_events", ["created_at"])
    op.create_index("ix_pipeline_events_alvo_ref", "pipeline_events", ["alvo_ref"])

    op.create_table(
        "agente_eventos",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agente", sa.String(length=50), nullable=False),
        sa.Column("alvo_tipo", sa.String(length=30), nullable=False),
        sa.Column("alvo_id", sa.String(length=100), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("origem", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agente_eventos_alvo", "agente_eventos", ["alvo_tipo", "alvo_id"])
    op.create_index("ix_agente_eventos_created_at", "agente_eventos", ["created_at"])

    # ── Pessoal (insumo da Fase 3) ────────────────────────────────
    op.create_table(
        "pessoal_perfil_mestre",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=True),
        sa.Column("resumo", sa.Text(), nullable=True),
        sa.Column("tom_escrita", sa.Text(), nullable=True),
        sa.Column("habilidades", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("projetos", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("experiencias", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("formacao", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("certificacoes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("o_que_procuro", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("blocos_curriculo", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contato", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pessoal_perfil_ativo", "pessoal_perfil_mestre", ["ativo"])

    op.create_table(
        "pessoal_vagas",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("titulo", sa.String(length=300), nullable=False),
        sa.Column("empresa", sa.String(length=300), nullable=True),
        sa.Column("link", sa.String(length=800), nullable=True),
        sa.Column("fonte", sa.String(length=100), nullable=True),
        sa.Column("contato_nome", sa.String(length=200), nullable=True),
        sa.Column("contato_email", sa.String(length=300), nullable=True),
        sa.Column("localizacao", sa.String(length=200), nullable=True),
        sa.Column("modelo", sa.String(length=30), nullable=True),
        sa.Column("senioridade", sa.String(length=50), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="quero_candidatar", nullable=False),
        sa.Column("analise_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("match_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("match_score", sa.Integer(), nullable=True),
        sa.Column("curriculo_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("curriculo_gerado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pessoal_vagas_status", "pessoal_vagas", ["status"])
    op.create_index("ix_pessoal_vagas_match_score", "pessoal_vagas", ["match_score"])

    op.create_table(
        "pessoal_candidatura_emails",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("vaga_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(length=20), server_default="email", nullable=False),
        sa.Column("destinatario", sa.String(length=300), nullable=True),
        sa.Column("assunto", sa.String(length=500), nullable=True),
        sa.Column("corpo", sa.Text(), nullable=False),
        sa.Column("tom", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="rascunho", nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("variantes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contexto", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["vaga_id"], ["pessoal_vagas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pessoal_cand_emails_vaga_id", "pessoal_candidatura_emails", ["vaga_id"])
    op.create_index("ix_pessoal_cand_emails_status", "pessoal_candidatura_emails", ["status"])


def downgrade() -> None:
    op.drop_table("pessoal_candidatura_emails")
    op.drop_table("pessoal_vagas")
    op.drop_table("pessoal_perfil_mestre")
    op.drop_table("agente_eventos")
    op.drop_table("pipeline_events")
    op.drop_table("ai_calls")
    op.drop_table("tentativas_login", schema="auth")
    op.drop_table("sessoes", schema="auth")
    op.drop_table("usuarios", schema="auth")
    op.execute("DROP SCHEMA IF EXISTS auth CASCADE")
    # A extensão `vector` não é derrubada: pode haver outro schema usando.
