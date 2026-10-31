"""O simulado da prova e o reforço que ele destrava — ou não.

O ciclo é este, e as quatro tabelas existem para guardar cada passo dele:

1. `estudo_simulado` + `estudo_simulado_item` — a prova inteira, 60 questões no
   quadro do edital, respondidas sem ver gabarito. A nota sai pela fórmula do
   edital (item 12.3): P = 100/Q × TA.
2. `estudo_reforco` — um por **assunto errado**. Nasce `aguardando_questoes`:
   as 5 questões de reforço não vêm do estoque (o estoque é da prova), são
   escritas sob medida para o erro e importadas depois.
3. `estudo_reforco_item` — as 5. Respondidas com correção na hora, porque aqui
   o objetivo é aprender, não medir.
4. Acertou 75% (4 de 5) → `aprovado`. Menos que isso → `reprovado`, e nasce a
   rodada seguinte do mesmo assunto, de novo aguardando questões.

O simulado seguinte só abre quando nenhum reforço está pendente. A trava é a
regra do ciclo, não um enfeite de tela: fazer outra prova sem fechar o buraco da
anterior é medir de novo o mesmo buraco.

Nada aqui escreve em `estudo_tentativa` nem mexe em `estudo_agenda`. A revisão
espaçada é outro instrumento, e misturar os dois faria uma questão de prova
sumir da revisão por 7 dias porque eu a acertei no meio do simulado.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

ESTADOS_SIMULADO = ("em_andamento", "finalizado")
ESTADOS_REFORCO = ("aguardando_questoes", "pronto", "aprovado", "reprovado")

# 75% de cada assunto. Com 5 questões, isso é 4 acertos: 3 de 5 (60%) não passa.
QUESTOES_POR_REFORCO = 5
APROVACAO_REFORCO = 0.75


class Simulado(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "estudo_simulado"

    # "Simulado nº 3" é como eu me refiro a ele; o uuid não serve para isso.
    numero: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="em_andamento")
    iniciado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Preenchidos ao finalizar. A nota fica gravada, e não recalculada, porque
    # o estoque muda (gabarito corrigido depois de recurso) e a nota de um
    # simulado é a que ele teve no dia.
    acertos: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int | None] = mapped_column(Integer)
    nota: Mapped[float | None] = mapped_column(Numeric(5, 2))

    itens: Mapped[list[SimuladoItem]] = relationship(
        back_populates="simulado",
        cascade="all, delete-orphan",
        order_by="SimuladoItem.ordem",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Simulado nº {self.numero} {self.estado}>"


class SimuladoItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "estudo_simulado_item"

    simulado_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_simulado.id", ondelete="CASCADE"),
        nullable=False,
    )
    questao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_questao.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    # Copiados da questão no momento da montagem: o diagnóstico de um simulado
    # antigo não pode mudar porque eu re-etiquetei a questão depois.
    materia: Mapped[str] = mapped_column(String(10), nullable=False)
    assunto: Mapped[str] = mapped_column(String(160), nullable=False)
    # Entrou para cobrir assunto errado no simulado anterior? Só para a tela
    # dizer "voltou porque você errou".
    revisao: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    resposta: Mapped[str | None] = mapped_column(String(1))
    respondida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Nulo até finalizar: durante a prova não existe certo e errado gravado.
    acertou: Mapped[bool | None] = mapped_column(Boolean)

    simulado: Mapped[Simulado] = relationship(back_populates="itens")

    __table_args__ = (
        Index("ux_estudo_simulado_item_ordem", "simulado_id", "ordem", unique=True),
        Index("ix_estudo_simulado_item_questao", "questao_id"),
    )


class Reforco(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "estudo_reforco"

    simulado_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_simulado.id", ondelete="CASCADE"),
        nullable=False,
    )
    materia: Mapped[str] = mapped_column(String(10), nullable=False)
    assunto: Mapped[str] = mapped_column(String(160), nullable=False)
    # 1 na primeira; reprovou, nasce a 2 do mesmo assunto, e assim por diante.
    rodada: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    estado: Mapped[str] = mapped_column(
        String(24), nullable=False, default="aguardando_questoes"
    )
    # Quantas eu errei no simulado — o tamanho do buraco, para a tela.
    erros_no_simulado: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acertos: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # A escrita das 5 questões pelo botão da tela (`scripts/simulado/
    # gerar_reforco.py`, que roda o Claude Code sem cabeça). Nulo = ninguém
    # pediu; 'gerando' enquanto o processo vive; 'erro' com o motivo. Quando dá
    # certo, quem muda é o `estado` (vira 'pronto'), e aqui fica 'ok'. O pid
    # existe para a tela saber que um 'gerando' morreu sem avisar.
    geracao_estado: Mapped[str | None] = mapped_column(String(10))
    geracao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geracao_pid: Mapped[int | None] = mapped_column(Integer)
    geracao_erro: Mapped[str | None] = mapped_column(String(2000))

    itens: Mapped[list[ReforcoItem]] = relationship(
        back_populates="reforco",
        cascade="all, delete-orphan",
        order_by="ReforcoItem.ordem",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ux_estudo_reforco_rodada", "simulado_id", "assunto", "rodada", unique=True
        ),
        Index("ix_estudo_reforco_estado", "estado"),
    )

    def __repr__(self) -> str:
        return f"<Reforco {self.assunto} r{self.rodada} {self.estado}>"


class ReforcoItem(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "estudo_reforco_item"

    reforco_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_reforco.id", ondelete="CASCADE"),
        nullable=False,
    )
    questao_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_questao.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    resposta: Mapped[str | None] = mapped_column(String(1))
    acertou: Mapped[bool | None] = mapped_column(Boolean)
    respondida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    reforco: Mapped[Reforco] = relationship(back_populates="itens")

    __table_args__ = (
        Index("ux_estudo_reforco_item_ordem", "reforco_id", "ordem", unique=True),
    )
