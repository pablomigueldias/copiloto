"""Rotas do conhecimento — /api/conhecimento/*.

Busca e inventário. **Não há endpoint de indexação** de propósito: uma varredura
leva minutos e prende a GPU, e request HTTP não é lugar para isso. Até o worker
da F4 existir, quem indexa é `python scripts/ingerir.py`.

Tudo atrás de sessão: o índice guarda notas pessoais, Perfil Mestre e vagas
inteiras — é o material mais privado do sistema depois de `ai_calls`.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.conhecimento import (
    BuscaResponse,
    InventarioResponse,
    RemocaoResponse,
)
from app.conhecimento.busca import buscar
from app.conhecimento.indexador import apagar_fonte, inventario, totais_por_tipo
from app.conhecimento.varredura import TIPOS
from app.db.models.auth.usuario import Usuario

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/conhecimento", tags=["conhecimento"])


@router.get("/buscar", response_model=BuscaResponse, summary="Busca híbrida no conhecimento")
async def get_buscar(
    _: UsuarioLogado,
    q: Annotated[str, Query(min_length=2, description="A pergunta, em linguagem natural")],
    fonte_tipo: Annotated[list[str] | None, Query(description="Filtra por tipo de fonte")] = None,
    tag: Annotated[list[str] | None, Query(description="Filtra por tag do frontmatter")] = None,
    limite: Annotated[int, Query(ge=1, le=50)] = 5,
) -> BuscaResponse:
    if fonte_tipo:
        invalidos = [t for t in fonte_tipo if t not in TIPOS]
        if invalidos:
            raise HTTPException(
                status_code=422,
                detail=f"fonte_tipo inválido: {', '.join(invalidos)}. Use um de {list(TIPOS)}.",
            )

    trechos = await buscar(q, limite=limite, fonte_tipo=fonte_tipo, tags=tag)
    return BuscaResponse(
        consulta=q,
        total=len(trechos),
        trechos=[
            {
                **asdict(t),
                "id": str(t.id),
                # Propriedade, não campo: `asdict` não a traz.
                "origem": t.origem,
            }
            for t in trechos
        ],
    )


@router.get("/fontes", response_model=InventarioResponse, summary="O que está indexado")
async def get_fontes(
    _: UsuarioLogado,
    fonte_tipo: str | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InventarioResponse:
    total, fontes = await inventario(fonte_tipo=fonte_tipo, limite=limite, offset=offset)
    return InventarioResponse(
        total=total,
        chunks_por_tipo=await totais_por_tipo(),
        itens=[asdict(f) for f in fontes],
    )


@router.delete("/fonte", response_model=RemocaoResponse, summary="Tira uma fonte do índice")
async def delete_fonte(
    _: UsuarioLogado,
    # Query, e não caminho na URL: `fonte_ref` é um caminho de arquivo cheio de
    # barras, e `/fonte/{ref}` viraria rota aninhada em vez de parâmetro.
    fonte_tipo: Annotated[str, Query()],
    fonte_ref: Annotated[str, Query()],
) -> RemocaoResponse:
    removidos = await apagar_fonte(fonte_tipo, fonte_ref)
    if not removidos:
        raise HTTPException(status_code=404, detail="Fonte não encontrada no índice.")
    return RemocaoResponse(
        fonte_tipo=fonte_tipo, fonte_ref=fonte_ref, chunks_removidos=removidos
    )
