"""Rotas do estudo — /api/estudo/*.

A tela de revisão faz três chamadas e nada mais: pega a fila, responde, adia.
Tudo que decide certo ou errado acontece no servidor, e por um motivo que não é
segurança e sim honestidade: se o gabarito viajasse junto com a questão, ele
estaria no DevTools, e a diferença entre "eu sabia" e "eu vi" sumiria do
histórico — que é justamente o que agenda a próxima revisão.

Por isso `QuestaoResponse.gabarito` só é preenchido na listagem (onde eu estou
conferindo o acervo) e nunca na fila (onde eu estou respondendo).
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.estudo import (
    AdiarRequest,
    AgendaSimples,
    Apagado,
    FilaResponse,
    ModuloCriado,
    ModuloPatch,
    ModuloRequest,
    ModuloResumo,
    PaginaQuestoes,
    QuestaoPatch,
    QuestaoRequest,
    QuestaoResponse,
    RespostaRequest,
    RespostaResponse,
    ResumoResponse,
    TentativaResponse,
    TopicoCriado,
    TopicoPatch,
    TopicoRequest,
)
from app.db.models.auth.usuario import Usuario
from app.db.models.estudo.questao import FORMATOS, TRILHAS, Questao
from app.estudo import servico

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/estudo", tags=["estudo"])


def _json(q: Questao, *, com_gabarito: bool = False) -> dict:
    agenda = q.agenda
    return {
        "id": str(q.id),
        "formato": q.formato,
        "modulo": q.topico.modulo.nome,
        "topico": q.topico.nome,
        "topico_id": str(q.topico_id),
        "comando": q.comando,
        "enunciado": q.enunciado,
        "texto_base": q.texto_base,
        "texto_base_fonte": q.texto_base_fonte,
        "codigo": q.codigo,
        "linguagem": q.linguagem,
        "alternativas": q.alternativas or [],
        "afirmacoes": q.afirmacoes or [],
        # A explicação só existe depois que eu escrevo. Ela viaja na listagem
        # (onde eu edito) e na resposta (depois de responder) — nunca antes.
        "explicacao": q.explicacao if com_gabarito else None,
        "origem": q.origem,
        "fonte": q.fonte,
        "dificuldade": q.dificuldade,
        "gabarito": q.gabarito if com_gabarito else None,
        "agenda": (
            {
                "proxima_em": agenda.proxima_em,
                "ultima_em": agenda.ultima_em,
                "intervalo_dias": agenda.intervalo_dias,
                "acertos_seguidos": agenda.acertos_seguidos,
                "total_acertos": agenda.total_acertos,
                "total_erros": agenda.total_erros,
                "estado": agenda.estado,
            }
            if agenda
            else None
        ),
    }


@router.get("/resumo", response_model=ResumoResponse, summary="Quantas voltam hoje")
async def get_resumo(_: UsuarioLogado) -> ResumoResponse:
    return ResumoResponse(**await servico.resumo())


@router.get("/modulos", response_model=list[ModuloResumo], summary="Módulos e tópicos")
async def get_modulos(_: UsuarioLogado) -> list[ModuloResumo]:
    return [ModuloResumo(**m) for m in await servico.modulos()]


@router.get("/formatos", summary="Os formatos que a tela sabe montar")
async def get_formatos(_: UsuarioLogado) -> dict:
    return {"formatos": list(FORMATOS), "trilhas": list(TRILHAS)}


def _erros_de_nome(e: Exception) -> HTTPException:
    """409 para nome em uso, 422 para entrada inválida — a tela trata diferente."""
    if isinstance(e, servico.NomeEmUso):
        return HTTPException(status_code=409, detail=str(e))
    return HTTPException(status_code=422, detail=str(e))


@router.post(
    "/modulos", response_model=ModuloCriado, status_code=201, summary="Cria um módulo"
)
async def post_modulo(req: ModuloRequest, _: UsuarioLogado) -> ModuloCriado:
    """Uma matéria nova — 'Estatística', 'Python'.

    Nasce vazia: módulo sem tópico não recebe questão, e é a tela que leva ao
    próximo passo.
    """
    try:
        m = await servico.criar_modulo(
            nome=req.nome, trilha=req.trilha, ordem=req.ordem
        )
    except (servico.NomeEmUso, servico.RespostaInvalida) as e:
        raise _erros_de_nome(e) from e
    return ModuloCriado(id=str(m.id), nome=m.nome, trilha=m.trilha, ordem=m.ordem)


@router.patch("/modulos/{modulo_id}", response_model=ModuloCriado, summary="Renomeia o módulo")
async def patch_modulo(
    modulo_id: UUID, req: ModuloPatch, _: UsuarioLogado
) -> ModuloCriado:
    try:
        m = await servico.atualizar_modulo(modulo_id, req.model_dump(exclude_unset=True))
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (servico.NomeEmUso, servico.RespostaInvalida) as e:
        raise _erros_de_nome(e) from e
    return ModuloCriado(id=str(m.id), nome=m.nome, trilha=m.trilha, ordem=m.ordem)


@router.delete("/modulos/{modulo_id}", response_model=Apagado, summary="Apaga o módulo")
async def delete_modulo(
    modulo_id: UUID,
    _: UsuarioLogado,
    forcar: Annotated[
        bool, Query(description="Apaga mesmo com questões dentro — leva o histórico junto")
    ] = False,
) -> Apagado:
    """Recusa por padrão quando há questões dentro.

    O cascade leva tópicos, questões, agendas e **todo o histórico de
    tentativas**. Meses de repetição espaçada são a única coisa aqui que não se
    refaz — um clique distraído não pode bastar. A tela pergunta com o número
    na mão antes de reenviar com `forcar`.
    """
    try:
        n = await servico.apagar_modulo(modulo_id, forcar=forcar)
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.NaoVazio as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return Apagado(questoes_apagadas=n)


@router.post(
    "/modulos/{modulo_id}/topicos",
    response_model=TopicoCriado,
    status_code=201,
    summary="Cria um tópico no módulo",
)
async def post_topico(
    modulo_id: UUID, req: TopicoRequest, _: UsuarioLogado
) -> TopicoCriado:
    try:
        t = await servico.criar_topico(
            modulo_id=modulo_id, nome=req.nome, ordem=req.ordem
        )
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (servico.NomeEmUso, servico.RespostaInvalida) as e:
        raise _erros_de_nome(e) from e
    return TopicoCriado(
        id=str(t.id), modulo_id=str(t.modulo_id), nome=t.nome, ordem=t.ordem
    )


@router.patch("/topicos/{topico_id}", response_model=TopicoCriado, summary="Renomeia o tópico")
async def patch_topico(
    topico_id: UUID, req: TopicoPatch, _: UsuarioLogado
) -> TopicoCriado:
    try:
        t = await servico.atualizar_topico(topico_id, req.model_dump(exclude_unset=True))
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (servico.NomeEmUso, servico.RespostaInvalida) as e:
        raise _erros_de_nome(e) from e
    return TopicoCriado(
        id=str(t.id), modulo_id=str(t.modulo_id), nome=t.nome, ordem=t.ordem
    )


@router.delete("/topicos/{topico_id}", response_model=Apagado, summary="Apaga o tópico")
async def delete_topico(
    topico_id: UUID,
    _: UsuarioLogado,
    forcar: bool = False,
) -> Apagado:
    try:
        n = await servico.apagar_topico(topico_id, forcar=forcar)
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.NaoVazio as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return Apagado(questoes_apagadas=n)


@router.get("/fila", response_model=FilaResponse, summary="A revisão de hoje")
async def get_fila(
    _: UsuarioLogado,
    topico_id: UUID | None = None,
    modulo_id: UUID | None = None,
    questao_id: Annotated[
        UUID | None, Query(description="Uma questão só — o botão 'responder' do acervo")
    ] = None,
    todas: Annotated[
        bool, Query(description="Ignora o agendamento e traz o tópico inteiro")
    ] = False,
    limite: Annotated[int, Query(ge=1, le=100)] = 24,
) -> FilaResponse:
    """Sem `todas`, só o que vence hoje. Com, o tópico inteiro.

    Responder fora da data conta igual — a tentativa entra no log e reagenda. O
    agendamento diz o mínimo que eu preciso rever; não o máximo que eu posso.
    """
    itens = await servico.fila(
        topico_id=topico_id,
        modulo_id=modulo_id,
        questao_id=questao_id,
        todas=todas,
        limite=limite,
    )
    return FilaResponse(total=len(itens), itens=[_json(q) for q in itens])


@router.get("/questoes", response_model=PaginaQuestoes, summary="O acervo")
async def get_questoes(
    _: UsuarioLogado,
    topico_id: UUID | None = None,
    modulo_id: UUID | None = None,
    busca: str | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginaQuestoes:
    total, itens = await servico.listar(
        topico_id=topico_id, modulo_id=modulo_id, busca=busca, limite=limite, offset=offset
    )
    return PaginaQuestoes(
        total=total, itens=[_json(q, com_gabarito=True) for q in itens]
    )


@router.post("/questoes", response_model=QuestaoResponse, status_code=201, summary="Cadastra uma questão")
async def post_questao(req: QuestaoRequest, _: UsuarioLogado) -> QuestaoResponse:
    dados = req.model_dump()
    dados["topico_id"] = UUID(dados["topico_id"])
    try:
        questao = await servico.criar_questao(dados)
    except servico.RespostaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return QuestaoResponse(**_json(questao, com_gabarito=True))


@router.get("/questoes/{questao_id}", response_model=QuestaoResponse, summary="Uma questão")
async def get_questao(questao_id: UUID, _: UsuarioLogado) -> QuestaoResponse:
    try:
        questao = await servico.obter(questao_id)
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return QuestaoResponse(**_json(questao, com_gabarito=True))


@router.patch("/questoes/{questao_id}", response_model=QuestaoResponse, summary="Corrige a questão")
async def patch_questao(
    questao_id: UUID, req: QuestaoPatch, _: UsuarioLogado
) -> QuestaoResponse:
    """Onde a explicação entra.

    O acervo importado dos PDFs vem sem justificativa — a banca publica gabarito,
    não razão. Escrever uma e apresentá-la como da banca seria inventar fonte;
    escrever a minha depois de errar é estudar.
    """
    try:
        questao = await servico.atualizar_questao(questao_id, req.model_dump())
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return QuestaoResponse(**_json(questao, com_gabarito=True))


@router.post(
    "/questoes/{questao_id}/responder",
    response_model=RespostaResponse,
    summary="Responde e reagenda",
)
async def post_responder(
    questao_id: UUID, req: RespostaRequest, _: UsuarioLogado
) -> RespostaResponse:
    try:
        return RespostaResponse(
            **await servico.responder(
                questao_id,
                resposta=req.resposta,
                tentativa_n=req.tentativa_n,
                segundos=req.segundos,
            )
        )
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except servico.RespostaInvalida as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post(
    "/questoes/{questao_id}/adiar",
    response_model=AgendaSimples,
    summary="Tira da fila por um mês",
)
async def post_adiar(
    questao_id: UUID, req: AdiarRequest, _: UsuarioLogado
) -> AgendaSimples:
    """Adiar não é acertar.

    Nenhuma tentativa é registrada: contar "está fácil" como acerto encheria a
    estatística com o que eu não respondi, e a taxa de acerto deixaria de medir
    o que ela existe para medir.
    """
    try:
        return AgendaSimples(**await servico.adiar(questao_id, dias=req.dias))
    except servico.QuestaoNaoEncontrada as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/questoes/{questao_id}/historico",
    response_model=list[TentativaResponse],
    summary="Toda vez que respondi esta questão",
)
async def get_historico(questao_id: UUID, _: UsuarioLogado) -> list[TentativaResponse]:
    return [
        TentativaResponse(
            id=str(t.id),
            respondida_em=t.respondida_em,
            acertou=t.acertou,
            resposta=t.resposta,
            tentativa_n=t.tentativa_n,
            segundos=t.segundos,
        )
        for t in await servico.historico(questao_id)
    ]
