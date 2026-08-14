"""Rotas de observabilidade — /api/observabilidade/*.

O que a tela vai consumir quando existir. Tudo atrás de sessão: `ai_calls`
guarda prompt e resposta inteiros, ou seja, todo o material que passa pelo
sistema.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.observabilidade import (
    AiCallDetalheResponse,
    PaginaAiCalls,
    PaginaEventos,
    StatsResponse,
)
from app.db.models.ai_call import AiCall
from app.db.models.auth.usuario import Usuario
from app.db.models.pipeline_event import PipelineEvent
from app.db.observability import stats as calcular_stats
from app.db.session import get_session

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/observabilidade", tags=["observabilidade"])


@router.get("/stats", response_model=StatsResponse, summary="Números do painel")
async def get_stats(_: UsuarioLogado) -> StatsResponse:
    return StatsResponse(**await calcular_stats())


@router.get("/ai-calls", response_model=PaginaAiCalls, summary="Chamadas de LLM")
async def listar_ai_calls(
    _: UsuarioLogado,
    agente: str | None = None,
    tarefa: str | None = None,
    modelo: str | None = None,
    sucesso: bool | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaAiCalls:
    filtros = []
    if agente:
        filtros.append(AiCall.agente == agente)
    if tarefa:
        filtros.append(AiCall.tarefa == tarefa)
    if modelo:
        filtros.append(AiCall.modelo == modelo)
    if sucesso is not None:
        filtros.append(AiCall.sucesso.is_(sucesso))

    async with get_session() as session:
        total = await session.scalar(select(func.count(AiCall.id)).where(*filtros)) or 0
        linhas = (
            await session.scalars(
                select(AiCall)
                .where(*filtros)
                .order_by(AiCall.created_at.desc())
                .limit(limite)
                .offset(offset)
            )
        ).all()

    return PaginaAiCalls(
        total=int(total),
        itens=[{**c.__dict__, "id": str(c.id)} for c in linhas],
    )


@router.get(
    "/ai-calls/{call_id}",
    response_model=AiCallDetalheResponse,
    summary="Uma chamada, com prompt e resposta",
)
async def detalhe_ai_call(call_id: UUID, _: UsuarioLogado) -> AiCallDetalheResponse:
    async with get_session() as session:
        call = await session.get(AiCall, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Chamada não encontrada.")
    return AiCallDetalheResponse(**{**call.__dict__, "id": str(call.id)})


@router.get("/eventos", response_model=PaginaEventos, summary="Eventos de pipeline")
async def listar_eventos(
    _: UsuarioLogado,
    evento: str | None = None,
    status: str | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaEventos:
    filtros = []
    if evento:
        filtros.append(PipelineEvent.evento == evento)
    if status:
        filtros.append(PipelineEvent.status == status)

    async with get_session() as session:
        total = await session.scalar(select(func.count(PipelineEvent.id)).where(*filtros)) or 0
        linhas = (
            await session.scalars(
                select(PipelineEvent)
                .where(*filtros)
                .order_by(PipelineEvent.created_at.desc())
                .limit(limite)
                .offset(offset)
            )
        ).all()

    return PaginaEventos(
        total=int(total),
        itens=[{**e.__dict__, "id": str(e.id)} for e in linhas],
    )
