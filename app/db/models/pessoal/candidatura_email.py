from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.pessoal.vaga import Vaga


class CandidaturaEmail(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Rascunho de candidatura (e-mail ou carta).

    PRINCÍPIO INEGOCIÁVEL: a ferramenta gera o rascunho e PARA. Quem revisa e
    envia é o humano — por isso o status nasce 'rascunho' e nada aqui dispara
    e-mail. A partir da Fase 4 o envio passa pela fila de aprovação.
    """

    __tablename__ = "pessoal_candidatura_emails"

    vaga_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pessoal_vagas.id", ondelete="CASCADE"),
        nullable=False,
    )

    # email | carta
    tipo: Mapped[str] = mapped_column(
        String(20), default="email", server_default="email", nullable=False
    )

    destinatario: Mapped[str | None] = mapped_column(String(300))
    assunto: Mapped[str | None] = mapped_column(String(500))
    corpo: Mapped[str] = mapped_column(Text, nullable=False)
    tom: Mapped[str | None] = mapped_column(String(100))

    # ciclo de vida — nasce rascunho; envio é manual, fora da ferramenta
    status: Mapped[str] = mapped_column(
        String(30), default="rascunho", server_default="rascunho", nullable=False
    )
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # variantes A/B e contexto usado na geração (pra revisar/treinar)
    variantes: Mapped[list | None] = mapped_column(JSONB)
    contexto: Mapped[dict | None] = mapped_column(JSONB)

    vaga: Mapped[Vaga] = relationship(back_populates="emails")

    __table_args__ = (
        Index("ix_pessoal_cand_emails_vaga_id", "vaga_id"),
        Index("ix_pessoal_cand_emails_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<CandidaturaEmail id={self.id} tipo={self.tipo} "
            f"status={self.status}>"
        )
