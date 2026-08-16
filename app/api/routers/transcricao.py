"""Rotas da transcrição — `/api/transcricao/*`.

O botão de gravar do painel. A máquina de estados inteira mora em
`app/conhecimento/gravacao.py`; aqui só há a casca HTTP.

**Por que polling e não WebSocket.** A tela pergunta o estado de segundo em
segundo enquanto grava. Um WebSocket seria mais elegante e traria reconexão,
heartbeat e um caminho novo de autenticação — para transportar uma lista de
strings que cresce a cada 20 s. O `GET` custa 2 ms e usa a sessão que já existe.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.transcricao import (
    EstadoTranscricao,
    IniciarRequest,
    NotaSalva,
    SalvarRequest,
)
from app.conhecimento import gravacao
from app.conhecimento import transcricao as tr
from app.conhecimento.varredura import ingerir
from app.db.models.auth.usuario import Usuario
from app.utils.logger import get_logger

logger = get_logger()

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/transcricao", tags=["transcricao"])


@router.get("/estado", response_model=EstadoTranscricao, summary="O que está acontecendo")
async def get_estado(_: UsuarioLogado) -> EstadoTranscricao:
    return EstadoTranscricao(**gravacao.estado())


@router.get("/destinos", summary="Pastas e tags que o vault já tem")
async def get_destinos(_: UsuarioLogado) -> dict:
    """O cardápio do formulário de salvar.

    Serve para eu **reaproveitar** o que já existe em vez de criar
    `Estudos/Python` ao lado de `Pessoal/Python` — que é como um vault deixa de
    ser navegável.
    """
    raiz = gravacao.vault()
    return {
        "pastas": tr.pastas_do_vault(raiz),
        "tags": tr.tags_do_vault(raiz)[:60],
        "vault": str(raiz),
    }


@router.post("/iniciar", response_model=EstadoTranscricao, summary="Começa a gravar")
async def post_iniciar(req: IniciarRequest, _: UsuarioLogado) -> EstadoTranscricao:
    try:
        await gravacao.iniciar(req.fonte)
    except gravacao.GravacaoErro as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EstadoTranscricao(**gravacao.estado())


@router.post("/parar", response_model=EstadoTranscricao, summary="Encerra e organiza")
async def post_parar(_: UsuarioLogado) -> EstadoTranscricao:
    """Para a captura e devolve na hora; o LLM organiza em segundo plano.

    Se a reescrita rodasse aqui dentro, uma aula de uma hora estouraria o
    timeout do request — e eu perderia a gravação por causa da etapa cosmética.
    """
    try:
        await gravacao.parar()
    except gravacao.GravacaoErro as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EstadoTranscricao(**gravacao.estado())


@router.delete(
    "/trecho/{indice}",
    response_model=EstadoTranscricao,
    summary="Corta um trecho (o anúncio no meio do vídeo)",
)
async def delete_trecho(indice: int, _: UsuarioLogado) -> EstadoTranscricao:
    """Tira um pedaço da transcrição, enquanto ela ainda está acontecendo.

    Anúncio no meio da aula entra na nota e no índice, e depois volta como
    resposta quando eu perguntar alguma coisa. Cortar ao vivo — eu já estou
    olhando a tela — é mais barato que qualquer filtro automático, e não corre o
    risco de apagar conteúdo real.
    """
    try:
        await gravacao.descartar_trecho(indice)
    except gravacao.GravacaoErro as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EstadoTranscricao(**gravacao.estado())


@router.post("/salvar", response_model=NotaSalva, summary="Grava a nota no vault")
async def post_salvar(req: SalvarRequest, _: UsuarioLogado) -> NotaSalva:
    try:
        destino = await gravacao.salvar(
            titulo=req.titulo, pasta=req.pasta, tags=req.tags, nome=req.nome_arquivo
        )
    except gravacao.GravacaoErro as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    # Indexa só a nota nova (`--caminho`), que é instantâneo. Esperar o worker
    # significaria até 10 min até a nota poder ser perguntada — e a vontade de
    # perguntar é maior logo depois de assistir.
    indexado = 0
    try:
        for r in (await ingerir(tipos=["nota"], caminho=str(destino))).values():
            indexado += r.chunks
    except Exception as e:  # noqa: BLE001 — a nota já está salva; o índice espera o worker
        logger.warning(f"Nota salva mas não indexada agora ({type(e).__name__}: {e}).")

    return NotaSalva(caminho=str(destino), chunks=indexado)


@router.post("/descartar", status_code=204, response_model=None, summary="Joga fora a sessão")
async def post_descartar(_: UsuarioLogado) -> None:
    await gravacao.descartar()
