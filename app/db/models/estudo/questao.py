"""A questão — o conteúdo, separado do meu desempenho nela.

Duas tabelas onde parece caber uma. O motivo é operacional: a questão nasce de
um PDF de prova e vai ser **re-importada** — gabarito que a banca alterou,
enunciado que o OCR cortou, explicação que eu escrevo meses depois. Se o meu
agendamento morasse na mesma linha, todo re-import seria um risco de zerar o
histórico. Conteúdo aqui, agendamento em `estudo_agenda`, tentativa a tentativa
em `estudo_tentativa`.

`origem` não é enfeite: é o que me deixa desconfiar do gabarito. "COFFITO 2023,
item 29, gabarito definitivo" é conferível; "achei na internet" não é.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # a relação resolve pelo registry do SQLAlchemy, por nome
    from app.db.models.estudo.agenda import Agenda

# Os formatos que a tela sabe montar. Os dois primeiros são os que as provas do
# meu concurso de fato usam — Quadrix aplica "julgue o item" e múltipla escolha
# de cinco alternativas. O resto existe porque a tela de Formatos os documenta e
# eu vou cadastrar questão própria: cada um muda o que é obrigatório abaixo.
FORMATOS = (
    "multipla_escolha",  # A a E, uma correta
    "certo_errado",      # julgue o item: gabarito 'C' ou 'E'
    "afirmacoes",        # I, II, III + pergunta final + A a E
    "negativa",          # o NÃO em maiúsculas, quatro certas e uma fora
    "texto_base",        # trecho de apoio + pergunta sobre ele
    "codigo",            # SQL/Python + pergunta sobre o que devolve
    "calculo",           # números no enunciado, número na resposta
    "flashcard",         # frente/verso, sem alternativa
)

# Ordem fixa, sempre. Quem revisa reconhece a posição antes do conteúdo, e para
# memória isso é ganho, não vício: o que varia entre revisões é a questão.
LETRAS = ("A", "B", "C", "D", "E")

# Onde o módulo aparece na sidebar. São dois porque são dois os motivos de eu
# estudar: a prova que tem data e o assunto que tem carreira.
TRILHAS = ("concurso", "especializacao")


class Modulo(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Uma matéria. 'Matemática e raciocínio lógico', 'Banco de dados'."""

    __tablename__ = "estudo_modulo"

    nome: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    # Uma de `TRILHAS` — a sidebar agrupa por isso.
    trilha: Mapped[str] = mapped_column(String(40), nullable=False, default="concurso")
    # Para ordenar a tela sem depender de ordem alfabética, que muda de sentido
    # quando entra matéria nova.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    topicos: Mapped[list[Topico]] = relationship(
        back_populates="modulo", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Modulo {self.nome}>"


class Topico(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Um assunto dentro da matéria. 'Lógica proposicional', 'Normalização'.

    É o par módulo+tópico que a revisão mostra no topo, e é por ele que o
    agendamento devolve a questão — nunca por questão solta.
    """

    __tablename__ = "estudo_topico"

    modulo_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_modulo.id", ondelete="CASCADE"),
        nullable=False,
    )
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    modulo: Mapped[Modulo] = relationship(back_populates="topicos")

    __table_args__ = (
        Index("ux_estudo_topico_modulo_nome", "modulo_id", "nome", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Topico {self.nome}>"


class Questao(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "estudo_questao"

    topico_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("estudo_topico.id", ondelete="CASCADE"),
        nullable=False,
    )
    formato: Mapped[str] = mapped_column(String(30), nullable=False)

    # O comando que vale para um bloco inteiro de itens: "Acerca da proposição
    # X, julgue os itens a seguir". Fica separado do enunciado porque numa prova
    # Quadrix ele é compartilhado por três itens — e na revisão cada item
    # precisa funcionar sozinho, então ele é repetido em cada questão.
    comando: Mapped[str | None] = mapped_column(Text)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)

    # Trecho de apoio (formato texto_base) e código (formato codigo). Nulos nos
    # outros, e é isso que a tela usa para decidir o que desenhar.
    texto_base: Mapped[str | None] = mapped_column(Text)
    texto_base_fonte: Mapped[str | None] = mapped_column(Text)
    codigo: Mapped[str | None] = mapped_column(Text)
    linguagem: Mapped[str | None] = mapped_column(String(30))

    # [{"letra": "A", "texto": "..."}]. Vazio em certo_errado e flashcard.
    alternativas: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # ["I ...", "II ...", "III ..."] no formato afirmacoes.
    afirmacoes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # 'A'..'E' na múltipla escolha; 'C' ou 'E' no julgue o item. É o único campo
    # que decide certo ou errado — por isso ele é `nullable=False` e conferido
    # contra o gabarito oficial na importação.
    gabarito: Mapped[str] = mapped_column(String(1), nullable=False)

    # Nula de propósito no acervo importado: os PDFs trazem gabarito, não
    # justificativa. Escrever explicação que a banca não escreveu e apresentá-la
    # como dela seria inventar fonte. Eu preencho depois, pela tela.
    explicacao: Mapped[str | None] = mapped_column(Text)

    # "Quadrix · COFFITO 2023 · Analista de TI · item 29" — o suficiente para
    # eu reabrir o PDF e conferir quando o gabarito me parecer errado.
    origem: Mapped[str | None] = mapped_column(Text)
    # Nota do vault de onde a questão saiu, quando não veio de prova.
    fonte: Mapped[str | None] = mapped_column(Text)

    # 1 a 3. Só ordena a fila do dia; o agendamento não usa.
    dificuldade: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    topico: Mapped[Topico] = relationship(lazy="joined")
    agenda: Mapped[Agenda | None] = relationship(
        back_populates="questao",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("dificuldade between 1 and 3", name="ck_estudo_questao_dificuldade"),
        Index("ix_estudo_questao_topico", "topico_id"),
        Index("ix_estudo_questao_formato", "formato"),
    )

    def __repr__(self) -> str:
        return f"<Questao {self.formato} {str(self.id)[:8]}>"
