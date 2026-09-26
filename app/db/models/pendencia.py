"""As pendências do Pablo, num quadro — o que antes morava numa lista de Markdown.

O `docs/PENDENCIAS.md` diz o que falta, mas é texto: não dá para arrastar um
item para "fazendo", filtrar por tópico nem ver o que tem prazo esta semana.
Cada linha aqui é um cartão do quadro de `/pendencias`.

`quando` e `prazo` são coisas diferentes, de propósito. Muita pendência não tem
data, tem **gatilho** ("antes do 1º contrato", "após 5 reuniões") — é a regra
de 26/09: fica registrada até a hora de precisar. `quando` guarda o gatilho como
foi escrito; `prazo` só existe quando há um dia de verdade, e é o que ordena.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

COLUNAS = ("a_fazer", "fazendo", "feito")


class Pendencia(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "pendencia"

    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    # O que fazer, em uma ou duas frases. O título diz o quê; aqui vai o como.
    descricao: Mapped[str | None] = mapped_column(Text)
    # "E-mail e domínio", "Currículo" — a coluna ou etiqueta do quadro.
    topico: Mapped[str] = mapped_column(String(80), nullable=False)
    # O gatilho, como foi escrito: "agora", "antes do 1º contrato", "03/10".
    quando: Mapped[str | None] = mapped_column(String(160))
    prazo: Mapped[date | None] = mapped_column(Date)
    # Onde está o detalhe: o arquivo, a seção. Nunca o detalhe copiado.
    onde: Mapped[str | None] = mapped_column(Text)

    coluna: Mapped[str] = mapped_column(
        String(20), nullable=False, default="a_fazer", server_default="a_fazer"
    )
    # Posição dentro da coluna; menor em cima.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "coluna IN (" + ", ".join(f"'{c}'" for c in COLUNAS) + ")",
            name="ck_pendencia_coluna",
        ),
        Index("ix_pendencia_coluna_ordem", "coluna", "ordem"),
        Index("ix_pendencia_topico", "topico"),
    )
