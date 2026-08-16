"""Rotas da fila de aprovação — /api/fila/*.

Três rotas e nada mais: listar, ver, decidir. É a superfície mínima que a F5 vai
usar, e cada coisa a mais aqui (prioridade, adiar, reabrir) seria inventada
antes de existir um caso que peça.

**Não existe rota de executar.** Ação aprovada fica marcada como aprovada; quem
manda o e-mail é o executor da F6, quando houver e-mail para mandar.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.fila import AcaoResponse, DecisaoRequest, PaginaFila
from app.db.models.acao_pendente import STATUS
from app.db.models.auth.usuario import Usuario
from app.fila import servico

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/fila", tags=["fila"])


def _json(acao) -> dict:
    return {**{c: getattr(acao, c) for c in AcaoResponse.model_fields if c != "id"},
            "id": str(acao.id)}


@router.get("", response_model=PaginaFila, summary="O que está esperando decisão")
async def get_fila(
    _: UsuarioLogado,
    status: Annotated[str | None, Query(description="pendente | aprovada | editada | rejeitada")] = "pendente",
    agente: str | None = None,
    tipo: str | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaFila:
    if status and status not in STATUS:
        raise HTTPException(
            status_code=422, detail=f"status inválido: {status}. Use um de {list(STATUS)}."
        )

    total, itens = await servico.listar(
        status=status, agente=agente, tipo=tipo, limite=limite, offset=offset
    )
    return PaginaFila(
        total=total,
        por_status=await servico.contar_por_status(),
        itens=[_json(a) for a in itens],
    )


@router.get("/{acao_id}", response_model=AcaoResponse, summary="Uma ação, inteira")
async def get_acao(acao_id: UUID, _: UsuarioLogado) -> AcaoResponse:
    try:
        return AcaoResponse(**_json(await servico.obter(acao_id)))
    except servico.AcaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{acao_id}/decidir", response_model=AcaoResponse, summary="Aprovar, editar ou rejeitar")
async def post_decidir(
    acao_id: UUID, req: DecisaoRequest, _: UsuarioLogado
) -> AcaoResponse:
    """Decisão é transição de estado — acontece uma vez.

    Decidir algo já decidido é `409`, e não sobrescrita: o par de treino não
    pode mudar de valor depois de contado.
    """
    try:
        acao = await servico.decidir(
            acao_id,
            decisao=req.decisao,
            texto_final=req.texto_final,
            motivo=req.motivo,
        )
    except servico.AcaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.JaDecidida as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return AcaoResponse(**_json(acao))
