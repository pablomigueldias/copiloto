"""Quando cada questão volta — e o registro de toda vez que ela voltou.

Duas tabelas com papéis diferentes, e a diferença é a razão de o sistema
existir:

- `estudo_tentativa` é **log**: uma linha por resposta, com a data e se acertei.
  Nunca é atualizada, nunca é apagada. É a memória do que aconteceu.
- `estudo_agenda` é **estado**: uma linha por questão, com a próxima data. É
  derivável do log, e mesmo assim existe — porque "quais voltam hoje" é a
  consulta que a tela faz a cada abertura, e derivar isso de um log crescente a
  cada request é pagar caro por uma informação que não muda entre respostas.

O intervalo cresce: sete dias no primeiro acerto e ×2,2 a cada acerto seguido,
até o teto. Errar não recua um degrau — **zera**, e a questão volta em dois
dias. Repetição espaçada é o mecanismo, e a assimetria é ele: o custo de rever
cedo demais é um minuto; o de rever tarde demais é errar na prova.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.estudo.questao import Questao

# Dias. Os três primeiros são os padrões da tela de revisão; o teto existe para
# a questão não sumir por dois anos depois de seis acertos seguidos.
INTERVALO_ACERTO = 7
INTERVALO_ERRO = 2
INTERVALO_ADIAR = 30
FATOR = 2.2
INTERVALO_MAX = 180

# `nova` nunca foi respondida; `aprendendo` tem erro recente; `dominada` são
# três acertos seguidos ou mais; `adiada` saiu da fila por escolha minha.
ESTADOS = ("nova", "aprendendo", "dominada", "adiada")
ACERTOS_PARA_DOMINAR = 3


class Agenda(Base, UUIDPrimaryKeyMixin):
    """O estado de uma questão para mim. Uma linha por questão."""

    __tablename__ = "estudo_agenda"

    questao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_questao.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # `date`, não `datetime`: "volta dia 28" é a pergunta, e guardar hora criaria
    # a possibilidade absurda de uma questão vencer às 14h32.
    proxima_em: Mapped[date] = mapped_column(Date, nullable=False)
    ultima_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    intervalo_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acertos_seguidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_acertos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_erros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="nova", server_default="nova"
    )

    questao: Mapped[Questao] = relationship(back_populates="agenda")

    __table_args__ = (
        # O índice que a tela usa em toda abertura: "o que vence até hoje".
        Index("ix_estudo_agenda_proxima", "proxima_em", "estado"),
    )

    def __repr__(self) -> str:
        return f"<Agenda {self.estado} volta={self.proxima_em}>"


class Tentativa(Base, UUIDPrimaryKeyMixin):
    """Uma resposta minha, com a data e se acertei. Só cresce.

    Guardar `tentativa_n` importa porque a tela deixa tentar de novo antes de
    revelar: acertar de primeira e acertar na segunda são coisas diferentes, e
    contar as duas como "acerto" apagaria a diferença. O agendamento usa
    `acertou` da **primeira** tentativa do bloco; o resto é para eu olhar.
    """

    __tablename__ = "estudo_tentativa"

    questao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_questao.id", ondelete="CASCADE"),
        nullable=False,
    )

    respondida_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    acertou: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # O que eu marquei: 'A'..'E', ou 'C'/'E' no julgue o item. Nulo quando a
    # questão foi adiada sem resposta.
    resposta: Mapped[str | None] = mapped_column(String(1))
    tentativa_n: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Quantos segundos entre abrir e responder. Nulo se a tela não mandou.
    segundos: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_estudo_tentativa_questao", "questao_id", "respondida_em"),
        # "quantas respondi hoje", "acerto por semana" — sempre por data.
        Index("ix_estudo_tentativa_data", "respondida_em"),
    )

    def __repr__(self) -> str:
        marca = "certo" if self.acertou else "errado"
        return f"<Tentativa {marca} {self.respondida_em:%d/%m}>"
