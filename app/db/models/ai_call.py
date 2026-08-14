from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class AiCall(Base, UUIDPrimaryKeyMixin):
    """Uma linha por chamada de LLM — inclusive as locais.

    No repo antigo só o provider pago gravava aqui, o que tornava a tela de
    observabilidade cega justamente no caminho que mais erra. O gateway da
    Fase 1 grava em TODO caminho, com ou sem sucesso.
    """

    __tablename__ = "ai_calls"

    agente: Mapped[str] = mapped_column(
        String(50), default="desconhecido", server_default="desconhecido"
    )
    # Casa com o contrato do gateway (§7): classificar | extrair | redigir |
    # resumir. É por este campo que se responde "qual tarefa gasta token".
    tarefa: Mapped[str | None] = mapped_column(String(50))

    provider: Mapped[str] = mapped_column(String(50))
    modelo: Mapped[str] = mapped_column(String(100))

    # ── Payload (só se observ_store_payloads) ─────────────────────
    prompt: Mapped[str | None] = mapped_column(Text)
    resposta: Mapped[str | None] = mapped_column(Text)
    prompt_chars: Mapped[int | None] = mapped_column(Integer)
    resposta_chars: Mapped[int | None] = mapped_column(Integer)

    # ── Custo ─────────────────────────────────────────────────────
    # Modelo local custa zero; o campo existe para a fase de coleta (§7), em
    # que a API externa escreve e é exatamente aí que o custo importa.
    tokens_input: Mapped[int | None] = mapped_column(Integer)
    tokens_output: Mapped[int | None] = mapped_column(Integer)
    tokens_total: Mapped[int | None] = mapped_column(Integer)
    custo_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))

    # ── Resultado ─────────────────────────────────────────────────
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    sucesso: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    finish_reason: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Referência livre ao objeto da chamada (vaga:<uuid>, contato:<uuid>...).
    # Substitui o `empresa_cnpj` do repo antigo, que só servia ao CRM de CNPJ.
    alvo_ref: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_ai_calls_agente", "agente"),
        Index("ix_ai_calls_created_at", "created_at"),
        Index("ix_ai_calls_sucesso", "sucesso"),
        Index("ix_ai_calls_alvo_ref", "alvo_ref"),
    )

    def __repr__(self) -> str:
        return f"<AiCall {self.agente}/{self.tarefa} ok={self.sucesso}>"
