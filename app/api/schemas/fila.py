"""Schemas da fila de aprovação — /api/fila/*."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AcaoResponse(BaseModel):
    id: str
    agente: str
    tipo: str
    titulo: str
    status: str
    contexto: str | None = None
    texto_gerado: str | None = None
    texto_final: str | None = None
    motivo: str | None = None
    payload: dict = {}
    alvo_ref: str | None = None
    criada_em: datetime
    decidida_em: datetime | None = None


class PaginaFila(BaseModel):
    total: int
    por_status: dict[str, int]
    itens: list[AcaoResponse]


class DecisaoRequest(BaseModel):
    decisao: Literal["aprovar", "editar", "rejeitar"]
    # Mandar o texto é o que produz o par de treino. Quem aprova sem mexer pode
    # omitir; quem mexeu, manda — e o serviço decide o rótulo comparando.
    texto_final: str | None = Field(default=None, max_length=50_000)
    motivo: str | None = Field(default=None, max_length=1_000)
