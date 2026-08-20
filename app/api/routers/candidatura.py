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
from fastapi.responses import FileResponse, Response

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.candidatura import (
    CurriculoTexto,
    CurriculoTextoResponse,
    EventoRequest,
    GeracaoResponse,
    MetricasResponse,
    PaginaVagas,
    VagaDetalheResponse,
    VagaLinha,
    VagaPatch,
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


def _linha(v) -> VagaLinha:
    """A vaga enxuta da listagem. Ver `VagaLinha` para o porquê."""
    return VagaLinha(
        **{
            c: getattr(v, c)
            for c in VagaLinha.model_fields
            if c not in ("id", "tem_curriculo")
        },
        id=str(v.id),
        tem_curriculo=v.curriculo_json is not None,
    )


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
    return PaginaVagas(total=total, itens=[_linha(v) for v in itens])


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


@router.patch("/{vaga_id}", response_model=VagaResponse, summary="Corrige campos da vaga")
async def patch_vaga(vaga_id: UUID, req: VagaPatch, _: UsuarioLogado) -> VagaResponse:
    """Edição campo a campo, direto do painel.

    `exclude_unset` é o que separa "não mandei este campo" de "mandei vazio para
    limpar" — sem ele, salvar o título apagaria a empresa.
    """
    campos = req.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(status_code=422, detail="Nada para atualizar.")
    try:
        vaga = await vagas.atualizar(vaga_id, campos)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except vagas.VagaErro as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return VagaResponse(**_json(vaga))


@router.delete(
    "/{vaga_id}",
    status_code=204,
    # 204 não tem corpo, por definição. Sem `response_model=None` explícito
    # esta versão do FastAPI infere um modelo da anotação e recusa a rota no
    # import — quebrando a aplicação inteira, não só esta rota.
    response_model=None,
    response_class=Response,
    summary="Apaga a vaga e o histórico dela",
)
async def delete_vaga(vaga_id: UUID, _: UsuarioLogado) -> None:
    """Vaga colada errada ficava para sempre — não havia como remover.

    Leva o histórico junto (`ON DELETE CASCADE`), e é irreversível: quem
    confirma é a tela, com o aviso de que os eventos vão junto.
    """
    try:
        await vagas.apagar(vaga_id)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


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
    vaga_id: UUID,
    _: UsuarioLogado,
    com_pdf: bool = True,
    para_fila: bool = True,
    reanalisar: bool = False,
) -> GeracaoResponse:
    """Gera o currículo. Com `reanalisar=true`, é o botão "analisar + gerar".

    O combo existe porque as duas etapas quase sempre andam juntas depois de eu
    editar a descrição da vaga — e duas chamadas do painel deixariam a tela
    mostrando um currículo novo com o score velho no meio do caminho.
    """
    try:
        if reanalisar:
            await servico.analisar(vaga_id, forcar=True)
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
        vaga=VagaResponse(**_json(await vagas.obter(vaga_id))),
    )


@router.get(
    "/{vaga_id}/curriculo.pdf",
    response_class=FileResponse,
    summary="Baixa o PDF do currículo gerado",
)
async def get_curriculo_pdf(vaga_id: UUID, _: UsuarioLogado) -> FileResponse:
    """O arquivo, para conferir a formatação com os próprios olhos.

    É `GET` e devolve o PDF direto: assim o link abre no visualizador do
    navegador, que é onde dá para ver se o layout quebrou — e o ATS lê o mesmo
    arquivo que eu estou vendo.
    """
    try:
        caminho, nome = await servico.pdf_da_vaga(vaga_id)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.SemCurriculo as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except perfil.PerfilAusente as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    # `inline` para abrir na aba; o navegador ainda oferece salvar.
    return FileResponse(
        caminho,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nome}"'},
    )


@router.get(
    "/{vaga_id}/curriculo.txt",
    response_model=CurriculoTextoResponse,
    summary="O currículo em texto, para editar",
)
async def get_curriculo_texto(vaga_id: UUID, _: UsuarioLogado) -> CurriculoTextoResponse:
    """O que a gaveta abre no editor.

    Sai do `curriculo_json`, a mesma fonte que o `curriculo.pdf` reimprime — o
    que eu leio aqui é o que sai no papel.
    """
    try:
        texto = await servico.texto_do_curriculo(vaga_id)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.SemCurriculo as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except perfil.PerfilAusente as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return CurriculoTextoResponse(vaga_id=str(vaga_id), texto=texto)


@router.put(
    "/{vaga_id}/curriculo",
    response_model=CurriculoTextoResponse,
    summary="Salva o currículo que eu editei à mão",
)
async def put_curriculo_texto(
    vaga_id: UUID, req: CurriculoTexto, _: UsuarioLogado
) -> CurriculoTextoResponse:
    """Substitui o texto do currículo e reimprime o PDF.

    `PUT` e não `PATCH`: o corpo é o documento inteiro, não um pedaço dele.

    **A anti-alucinação não roda aqui, e é deliberado.** Ela existe para impedir
    que o *modelo* invente tecnologia que eu não tenho; quem escreveu agora fui
    eu, que sou a autoridade sobre o meu próprio currículo. Rejeitar o meu texto
    porque ele cita algo fora do Perfil Mestre seria o filtro trabalhando contra
    o dono dele — o certo é o perfil ganhar o dado que falta.

    Devolve o texto relido do JSON gravado, e não o que foi enviado: o que o
    `de_texto` não conseguiu ler continua como estava, e a tela precisa mostrar
    o que ficou de verdade.
    """
    try:
        caminho = await servico.aplicar_texto_aprovado(vaga_id, req.texto, origem="painel")
        texto = await servico.texto_do_curriculo(vaga_id)
    except vagas.VagaNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.SemCurriculo as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except perfil.PerfilAusente as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return CurriculoTextoResponse(
        vaga_id=str(vaga_id), texto=texto, pdf=str(caminho) if caminho else None
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
