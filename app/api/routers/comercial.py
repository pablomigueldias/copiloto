"""Rotas do CRM comercial — /api/comercial/*.

Empresas (Fase 1, passo 2): procurar na base e trazer para o CRM. Leads
(passo 3): listar, ver a ficha e pesquisar. Redator (passo 4): escrever o
e-mail 1 ou o lembrete para a fila, e marcar o aprovado como enviado. O cadastro
(`/crm/*`): empresas, contatos, negócios e atividades com CRUD, a ficha de cada
um com o que está ligado a ele, e o painel. As regras moram em
`app/comercial/crm/`; aqui só a porta.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.comercial import (
    AtividadeCrm,
    CamposRequest,
    Criado,
    EmpresaLinha,
    EnvieiRequest,
    EscreverRequest,
    EscreverResposta,
    InteracaoResponse,
    LeadDetalhe,
    LeadLinha,
    MoverRequest,
    NegocioCrm,
    PaginaContatosCrm,
    PaginaEmpresas,
    PaginaEmpresasCrm,
    PainelCrm,
    PesquisarRequest,
    PesquisarResposta,
    RascunhoResponse,
    RegistrarRequest,
    Registro,
    TarefaResponse,
    TipoRegistro,
    TrazerRequest,
    TrazerResposta,
)
from app.comercial.crm import cadastro, empresas, leads, pesquisador, redator
from app.db.models.auth.usuario import Usuario
from app.db.models.comercial.crm import Interacao, Lead, Tarefa
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


def _linha(lead: Lead) -> dict:
    return {
        "id": lead.id, "nome": lead.nome, "estagio": lead.estagio, "email": lead.email,
        "email_confirmado": lead.email_fonte is not None, "site": lead.site,
        "proxima_acao": lead.proxima_acao, "pesquisado_em": lead.pesquisado_em,
        "criado_em": lead.criado_em,
    }


async def _detalhe(session, lead_id: int) -> LeadDetalhe:
    lead = await session.get(Lead, lead_id, populate_existing=True)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} não existe")
    interacoes = await session.scalars(
        select(Interacao).where(Interacao.lead_id == lead_id).order_by(Interacao.criado_em.desc())
    )
    tarefas = await session.scalars(
        select(Tarefa).where(Tarefa.lead_id == lead_id).order_by(Tarefa.vence_em, Tarefa.id)
    )
    return LeadDetalhe(
        **_linha(lead),
        email_fonte=lead.email_fonte, telefone=lead.telefone, estabelecimento_id=lead.estabelecimento_id,
        interacoes=[InteracaoResponse.model_validate(i, from_attributes=True) for i in interacoes],
        tarefas=[TarefaResponse.model_validate(t, from_attributes=True) for t in tarefas],
        rascunhos=[
            RascunhoResponse.model_validate(r, from_attributes=True)
            for r in await redator.rascunhos(session, lead_id)
        ],
    )


@router.get("/leads", response_model=list[LeadLinha], summary="Os leads do CRM, mais novos primeiro")
async def get_leads(_: UsuarioLogado) -> list[LeadLinha]:
    async with get_session() as session:
        linhas = await session.scalars(select(Lead).order_by(Lead.criado_em.desc()).limit(500))
        return [LeadLinha(**_linha(lead)) for lead in linhas]


@router.get("/leads/{lead_id}", response_model=LeadDetalhe, summary="Um lead, com a ficha e a linha do tempo")
async def get_lead(lead_id: int, _: UsuarioLogado) -> LeadDetalhe:
    async with get_session() as session:
        return await _detalhe(session, lead_id)


@router.post("/leads/{lead_id}/pesquisar", response_model=PesquisarResposta, summary="Pesquisador: a ficha da clínica")
async def post_pesquisar(lead_id: int, req: PesquisarRequest, _: UsuarioLogado) -> PesquisarResposta:
    async with get_session() as session:
        try:
            r = await pesquisador.pesquisar(session, lead_id, site=req.site)
        except leads.CrmErro as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return PesquisarResposta(
            status=r.status, email_confirmado=r.email_confirmado,
            mensagem=r.mensagem or ("ficha pronta" if r.status == "ok" else ""),
            lead=await _detalhe(session, lead_id),
        )


@router.post("/leads/{lead_id}/escrever", response_model=EscreverResposta, summary="Redator: texto para a fila")
async def post_escrever(lead_id: int, req: EscreverRequest, _: UsuarioLogado) -> EscreverResposta:
    async with get_session() as session:
        try:
            r = await redator.escrever(session, lead_id, tipo=req.tipo)
        except redator.NaoPode as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except leads.CrmErro as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return EscreverResposta(acao_id=r.acao_id, avisos=r.avisos, lead=await _detalhe(session, lead_id))


@router.post("/leads/{lead_id}/enviei", response_model=LeadDetalhe, summary="Marcar o texto aprovado como enviado")
async def post_enviei(lead_id: int, req: EnvieiRequest, _: UsuarioLogado) -> LeadDetalhe:
    async with get_session() as session:
        try:
            await redator.enviei(session, lead_id, req.acao_id)
        except redator.NaoPode as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except leads.CrmErro as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        return await _detalhe(session, lead_id)


# ── o cadastro do CRM ──


def _erro(e: leads.CrmErro) -> HTTPException:
    if isinstance(e, cadastro.NaoAchei):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, (cadastro.NaoPode, leads.Suprimido, leads.JaNoCrm, leads.TransicaoInvalida)):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail=str(e))


@router.get("/crm/opcoes", summary="Os rótulos e as opções do CRM")
async def get_opcoes(_: UsuarioLogado) -> dict[str, dict[str, str]]:
    return cadastro.OPCOES


@router.get("/crm/painel", response_model=PainelCrm, summary="Visão geral do CRM")
async def get_painel(_: UsuarioLogado) -> PainelCrm:
    async with get_session() as session:
        return PainelCrm(**await cadastro.painel(session))


@router.get("/crm/empresas", response_model=PaginaEmpresasCrm, summary="Empresas do CRM")
async def get_empresas_crm(
    _: UsuarioLogado, busca: str | None = None, status: str | None = None
) -> PaginaEmpresasCrm:
    async with get_session() as session:
        total, itens = await cadastro.listar_empresas(session, busca=busca, status=status)
    return PaginaEmpresasCrm(total=total, itens=itens)


@router.get("/crm/contatos", response_model=PaginaContatosCrm, summary="Contatos do CRM")
async def get_contatos(
    _: UsuarioLogado, busca: str | None = None, empresa_id: int | None = None
) -> PaginaContatosCrm:
    async with get_session() as session:
        total, itens = await cadastro.listar_contatos(session, busca=busca, empresa_id=empresa_id)
    return PaginaContatosCrm(total=total, itens=itens)


@router.get("/crm/negocios", response_model=list[NegocioCrm], summary="Negócios, para o kanban e a lista")
async def get_negocios(
    _: UsuarioLogado, busca: str | None = None, empresa_id: int | None = None
) -> list[NegocioCrm]:
    async with get_session() as session:
        return [NegocioCrm(**n) for n in await cadastro.listar_negocios(session, busca=busca, empresa_id=empresa_id)]


@router.get("/crm/atividades", response_model=list[AtividadeCrm], summary="Atividades (tarefas)")
async def get_atividades(
    _: UsuarioLogado,
    situacao: Annotated[str, Query(description="abertas | atrasadas | feitas | todas")] = "abertas",
    lead_id: int | None = None,
) -> list[AtividadeCrm]:
    async with get_session() as session:
        try:
            itens = await cadastro.listar_atividades(session, situacao=situacao, lead_id=lead_id)
        except leads.CrmErro as e:
            raise _erro(e) from e
    return [AtividadeCrm(**a) for a in itens]


@router.post("/crm/{tipo}", response_model=Criado, status_code=201, summary="Criar")
async def post_registro(tipo: TipoRegistro, req: CamposRequest, _: UsuarioLogado) -> Criado:
    async with get_session() as session:
        try:
            return Criado(id=await cadastro.criar(session, tipo, req.campos))
        except leads.CrmErro as e:
            raise _erro(e) from e


@router.get("/crm/{tipo}/{id_}", response_model=Registro, summary="A ficha, com o que está ligado")
async def get_registro(tipo: TipoRegistro, id_: int, _: UsuarioLogado) -> Registro:
    async with get_session() as session:
        try:
            return Registro(**await cadastro.registro(session, tipo, id_))
        except leads.CrmErro as e:
            raise _erro(e) from e


@router.patch("/crm/{tipo}/{id_}", response_model=Registro, summary="Editar um ou mais campos")
async def patch_registro(tipo: TipoRegistro, id_: int, req: CamposRequest, _: UsuarioLogado) -> Registro:
    async with get_session() as session:
        try:
            await cadastro.editar(session, tipo, id_, req.campos)
            return Registro(**await cadastro.registro(session, tipo, id_))
        except leads.CrmErro as e:
            raise _erro(e) from e


@router.delete("/crm/{tipo}/{id_}", status_code=204, summary="Excluir")
async def delete_registro(tipo: TipoRegistro, id_: int, _: UsuarioLogado) -> Response:
    async with get_session() as session:
        try:
            await cadastro.excluir(session, tipo, id_)
        except leads.CrmErro as e:
            raise _erro(e) from e
    return Response(status_code=204)


@router.post("/crm/negocio/{id_}/mover", response_model=Registro, summary="Mudar o estágio, pela regra")
async def post_mover(id_: int, req: MoverRequest, _: UsuarioLogado) -> Registro:
    async with get_session() as session:
        try:
            await cadastro.mover(session, id_, req.para, req.motivo)
            return Registro(**await cadastro.registro(session, "negocio", id_))
        except leads.CrmErro as e:
            raise _erro(e) from e


@router.post("/crm/negocio/{id_}/registrar", response_model=Registro, summary="Nota ou contato feito fora")
async def post_registrar(id_: int, req: RegistrarRequest, _: UsuarioLogado) -> Registro:
    async with get_session() as session:
        try:
            await cadastro.registrar(session, id_, texto=req.texto, canal=req.canal, direcao=req.direcao)
            return Registro(**await cadastro.registro(session, "negocio", id_))
        except leads.CrmErro as e:
            raise _erro(e) from e
