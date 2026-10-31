"""Rotas do simulado — /api/estudo/simulado/*.

O mesmo princípio da revisão, mais forte: durante a prova o gabarito não sai do
servidor. `GET /{id}` de um simulado em andamento devolve a questão sem
gabarito, sem explicação e sem o assunto — o assunto no topo da questão já é
meia resposta. Depois de entregue, a mesma rota devolve tudo.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies.auth import usuario_atual
from app.db.models.auth.usuario import Usuario
from app.estudo import simulado as servico
from app.estudo.servico import EstudoErro

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/estudo/simulado", tags=["simulado"])


class MarcarRequest(BaseModel):
    # `null` desmarca: na prova de papel, apagar a bolinha também existe.
    resposta: str | None = Field(default=None, pattern="^[A-E]$")


class ResponderReforcoRequest(BaseModel):
    resposta: str = Field(pattern="^[A-E]$")


def _http(e: EstudoErro) -> HTTPException:
    if isinstance(e, servico.SimuladoNaoEncontrado | servico.ReforcoNaoEncontrado):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, servico.SimuladoBloqueado | servico.EstadoInvalido):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail=str(e))


@router.get("", summary="Onde estou no ciclo: prova, reforço ou liberado")
async def get_estado(_: UsuarioLogado) -> dict:
    return await servico.estado()


@router.post("", status_code=201, summary="Monta o próximo simulado")
async def post_simulado(_: UsuarioLogado) -> dict:
    """409 enquanto houver reforço pendente — é a trava do ciclo."""
    try:
        sim = await servico.iniciar()
    except EstudoErro as e:
        raise _http(e) from e
    return await servico.obter(sim.id)


@router.post("/reforcos/gerar", summary="Gera as questões de todo reforço pendente")
async def post_gerar_todos(_: UsuarioLogado) -> list[dict]:
    """Dispara e volta na hora: a escrita leva minutos e roda fora da API."""
    try:
        return await servico.gerar_pendentes()
    except EstudoErro as e:
        raise _http(e) from e


@router.post("/reforco/{reforco_id}/gerar", summary="Gera as 5 questões deste reforço")
async def post_gerar(reforco_id: UUID, _: UsuarioLogado) -> list[dict]:
    try:
        return await servico.gerar([reforco_id])
    except EstudoErro as e:
        raise _http(e) from e


@router.get("/reforco/{reforco_id}", summary="As 5 questões de um reforço")
async def get_reforco(reforco_id: UUID, _: UsuarioLogado) -> dict:
    try:
        return await servico.obter_reforco(reforco_id)
    except EstudoErro as e:
        raise _http(e) from e


@router.post("/reforco/{reforco_id}/{ordem}", summary="Responde e corrige na hora")
async def post_reforco(
    reforco_id: UUID, ordem: int, req: ResponderReforcoRequest, _: UsuarioLogado
) -> dict:
    try:
        return await servico.responder_reforco(reforco_id, ordem, req.resposta)
    except EstudoErro as e:
        raise _http(e) from e


@router.get("/{simulado_id}", summary="O caderno — sem gabarito até entregar")
async def get_simulado(simulado_id: UUID, _: UsuarioLogado) -> dict:
    try:
        return await servico.obter(simulado_id)
    except EstudoErro as e:
        raise _http(e) from e


@router.put("/{simulado_id}/{ordem}", summary="Marca a alternativa (sem corrigir)")
async def put_resposta(
    simulado_id: UUID, ordem: int, req: MarcarRequest, _: UsuarioLogado
) -> dict:
    try:
        return await servico.marcar(simulado_id, ordem, req.resposta)
    except EstudoErro as e:
        raise _http(e) from e


@router.post("/{simulado_id}/entregar", summary="Entrega: nota do edital e diagnóstico")
async def post_entregar(simulado_id: UUID, _: UsuarioLogado) -> dict:
    try:
        return await servico.finalizar(simulado_id)
    except EstudoErro as e:
        raise _http(e) from e


@router.get("/{simulado_id}/resultado", summary="Nota, matéria a matéria, e o que errei")
async def get_resultado(simulado_id: UUID, _: UsuarioLogado) -> dict:
    try:
        return await servico.resultado(simulado_id)
    except EstudoErro as e:
        raise _http(e) from e
