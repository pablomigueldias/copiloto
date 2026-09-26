"""Rotas do CRM comercial — /api/comercial/*.

Por ora, a tela Empresas (Fase 1, passo 2): procurar na base de prospecção e
trazer para o CRM. As regras moram em `app/comercial/crm/`; aqui só a porta.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.comercial import (
    EmpresaLinha,
    PaginaEmpresas,
    TrazerRequest,
    TrazerResposta,
)
from app.comercial.crm import empresas, leads
from app.db.models.auth.usuario import Usuario
from app.db.session import get_session

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/comercial", tags=["comercial"])


@router.get("/empresas", response_model=PaginaEmpresas, summary="Procurar na base de prospecção")
async def get_empresas(
    _: UsuarioLogado,
    termo: str = "psic",
    segmento: Annotated[str | None, Query(description="clinica_especialidade | consultorio_isolado | todos")] = "clinica_especialidade",
    bairro: str | None = None,
    so_com_email: bool = True,
    incluir_no_crm: bool = True,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaEmpresas:
    if segmento == "todos":
        segmento = None
    elif segmento and segmento not in empresas.SEGMENTOS:
        raise HTTPException(status_code=422, detail=f"segmento inválido: {segmento}")
    async with get_session() as session:
        total, linhas = await empresas.buscar(
            session, termo=termo, segmento=segmento or None, bairro=bairro,
            so_com_email=so_com_email, incluir_no_crm=incluir_no_crm, limite=limite, offset=offset,
        )
    return PaginaEmpresas(total=total, itens=[EmpresaLinha(**vars(linha)) for linha in linhas])


@router.post("/empresas/trazer", response_model=TrazerResposta, summary="Trazer para o CRM")
async def post_trazer(req: TrazerRequest, _: UsuarioLogado) -> TrazerResposta:
    async with get_session() as session:
        try:
            r = await empresas.trazer(session, req.ids, confirmar_pessoa_fisica=req.confirmar_pessoa_fisica)
        except leads.CrmErro as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    return TrazerResposta(trazidos=r.trazidos, pulados=r.pulados)
