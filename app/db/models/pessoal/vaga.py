from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.pessoal.candidatura_email import CandidaturaEmail


# Pipeline da candidatura. Máquina de estados no banco — quem decide a
# transição é o código, nunca o LLM.
STATUS_VAGA = (
    "quero_candidatar",
    "candidatei",
    "respondeu",
    "entrevista",
    "fim",
)


class Vaga(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Vaga-alvo do agente de candidatura (Fase 3).

    A JD entra colada ou raspada de uma URL; o extrator a destrincha em
    ``analise_json`` e o cruzamento com o Perfil Mestre vira ``match_json``.
    """

    __tablename__ = "pessoal_vagas"

    # ── Identidade da vaga ───────────────────────────────────────
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    empresa: Mapped[str | None] = mapped_column(String(300))
    link: Mapped[str | None] = mapped_column(String(800))
    fonte: Mapped[str | None] = mapped_column(String(100))  # LinkedIn, Gupy...

    # ── Contato pra candidatura ──────────────────────────────────
    contato_nome: Mapped[str | None] = mapped_column(String(200))
    contato_email: Mapped[str | None] = mapped_column(String(300))

    # ── Detalhes ─────────────────────────────────────────────────
    localizacao: Mapped[str | None] = mapped_column(String(200))
    modelo: Mapped[str | None] = mapped_column(String(30))  # remoto/hibrido/presencial
    senioridade: Mapped[str | None] = mapped_column(String(50))
    descricao: Mapped[str] = mapped_column(Text, nullable=False)  # JD colada
    notas: Mapped[str | None] = mapped_column(Text)

    # ── Pipeline ─────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(30),
        default="quero_candidatar",
        server_default="quero_candidatar",
        nullable=False,
    )

    # ── Saídas da IA ─────────────────────────────────────────────
    # analise_json: {requisitos_obrigatorios[], desejaveis[],
    #   stack[], senioridade, palavras_chave[], resumo}
    analise_json: Mapped[dict | None] = mapped_column(JSONB)
    # match_json: {aderencia, tenho[], gaps[], destaques[]}
    match_json: Mapped[dict | None] = mapped_column(JSONB)
    # Match resumido como inteiro 0-100 (pra ordenar a lista)
    match_score: Mapped[int | None] = mapped_column(Integer)

    # ── Currículo ATS gerado (persistido pra não regerar toda vez) ───
    # curriculo_json: CurriculoVaga adaptado a ESTA vaga (resumo/competências/
    #   experiências/projetos). Dados factuais ainda saem do perfil ao gerar.
    curriculo_json: Mapped[dict | None] = mapped_column(JSONB)
    curriculo_gerado_em: Mapped[datetime | None] = mapped_column(DateTime)

    emails: Mapped[list[CandidaturaEmail]] = relationship(
        back_populates="vaga",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_pessoal_vagas_status", "status"),
        Index("ix_pessoal_vagas_match_score", "match_score"),
    )

    def __repr__(self) -> str:
        return f"<Vaga id={self.id} titulo={self.titulo!r} status={self.status}>"
