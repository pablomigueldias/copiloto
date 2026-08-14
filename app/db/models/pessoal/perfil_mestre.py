from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PerfilMestre(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Quem EU sou — o insumo central dos agentes pessoais.

    A fonte factual de tudo que os agentes escrevem sobre mim. A regra
    anti-alucinação da Fase 3 depende disto: o gerador SELECIONA e reformula
    itens daqui, nunca inventa. Costuma existir um só perfil com ``ativo=True``.
    """

    __tablename__ = "pessoal_perfil_mestre"

    # ── Identidade ───────────────────────────────────────────────
    ativo: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    titulo: Mapped[str | None] = mapped_column(String(200))  # ex: "Dev Full-Stack"
    resumo: Mapped[str | None] = mapped_column(Text)  # bio curta

    # ── Tom de escrita (pra carta soar como você, não como IA) ───
    tom_escrita: Mapped[str | None] = mapped_column(Text)

    # ── Blocos estruturados (JSONB) ──────────────────────────────
    # habilidades: [{nome, nivel, onde_usou}]
    habilidades: Mapped[list | None] = mapped_column(JSONB)
    # projetos: [{nome, descricao, prova, stack: [], link}]
    projetos: Mapped[list | None] = mapped_column(JSONB)
    # experiencias: [{empresa, cargo, periodo, descricao}]
    experiencias: Mapped[list | None] = mapped_column(JSONB)
    # formacao: [{instituicao, curso, periodo}]
    formacao: Mapped[list | None] = mapped_column(JSONB)
    # certificacoes: [{nome, tema, instituicao, ano, prova}]
    certificacoes: Mapped[list | None] = mapped_column(JSONB)
    # o_que_procuro: {stack: [], modelo, tipo_empresa, pretensao, observacoes}
    o_que_procuro: Mapped[dict | None] = mapped_column(JSONB)
    # blocos_curriculo: [{titulo, conteudo, tags: []}] — reaproveitáveis
    blocos_curriculo: Mapped[list | None] = mapped_column(JSONB)
    # contato: {email, telefone, linkedin, github, portfolio}
    contato: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_pessoal_perfil_ativo", "ativo"),
    )

    def __repr__(self) -> str:
        return f"<PerfilMestre id={self.id} nome={self.nome!r} ativo={self.ativo}>"
