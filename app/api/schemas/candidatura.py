"""Schemas da candidatura — /api/vagas/*."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VagaRequest(BaseModel):
    descricao: str = Field(min_length=50, max_length=40_000)
    titulo: str | None = None
    empresa: str | None = None
    link: str | None = None
    fonte: str | None = None


class EventoRequest(BaseModel):
    evento: str
    detalhe: str | None = None


class VagaResponse(BaseModel):
    id: str
    titulo: str
    empresa: str | None = None
    status: str
    link: str | None = None
    localizacao: str | None = None
    modelo: str | None = None
    senioridade: str | None = None
    contato_email: str | None = None
    match_score: int | None = None
    analise_json: dict | None = None
    match_json: dict | None = None
    curriculo_json: dict | None = None
    curriculo_gerado_em: datetime | None = None
    created_at: datetime


class PaginaVagas(BaseModel):
    total: int
    itens: list[VagaResponse]


class EventoResponse(BaseModel):
    evento: str
    detalhe: str | None = None
    ocorreu_em: datetime


class VagaDetalheResponse(VagaResponse):
    descricao: str
    historico: list[EventoResponse] = []


class GeracaoResponse(BaseModel):
    vaga_id: str
    curriculo: dict
    pdf: str | None = None
    acao_id: str | None = None
    # O que a anti-alucinação derrubou e o que o ATS vai reclamar: a resposta
    # carrega os dois porque são o que decide se dá para enviar como está.
    rejeitados: list[str] = []
    avisos: list[str] = []


class MetricasResponse(BaseModel):
    funil: dict[str, int]
    por_status: dict[str, int]
    taxa_resposta: float | None = None
    dias_ate_resposta: float | None = None
    followup_vencido: int
    paradas: list[dict] = []
    gaps_frequentes: list[dict] = []
    score_medio: float | None = None
