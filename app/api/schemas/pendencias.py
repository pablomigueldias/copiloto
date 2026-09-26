"""Schemas do quadro de pendências — /api/pendencias/*."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Coluna = Literal["a_fazer", "fazendo", "feito"]


class PendenciaResponse(BaseModel):
    id: str
    titulo: str
    descricao: str | None = None
    topico: str
    quando: str | None = None
    prazo: date | None = None
    onde: str | None = None
    coluna: Coluna
    ordem: int
    concluida_em: datetime | None = None
    created_at: datetime


class Quadro(BaseModel):
    topicos: list[str]
    itens: list[PendenciaResponse]


class PendenciaNova(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    topico: str = Field(min_length=1, max_length=80)
    descricao: str | None = Field(default=None, max_length=5_000)
    quando: str | None = Field(default=None, max_length=160)
    prazo: date | None = None
    onde: str | None = Field(default=None, max_length=1_000)
    coluna: Coluna = "a_fazer"


class PendenciaEdicao(BaseModel):
    """Só o que veio muda. `prazo: null` apaga o prazo; omitir não mexe."""

    titulo: str | None = Field(default=None, min_length=1, max_length=300)
    topico: str | None = Field(default=None, min_length=1, max_length=80)
    descricao: str | None = Field(default=None, max_length=5_000)
    quando: str | None = Field(default=None, max_length=160)
    prazo: date | None = None
    onde: str | None = Field(default=None, max_length=1_000)
    coluna: Coluna | None = None
    ordem: int | None = Field(default=None, ge=0)
