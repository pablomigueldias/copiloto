"""Rotas da redação — /api/blog/*.

A superfície do CMS: listar, ver, criar, salvar, mudar de estado, prever o MDX,
exportar, abrir PR e concluir a publicação.

**Abrir o PR e concluir são duas rotas, e é de propósito.** Nenhuma das duas
acontece sozinha, e a segunda recusa enquanto os checks não estiverem verdes.
O sistema faz os oito passos repetidos; a decisão de publicar continua sendo um
clique meu — a mesma regra da fila de aprovação, com o CI no meio.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.blog import (
    EdicaoPost,
    EstadoRequest,
    ExportacaoResponse,
    NovoPost,
    PaginaPosts,
    PostDetalhe,
    PostLinha,
    PrAbertoResponse,
    PreviaResponse,
    PreviaSiteResponse,
    PrResponse,
    PublicadoResponse,
    VersaoResponse,
    Vocabulario,
)
from app.blog import camadas as camadas_mod
from app.blog import fluxo, mdx, publicacao, servico
from app.blog import previa as previa_mod
from app.db.models.auth.usuario import Usuario

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/blog", tags=["blog"])


def _linha(post) -> dict:
    return {
        "id": str(post.id),
        "slug": post.slug,
        "titulo": post.titulo,
        "descricao": post.descricao,
        "estado": post.estado,
        "pilar": post.pilar,
        "tags": list(post.tags or []),
        "palavras": camadas_mod.palavras(post.corpo or ""),
        "camadas_ok": camadas_mod.tudo_verde(
            camadas_mod.analisar(
                corpo=post.corpo or "",
                descricao=post.descricao,
                tags=list(post.tags or []),
                origem=list(post.origem or []),
            )
        ),
        "data_publicacao": post.data_publicacao,
        "exportado_em": post.exportado_em,
        "pr_numero": post.pr_numero,
        "pr_url": post.pr_url,
        "publicado_em": post.publicado_em,
        "updated_at": post.updated_at,
    }


def _detalhe(post) -> dict:
    return {
        **_linha(post),
        "corpo": post.corpo or "",
        "notas": post.notas,
        "origem": list(post.origem or []),
        "diagnostico": servico.diagnostico(post),
        "created_at": post.created_at,
    }


@router.get("/vocabulario", response_model=Vocabulario, summary="Pilares, tags e limites do blog")
async def get_vocabulario(_: UsuarioLogado) -> Vocabulario:
    return Vocabulario()


@router.get("", response_model=PaginaPosts, summary="A redação inteira")
async def get_posts(
    _: UsuarioLogado,
    estado: Annotated[str | None, Query(description="pauta | rascunho | pronto | publicado | arquivado")] = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaPosts:
    try:
        total, itens = await servico.listar(estado=estado, limite=limite, offset=offset)
    except servico.EstadoInvalido as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return PaginaPosts(
        total=total,
        por_estado=await servico.contar_por_estado(),
        itens=[PostLinha(**_linha(p)) for p in itens],
    )


@router.post("", response_model=PostDetalhe, status_code=201, summary="Nova pauta")
async def post_post(req: NovoPost, _: UsuarioLogado) -> PostDetalhe:
    post = await servico.criar(
        titulo=req.titulo,
        pilar=req.pilar,
        corpo=req.corpo,
        notas=req.notas,
        origem=req.origem,
    )
    return PostDetalhe(**_detalhe(post))


@router.get("/{post_id}", response_model=PostDetalhe, summary="Um post, com o diagnóstico")
async def get_post(post_id: UUID, _: UsuarioLogado) -> PostDetalhe:
    try:
        return PostDetalhe(**_detalhe(await servico.obter(post_id)))
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{post_id}", response_model=PostDetalhe, summary="Salvar")
async def patch_post(post_id: UUID, req: EdicaoPost, _: UsuarioLogado) -> PostDetalhe:
    campos = req.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(status_code=422, detail="nada para salvar")
    try:
        post = await servico.salvar(post_id, campos)
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.BlogErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return PostDetalhe(**_detalhe(post))


@router.post("/{post_id}/estado", response_model=PostDetalhe, summary="Mudar de estado")
async def post_estado(post_id: UUID, req: EstadoRequest, _: UsuarioLogado) -> PostDetalhe:
    """`pronto` só entra com as camadas verdes — o 409 lista o que falta."""
    try:
        post = await servico.mudar_estado(post_id, req.estado)
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.NaoEstaPronto as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except servico.EstadoInvalido as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return PostDetalhe(**_detalhe(post))


@router.get("/{post_id}/versoes", response_model=list[VersaoResponse], summary="O corpo de antes")
async def get_versoes(post_id: UUID, _: UsuarioLogado) -> list[VersaoResponse]:
    return [
        VersaoResponse(
            numero=v.numero, titulo=v.titulo, palavras=v.palavras, criada_em=v.criada_em
        )
        for v in await servico.versoes(post_id)
    ]


@router.get("/{post_id}/previa", response_model=PreviaResponse, summary="O MDX que sairia")
async def get_previa(post_id: UUID, _: UsuarioLogado) -> PreviaResponse:
    try:
        return PreviaResponse(mdx=servico.previa(await servico.obter(post_id)))
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/{post_id}/previa-no-site",
    response_model=PreviaSiteResponse,
    summary="Ver como fica, no blog de verdade",
)
async def post_previa_no_site(post_id: UUID, _: UsuarioLogado) -> PreviaSiteResponse:
    """Escreve o rascunho no repo do blog, regera o índice e devolve a URL.

    O 422 aqui costuma ser útil: quem reprova é o gerador do blog, que roda o
    linter de privacidade e a validação de frontmatter. Ver o erro na prévia é
    melhor do que vê-lo no CI de um PR.
    """
    try:
        return PreviaSiteResponse(
            **await previa_mod.montar(await servico.obter(post_id))
        )
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (previa_mod.PreviaErro, mdx.ExportacaoErro) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except FileNotFoundError as e:
        # `npm` fora do PATH do processo da API — acontece quando o uvicorn sobe
        # de um ambiente sem o node carregado, e o erro cru não diz isso.
        raise HTTPException(
            status_code=422, detail="não achei o `npm` no PATH para regerar o índice do blog"
        ) from e


@router.post(
    "/{post_id}/pr", response_model=PrAbertoResponse, summary="Abrir o PR do post"
)
async def post_pr(post_id: UUID, _: UsuarioLogado) -> PrAbertoResponse:
    """Branch da `origin/main`, commit do `.mdx`, push e PR. Não mergeia.

    Só o arquivo deste post entra no commit — o resto do working tree do blog
    fica onde está.
    """
    try:
        return PrAbertoResponse(**await fluxo.abrir_pr(post_id))
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.NaoEstaPronto as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (publicacao.PublicacaoErro, mdx.ExportacaoErro) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=422,
            detail="não achei o `git` ou o `gh` no PATH do processo da API",
        ) from e


@router.get("/{post_id}/pr", response_model=PrResponse, summary="Situação do PR")
async def get_pr(post_id: UUID, _: UsuarioLogado) -> PrResponse:
    try:
        return PrResponse(**await fluxo.situacao(post_id))
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except publicacao.PublicacaoErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post(
    "/{post_id}/publicar",
    response_model=PublicadoResponse,
    summary="Concluir: fecha o PR na main e o post vai ao ar",
)
async def post_publicar(post_id: UUID, _: UsuarioLogado) -> PublicadoResponse:
    """O 422 aqui é o freio: sem os checks verdes, não fecha.

    Depois disto o deploy de produção é do Workers Builds da Cloudflare, que
    escuta a `main` — leva uns minutos, e não passa por aqui.
    """
    try:
        return PublicadoResponse(**await fluxo.concluir(post_id))
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except publicacao.PublicacaoErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/{post_id}/exportar", response_model=ExportacaoResponse, summary="Escrever o .mdx")
async def post_exportar(post_id: UUID, _: UsuarioLogado) -> ExportacaoResponse:
    """Escreve o arquivo no `content/blog/` do repo do blog. Não faz commit."""
    try:
        return ExportacaoResponse(**await servico.exportar(post_id))
    except servico.PostNaoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except mdx.ExportacaoErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
