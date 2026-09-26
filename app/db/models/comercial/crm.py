"""O CRM da Fase 1: quem está em conversa, em que pé, e o que fazer a seguir.

Plano em `docs/motor-comercial/fase-1/00-visao-geral.md`, passo 1. Três regras:

- **Estabelecimento não é lead (D9).** A base de prospecção é o universo do que
  existe; o lead é quem eu trouxe para conversar. `estabelecimento_id` aponta
  para lá e fica nulo quando o lead veio do WhatsApp, do site ou de indicação.
  Se a base apagar o estabelecimento (retenção ou supressão), o lead continua,
  sem o vínculo: a conversa que já aconteceu não some por causa da base.
- **Um lead, uma tabela.** O lead do bot comercial (Cloud API) entra aqui
  também, com colunas próprias quando o bot chegar, e não numa segunda tabela.
- **Estágio muda por regra de código** (`app/comercial/crm/leads.py`), e cada
  mudança fica em `comercial_transicao`, com o motivo.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrigemLead(StrEnum):
    PROSPECCAO = "prospeccao"
    WHATSAPP = "whatsapp"
    SITE = "site"
    INDICACAO = "indicacao"
    NEWSLETTER = "newsletter"


class Estagio(StrEnum):
    PROSPECT = "prospect"
    CONTATADO = "contatado"
    RESPONDEU = "respondeu"
    REUNIAO = "reuniao"
    PROPOSTA = "proposta"
    GANHO = "ganho"
    PERDIDO = "perdido"
    NAO_AGORA = "nao_agora"


class Canal(StrEnum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"
    REUNIAO = "reuniao"
    NOTA = "nota"


class Direcao(StrEnum):
    SAIDA = "saida"
    ENTRADA = "entrada"
    INTERNA = "interna"  # nota minha, ficha do Pesquisador


class TipoTarefa(StrEnum):
    PESQUISAR = "pesquisar"
    ESCREVER_EMAIL = "escrever_email"
    ENVIAR_EMAIL = "enviar_email"
    LEMBRETE = "lembrete"
    LINKEDIN = "linkedin"
    RESPONDER = "responder"
    MARCAR_RAIOX = "marcar_raiox"


def _check(coluna: str, enum: type[StrEnum], nome: str) -> CheckConstraint:
    valores = ", ".join(f"'{v.value}'" for v in enum)
    return CheckConstraint(f"{coluna} IN ({valores})", name=nome)


def _agora() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Lead(Base):
    __tablename__ = "comercial_lead"
    __table_args__ = (
        _check("origem", OrigemLead, "ck_comercial_lead_origem"),
        _check("estagio", Estagio, "ck_comercial_lead_estagio"),
        Index("ix_comercial_lead_estagio", "estagio", "proxima_em"),
        Index("ix_comercial_lead_estabelecimento", "estabelecimento_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    origem: Mapped[str] = mapped_column(String(12), nullable=False)
    estabelecimento_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("prospeccao_estabelecimento.id", ondelete="SET NULL")
    )
    # O nome que aparece no card: a clínica, ou a pessoa quando não há empresa.
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    contato_nome: Mapped[str | None] = mapped_column(Text)
    cargo: Mapped[str | None] = mapped_column(Text)
    # Só o canal que vai ser usado, normalizado. O resto fica na base.
    email: Mapped[str | None] = mapped_column(Text)
    telefone: Mapped[str | None] = mapped_column(String(20))
    site: Mapped[str | None] = mapped_column(Text)
    # Onde a própria clínica publica o e-mail (Pesquisador, passo 3). Nulo = não
    # confirmado, e e-mail não confirmado não vira destinatário (regras §4).
    email_fonte: Mapped[str | None] = mapped_column(Text)
    pesquisado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estagio: Mapped[str] = mapped_column(String(12), nullable=False, default="prospect")
    proxima_acao: Mapped[str | None] = mapped_column(Text)
    proxima_em: Mapped[date | None] = mapped_column(Date)
    # `nao_agora` volta a ser prospect nesta data (90 dias, README §3).
    volta_em: Mapped[date | None] = mapped_column(Date)
    motivo_perda: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = _agora()
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Transicao(Base):
    __tablename__ = "comercial_transicao"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comercial_lead.id", ondelete="CASCADE"), nullable=False, index=True
    )
    de: Mapped[str | None] = mapped_column(String(12))
    para: Mapped[str] = mapped_column(String(12), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = _agora()


class Interacao(Base):
    """A linha do tempo. Chama-se assim porque `prospeccao_atividade` já é CNAE."""

    __tablename__ = "comercial_interacao"
    __table_args__ = (
        _check("canal", Canal, "ck_comercial_interacao_canal"),
        _check("direcao", Direcao, "ck_comercial_interacao_direcao"),
        Index("ix_comercial_interacao_lead", "lead_id", "criado_em"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comercial_lead.id", ondelete="CASCADE"), nullable=False
    )
    canal: Mapped[str] = mapped_column(String(10), nullable=False)
    direcao: Mapped[str] = mapped_column(String(8), nullable=False)
    # "email_1", "lembrete", "resposta", "ficha"... livre: é rótulo, não regra.
    tipo: Mapped[str | None] = mapped_column(String(30))
    texto: Mapped[str | None] = mapped_column(Text)
    # A ficha do Pesquisador: cada fato com a URL de onde veio.
    dados: Mapped[dict | None] = mapped_column(JSONB)
    ai_call_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_calls.id", ondelete="SET NULL")
    )
    criado_em: Mapped[datetime] = _agora()


class Tarefa(Base):
    __tablename__ = "comercial_tarefa"
    __table_args__ = (
        _check("tipo", TipoTarefa, "ck_comercial_tarefa_tipo"),
        Index("ix_comercial_tarefa_aberta", "vence_em", postgresql_where="feita_em IS NULL"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    lead_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comercial_lead.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    vence_em: Mapped[date] = mapped_column(Date, nullable=False)
    feita_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _agora()
