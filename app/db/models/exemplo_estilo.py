"""Texto meu, aprovado por mim — a camada 2 do plano (§4), "como soar".

O degrau 3 da escada da qualidade: três exemplos meus, escolhidos por
similaridade com a situação nova, colados no prompt. O plano estima que entrega
60-70% do que o fine-tune entregaria, por dias de trabalho em vez de meses.

O embedding é do **contexto**, não do texto. Na hora de gerar, o que existe é a
situação ("e-mail frio para agência pequena que pediu orçamento"); comparar
situação com situação é o que acha o exemplo certo. Comparar a situação nova com
o texto de um e-mail antigo compara coisas de naturezas diferentes.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.models.conhecimento import DIM_EMBEDDING


class ExemploEstilo(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "exemplo_estilo"

    # 'email_frio' | 'bullet_curriculo' | 'msg_recrutador' — o `tipo` da ação
    # que o produziu.
    tarefa: Mapped[str] = mapped_column(String(50), nullable=False)
    contexto: Mapped[str] = mapped_column(Text, nullable=False)
    # A versão aprovada: o que eu mandei, não o que a IA escreveu.
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    # Preenchido pelo worker, segundos depois. Aprovar não pode esperar GPU.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIM_EMBEDDING))

    # SET NULL: apagar a ação não pode levar junto um exemplo já aprovado — ele
    # virou dado meu, não rastro dela.
    acao_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acao_pendente.id", ondelete="SET NULL")
    )
    aprovado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_exemplo_estilo_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_exemplo_estilo_tarefa", "tarefa"),
    )

    def __repr__(self) -> str:
        return f"<Exemplo {self.tarefa} {self.texto[:40]!r}>"
