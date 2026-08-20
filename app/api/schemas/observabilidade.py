"""Schemas da observabilidade — /api/observabilidade/*."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StatsResponse(BaseModel):
    ai_calls_total: int
    ai_calls_falhas: int
    tokens_total: int
    # `None` = nenhuma chamada com preço conhecido. Diferente de 0.0, que
    # afirma que rodou e não custou nada (modelo local).
    custo_usd_estimado: float | None = None
    ai_calls_sem_preco: int = 0
    latencia_media_ms: int | None = None
    pipeline_events_total: int


class AiCallResponse(BaseModel):
    id: str
    agente: str
    tarefa: str | None = None
    provider: str
    modelo: str
    # Prompt e resposta só vêm no detalhe: na lista eles pesam megabytes.
    prompt_chars: int | None = None
    resposta_chars: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    tokens_total: int | None = None
    latencia_ms: int | None = None
    sucesso: bool
    finish_reason: str | None = None
    error_message: str | None = None
    alvo_ref: str | None = None
    created_at: datetime


class AiCallDetalheResponse(AiCallResponse):
    prompt: str | None = None
    resposta: str | None = None


class EventoResponse(BaseModel):
    id: str
    evento: str
    status: str
    detalhe: str | None = None
    alvo_ref: str | None = None
    duracao_ms: int | None = None
    created_at: datetime


class Pagina(BaseModel):
    total: int
    itens: list


class PaginaAiCalls(Pagina):
    itens: list[AiCallResponse]


class PaginaEventos(Pagina):
    itens: list[EventoResponse]
