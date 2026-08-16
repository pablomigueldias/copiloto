"""Rotas da candidatura — /api/vagas/*.

A entrada é sempre texto colado (§7 do plano: zero automação de LinkedIn). O
que a API faz é o que a CLI faz — analisar, gerar, registrar evento e medir.

**Não existe rota de enviar.** O currículo vira PDF e a ação entra na fila; o
envio é da F6.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.candidatura import (
    EventoRequest,
    GeracaoResponse,
    MetricasResponse,
    PaginaVagas,
    VagaDetalheResponse,
    VagaRequest,
    VagaResponse,
)
from app.candidatura import metricas as painel
from app.candidatura import perfil, servico, vagas
from app.db.models.auth.usuario import Usuario
from app.db.models.pessoal.vaga import STATUS_VAGA

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/vagas", tags=["candidatura"])


def _json(v) -> dict:
    return {**{c: getattr(v, c) for c in VagaResponse.model_fields if c != "id"}, "id": str(v.id)}


@router.post("", response_model=VagaResponse, status_code=201, summary="Cola uma vaga")
async def post_vaga(_: UsuarioLogado, req: VagaRequest) -> VagaResponse:
    try:
        vaga = await vagas.criar(**req.model_dump())
    except vagas.VagaErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return VagaResponse(**_json(vaga))


@router.get("", response_model=PaginaVagas, summary="As vagas, mais aderentes primeiro")
async def get_vagas(
    _: UsuarioLogado,
    status: str | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaVagas:
    if status and status not in STATUS_VAGA:
        raise HTTPException(status_code=422, detail=f"status inválido: {status}")
    total, itens = await vagas.listar(status=status, limite=limite, offset=offset)
    return PaginaVagas(total=total, itens=[_json(v) for v in itens])


@router.get("/metricas", response_model=MetricasResponse, summary="Funil, gaps e follow-up")
async def get_metricas(_: UsuarioLogado) -> MetricasResponse:
    return MetricasResponse(**(await painel.calcular()).como_json())


@router.get("/{vaga_id}", response_model=VagaDetalheResponse, summary="Uma vaga, com histórico")
async def get_vaga(vaga_id: UUID, _: UsuarioLogado) -> VagaDetalheResponse:
    try:
        vaga = await vagas.obter(vaga_id)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    historico = await vagas.historico(vaga_id)
    return VagaDetalheResponse(
        **_json(vaga),
        descricao=vaga.descricao,
        historico=[
            {"evento": e.evento, "detalhe": e.detalhe, "ocorreu_em": e.ocorreu_em}
            for e in historico
        ],
    )


@router.post("/{vaga_id}/analisar", response_model=VagaResponse, summary="Requisitos + match")
async def post_analisar(vaga_id: UUID, _: UsuarioLogado, forcar: bool = False) -> VagaResponse:
    try:
        analise = await servico.analisar(vaga_id, forcar=forcar)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except perfil.PerfilAusente as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VagaResponse(**_json(analise.vaga))


@router.post("/{vaga_id}/curriculo", response_model=GeracaoResponse, summary="Gera o currículo")
async def post_curriculo(
    vaga_id: UUID, _: UsuarioLogado, com_pdf: bool = True, para_fila: bool = True
) -> GeracaoResponse:
    try:
        g = await servico.gerar_curriculo(vaga_id, com_pdf=com_pdf, para_fila=para_fila)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except perfil.PerfilAusente as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return GeracaoResponse(
        vaga_id=str(vaga_id),
        curriculo=g.curriculo.como_json(),
        pdf=str(g.pdf) if g.pdf else None,
        acao_id=str(g.acao_id) if g.acao_id else None,
        rejeitados=g.curriculo.rejeitados,
        avisos=g.curriculo.avisos,
    )


@router.post("/{vaga_id}/evento", response_model=VagaResponse, summary="Registra o que aconteceu")
async def post_evento(vaga_id: UUID, req: EventoRequest, _: UsuarioLogado) -> VagaResponse:
    try:
        await vagas.registrar_evento(vaga_id, req.evento, detalhe=req.detalhe)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except vagas.VagaErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return VagaResponse(**_json(await vagas.obter(vaga_id)))
