"""Schemas do conhecimento — /api/conhecimento/*."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TrechoResponse(BaseModel):
    """Um resultado de busca.

    `fonte_ref`, `titulo` e `origem` não são detalhe de depuração: a tela da F3
    cita a fonte, e `origem` diz se o trecho veio do vetor, do full-text ou dos
    dois — é como se descobre que metade da busca está carregando a outra.
    """

    id: str
    fonte_tipo: str
    fonte_ref: str
    ordem: int
    titulo: str | None = None
    conteudo: str
    metadados: dict = {}
    score: float
    origem: str


class BuscaResponse(BaseModel):
    consulta: str
    total: int
    trechos: list[TrechoResponse]


class FonteResponse(BaseModel):
    fonte_tipo: str
    fonte_ref: str
    titulo: str | None = None
    chunks: int
    atualizado_em: datetime


class InventarioResponse(BaseModel):
    total: int
    chunks_por_tipo: dict[str, int]
    itens: list[FonteResponse]


class RemocaoResponse(BaseModel):
    fonte_tipo: str
    fonte_ref: str
    chunks_removidos: int
