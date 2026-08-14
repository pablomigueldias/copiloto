from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class AgenteEvento(Base, UUIDPrimaryKeyMixin):
    """Memória compartilhada entre agentes (blackboard).

    Cada agente — ou ação manual — escreve aqui o que fez sobre um **alvo**
    (vaga, contato, chunk...). Qualquer outro lê a linha do tempo do alvo pra
    saber o que já foi feito. É o que destrava a coordenação sem dar ao LLM a
    decisão de fluxo.
    """

    __tablename__ = "agente_eventos"

    agente: Mapped[str] = mapped_column(String(50), nullable=False)
    alvo_tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    alvo_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    resumo: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    origem: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_agente_eventos_alvo", "alvo_tipo", "alvo_id"),
        Index("ix_agente_eventos_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AgenteEvento {self.agente}:{self.tipo} {self.alvo_tipo}/{self.alvo_id}>"
