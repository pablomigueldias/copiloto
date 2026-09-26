"""Rotas do quadro de pendências — /api/pendencias/*.

Quatro rotas: o quadro inteiro, criar, editar (inclui mover de coluna) e apagar.
Mover é só uma edição de `coluna` e `ordem`; rota própria para isso seria uma
segunda porta para a mesma regra de `concluida_em`.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.pendencias import (
    PendenciaEdicao,
    PendenciaNova,
    PendenciaResponse,
    Quadro,
)
from app.db.models.auth.usuario import Usuario
from app.pendencias import servico

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/pendencias", tags=["pendencias"])


def _json(p) -> PendenciaResponse:
    campos = {c: getattr(p, c) for c in PendenciaResponse.model_fields if c != "id"}
    return PendenciaResponse(id=str(p.id), **campos)


@router.get("", response_model=Quadro, summary="O quadro inteiro")
async def get_quadro(_: UsuarioLogado, topico: str | None = None) -> Quadro:
    itens = await servico.listar(topico=topico)
    return Quadro(topicos=await servico.topicos(), itens=[_json(p) for p in itens])


@router.post("", response_model=PendenciaResponse, status_code=201, summary="Cartão novo")
async def post_pendencia(req: PendenciaNova, _: UsuarioLogado) -> PendenciaResponse:
    try:
        return _json(await servico.criar(**req.model_dump()))
    except servico.PendenciaErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.patch("/{pendencia_id}", response_model=PendenciaResponse, summary="Editar ou mover")
async def patch_pendencia(
    pendencia_id: UUID, req: PendenciaEdicao, _: UsuarioLogado
) -> PendenciaResponse:
    try:
        p = await servico.atualizar(pendencia_id, **req.model_dump(exclude_unset=True))
    except servico.PendenciaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.PendenciaErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _json(p)


@router.delete("/{pendencia_id}", status_code=204, summary="Apagar")
async def delete_pendencia(pendencia_id: UUID, _: UsuarioLogado) -> Response:
    try:
        await servico.apagar(pendencia_id)
    except servico.PendenciaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)
