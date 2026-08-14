from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class PipelineEvent(Base, UUIDPrimaryKeyMixin):
    """Telemetria técnica: etapa começou, terminou, quanto demorou, falhou.

    NÃO confundir com `agente_eventos` (blackboard: o que um agente FEZ sobre
    um alvo). A separação é fina — se a tela de observabilidade da F1.7 acabar
    lendo só uma das duas, a outra deve morrer.
    """

    __tablename__ = "pipeline_events"

    evento: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="ok", server_default="ok", nullable=False
    )
    detalhe: Mapped[str | None] = mapped_column(Text)
    alvo_ref: Mapped[str | None] = mapped_column(String(120))
    duracao_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_pipeline_events_evento", "evento"),
        Index("ix_pipeline_events_created_at", "created_at"),
        Index("ix_pipeline_events_alvo_ref", "alvo_ref"),
    )

    def __repr__(self) -> str:
        return f"<PipelineEvent {self.evento} status={self.status}>"
