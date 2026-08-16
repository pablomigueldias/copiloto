"""O histórico de cada candidatura — o filme, não a foto.

`Vaga.status` responde *onde está*. Isto responde *quanto tempo levou para
chegar ali* e *quantas viraram entrevista* — e essas duas perguntas são a razão
de existir a parte de métricas da F5.

Sem tabela de evento, "tempo médio até a primeira resposta" é impossível de
calcular depois: a informação não foi guardada quando existia.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

# A ordem importa: é a ordem do funil no painel.
EVENTOS = (
    "salva",         # colei a vaga
    "analisada",     # requisitos extraídos + match calculado
    "gerada",        # currículo e carta prontos
    "enviada",       # eu mandei (a F5 não manda; ela registra que eu mandei)
    "visualizada",   # recrutador abriu / visualizou
    "respondida",    # veio resposta humana
    "entrevista",
    "recusada",
    "sem_retorno",   # o relógio venceu, ninguém respondeu
)


class CandidaturaEvento(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "candidatura_evento"

    vaga_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pessoal_vagas.id", ondelete="CASCADE"),
        nullable=False,
    )
    evento: Mapped[str] = mapped_column(String(30), nullable=False)
    detalhe: Mapped[str | None] = mapped_column(Text)
    ocorreu_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_candidatura_evento_vaga", "vaga_id", "ocorreu_em"),
        Index("ix_candidatura_evento_evento", "evento"),
    )

    def __repr__(self) -> str:
        return f"<Evento {self.evento} vaga={self.vaga_id}>"
