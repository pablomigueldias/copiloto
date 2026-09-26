"""Schemas do CRM comercial — /api/comercial/*."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EmpresaLinha(BaseModel):
    id: int
    nome: str
    segmento: str | None = None
    bairro: str | None = None
    pessoa_fisica: bool
    cnes: str | None = None
    emails: list[str] = []
    telefones: list[str] = []
    lead_id: int | None = None


class PaginaEmpresas(BaseModel):
    total: int
    itens: list[EmpresaLinha]


class TrazerRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=10)
    confirmar_pessoa_fisica: bool = False


class TrazerResposta(BaseModel):
    trazidos: list[int]
    # estabelecimento → motivo de ter ficado de fora
    pulados: dict[int, str]
