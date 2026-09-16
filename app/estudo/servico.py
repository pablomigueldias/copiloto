"""O serviço do estudo: a fila do dia, a resposta e o cadastro.

A regra que mora só aqui: **o agendamento usa a primeira tentativa do bloco.**
A tela deixa tentar de novo antes de revelar a resposta, e isso é bom para
aprender — mas acertar na segunda não é acertar. Se as duas contassem igual,
o intervalo cresceria com base numa memória que não existe, e a questão sumiria
por 35 dias por causa de um chute que deu certo na repescagem.

Toda tentativa vai para o log de qualquer jeito. O que muda entre a primeira e
as seguintes é só quem manda no `proxima_em`.
"""
from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import BASE_DIR, settings
from app.db.models.estudo.agenda import Agenda, Tentativa
from app.db.models.estudo.questao import (
    FORMATOS,
    IMAGENS_DIR,
    LETRAS,
    TRILHAS,
    Banca,
    Modulo,
    Questao,
    Topico,
)
from app.db.session import get_session
from app.estudo import agendamento
from app.utils.logger import get_logger

logger = get_logger()


class EstudoErro(Exception):
    """Problema de uso que o chamador precisa tratar."""


class QuestaoNaoEncontrada(EstudoErro):
    pass


class RespostaInvalida(EstudoErro):
    pass


class NomeEmUso(EstudoErro):
    """Já existe módulo com esse nome, ou tópico com esse nome no módulo."""


class NaoVazio(EstudoErro):
    """Apagar levaria questões junto. Quem decide isso sou eu, explicitamente."""


class ImagemInexistente(EstudoErro):
    """A questão aponta para um arquivo que não está em `data/estudo/imagens`."""


def hoje() -> date:
    """Que dia é hoje **para quem estuda** — no fuso dele, não em UTC.

    Instante é `timestamptz` e vai em UTC; isso está certo. Mas "quais questões
    voltam hoje" não é um instante, é uma data civil. Com `now(UTC).date()` a
    fila do dia virava às 21h de Brasília: às 20h59 a tela dizia "16 voltam
    hoje" e às 21h01 dizia "amanhã", sem eu ter feito nada. O projeto já
    carrega `TIMEZONE` no `.env` justamente para isto.
    """
    return datetime.now(ZoneInfo(settings.timezone)).date()


def _estado(a: Agenda) -> agendamento.Estado:
    return agendamento.Estado(
        proxima_em=a.proxima_em,
        intervalo_dias=a.intervalo_dias,
        acertos_seguidos=a.acertos_seguidos,
        total_acertos=a.total_acertos,
        total_erros=a.total_erros,
        estado=a.estado,
    )


def _aplicar(a: Agenda, novo: agendamento.Estado, *, quando: datetime) -> None:
    a.proxima_em = novo.proxima_em
    a.intervalo_dias = novo.intervalo_dias
    a.acertos_seguidos = novo.acertos_seguidos
    a.total_acertos = novo.total_acertos
    a.total_erros = novo.total_erros
    a.estado = novo.estado
    a.ultima_em = quando


def _com_relacoes(stmt: Select) -> Select:
    return stmt.options(
        selectinload(Questao.topico).selectinload(Topico.modulo),
        selectinload(Questao.agenda),
    )


# ── Banca pausada ────────────────────────────────────────────────────────
#
# Uma banca pausada não sai do acervo: ela sai do **estudo**. A fila do dia, o
# resumo e os contadores dos módulos deixam de contá-la; o acervo (`listar`) a
# mostra inteira, porque é lá que eu confiro gabarito e escrevo explicação, e
# esconder questão de quem foi procurá-la seria mentir sobre o que existe.
#
# Os dois predicados abaixo são subconsulta e não `join`, de propósito: eles
# entram em consultas que já têm três junções e num agregado por tópico, e um
# `outerjoin` a mais em cada uma mudaria a cardinalidade dos `count()`.


def _sem_banca_pausada():
    """A questão entra na fila de hoje.

    `banca_id IS NULL` entra: é a questão inédita, que eu escrevi, e ela não
    pertence a concurso nenhum. O `or_` explícito existe porque `NULL NOT IN
    (...)` é `NULL` em SQL — sem ele, toda questão sem banca sumiria da fila.
    """
    return or_(
        Questao.banca_id.is_(None),
        Questao.banca_id.notin_(select(Banca.id).where(Banca.ativa.is_(False))),
    )


def _de_banca_pausada():
    """O contrário — o que está parado, para a tela poder dizer quanto é."""
    return Questao.banca_id.in_(select(Banca.id).where(Banca.ativa.is_(False)))


# ── A fila do dia ────────────────────────────────────────────────────────

_ITEM_NA_ORIGEM = re.compile(r"(?:item|quest(?:ão|ao))\s+(\d+)", re.IGNORECASE)


def _bloco(q: Questao) -> tuple[uuid.UUID, str] | None:
    """A chave que junta os itens que dividem o mesmo texto de apoio.

    É o `texto_base` que identifica o bloco, não o `comando`: o comando se
    repete entre provas diferentes ("julgue o item a seguir"), o texto de apoio
    não. Vai com o tópico junto porque o mesmo trecho pode ser reaproveitado por
    outra banca em outro tópico, e aí são dois blocos, não um.
    """
    texto = (q.texto_base or "").strip()
    return (q.topico_id, texto) if texto else None


def _ordem_no_bloco(q: Questao) -> tuple[int, str]:
    """Dentro do bloco vale a ordem da prova, não a do agendamento.

    A `origem` termina em "item N" — ou "questão N", quando o bloco é de
    múltipla escolha e a prova numera assim (contrato do `cadastrar-questao.md`)
    —, e é esse N que põe o 16 antes do 18. Sem isto a ordenação por dificuldade
    embaralha o bloco: foi o que aconteceu em 06/09/2026 com o texto do
    COREN-PR, que veio 18, 16, 17.
    """
    achado = _ITEM_NA_ORIGEM.search(q.origem or "")
    return (int(achado.group(1)) if achado else 10**6, q.origem or "")


async def _irmaos_por_bloco(
    session, questoes: Sequence[Questao]
) -> dict[tuple[uuid.UUID, str], list[Questao]]:
    """Todos os itens dos blocos representados em `questoes`, na ordem da prova.

    Traz **inclusive os que não venceram hoje**. É o ponto da coisa: reler
    quatro parágrafos para responder um item, e reler os mesmos quatro
    parágrafos duas semanas depois para responder o item seguinte, é pagar o
    custo do texto N vezes. Quando o bloco aparece, ele aparece inteiro.

    Responder adiantado conta igual — a tentativa entra no log e reagenda, como
    em qualquer treino fora da data.
    """
    chaves = {c for c in (_bloco(q) for q in questoes) if c is not None}
    if not chaves:
        return {}

    stmt = (
        _com_relacoes(select(Questao))
        .join(Agenda, Agenda.questao_id == Questao.id)
        .where(
            _sem_banca_pausada(),
            or_(
                *[
                    and_(Questao.topico_id == topico, Questao.texto_base == texto)
                    for topico, texto in chaves
                ]
            ),
        )
    )
    blocos: dict[tuple[uuid.UUID, str], list[Questao]] = {}
    for q in (await session.scalars(stmt)).unique().all():
        chave = _bloco(q)
        if chave is not None:
            blocos.setdefault(chave, []).append(q)
    for itens in blocos.values():
        itens.sort(key=_ordem_no_bloco)
    return blocos


async def fila(
    *,
    topico_id: uuid.UUID | None = None,
    modulo_id: uuid.UUID | None = None,
    banca_id: uuid.UUID | None = None,
    questao_id: uuid.UUID | None = None,
    todas: bool = False,
    limite: int = 24,
) -> list[Questao]:
    """O que volta hoje, o que errei primeiro — com os blocos inteiros.

    A ordem não é cronológica: `total_erros` desc antes de `proxima_em` asc.
    Quem já errou entra na frente porque é onde a revisão rende — deixar as
    erradas para o fim da sessão é deixá-las para quando o cansaço chega.

    **Item que divide texto de apoio com outro não vem sozinho.** Um bloco de
    "julgue os itens" é uma leitura só; o agendamento, que trata cada item como
    uma questão independente, espalhava os seis por dias diferentes e cobrava a
    leitura do texto seis vezes. Então o que o agendamento escolhe é o BLOCO:
    basta um item vencer para os irmãos virem junto, na ordem da prova, até
    acabar. Quem decide a posição do bloco na fila é o item mais atrasado dele —
    o erro continua puxando para a frente.

    Por isso `limite` é piso, não teto: a fila nunca corta um bloco no meio.
    Ela para de abrir blocos novos ao alcançar o limite, e termina o que abriu.

    `todas=True` ignora o agendamento. Existe porque abrir um tópico e não poder
    responder nada — porque o algoritmo decidiu que hoje não é o dia — é a tela
    dizendo não a quem quer estudar. Responder fora da data **conta igual**: a
    tentativa entra no log e reagenda. A repetição espaçada me diz o mínimo que
    eu preciso rever, não o máximo que eu posso.

    `questao_id` é a exceção: é o botão "responder" de UMA questão do acervo, e
    quem clica nele pediu aquela questão, não o bloco dela. Ela ignora a pausa
    da banca também: quem clicou em responder aquela questão já a viu na tela e
    não precisa que o filtro decida por ele.

    **Banca pausada não entra.** É para isso que ela existe: quando eu troco de
    concurso, a fila do dia tem de virar junto, senão a repetição espaçada me
    devolve todo dia uma prova que eu não vou fazer.
    """
    async with get_session() as session:
        stmt = (
            _com_relacoes(select(Questao))
            .join(Agenda, Agenda.questao_id == Questao.id)
            .order_by(
                Agenda.total_erros.desc(),
                Agenda.proxima_em.asc(),
                Questao.dificuldade.asc(),
            )
            .limit(limite)
        )
        if not todas and questao_id is None:
            stmt = stmt.where(Agenda.proxima_em <= hoje())
        if questao_id:
            stmt = stmt.where(Questao.id == questao_id)
        else:
            stmt = stmt.where(_sem_banca_pausada())
        if banca_id:
            stmt = stmt.where(Questao.banca_id == banca_id)
        if topico_id:
            stmt = stmt.where(Questao.topico_id == topico_id)
        if modulo_id:
            stmt = stmt.join(Topico, Topico.id == Questao.topico_id).where(
                Topico.modulo_id == modulo_id
            )
        vencendo = list((await session.scalars(stmt)).unique().all())

        if questao_id is not None:
            return vencendo

        blocos = await _irmaos_por_bloco(session, vencendo)

        saida: list[Questao] = []
        vistos: set[uuid.UUID] = set()
        for q in vencendo:
            if q.id in vistos:  # já entrou junto com um irmão que veio antes
                continue
            if saida and len(saida) >= limite:
                break
            chave = _bloco(q)
            unidade = blocos.get(chave, [q]) if chave is not None else [q]
            saida.extend(unidade)
            vistos.update(x.id for x in unidade)
        return saida


async def resumo() -> dict:
    """Os números do topo da tela inicial.

    Os contadores de acervo e de agenda excluem banca pausada; `pausadas` existe
    justamente para dizer quanto ficou de fora. Sem esse número, trocar de
    concurso faria 96 questões evaporarem da tela sem explicação, e a primeira
    reação seria achar que o import quebrou.

    `respondidas_hoje` é a exceção e continua global: é um fato sobre o meu dia,
    não sobre o acervo ativo. Se eu respondi doze questões da Quadrix de manhã e
    pausei a banca à tarde, elas continuam respondidas.
    """
    h = hoje()
    async with get_session() as session:
        total = await session.scalar(
            select(func.count(Questao.id)).where(_sem_banca_pausada())
        ) or 0
        pausadas = await session.scalar(
            select(func.count(Questao.id)).where(_de_banca_pausada())
        ) or 0

        linhas = (
            await session.execute(
                select(Agenda.estado, func.count(Agenda.id))
                .join(Questao, Questao.id == Agenda.questao_id)
                .where(Agenda.proxima_em <= h, _sem_banca_pausada())
                .group_by(Agenda.estado)
            )
        ).all()
        por_estado = {estado: n for estado, n in linhas}

        vencendo = sum(por_estado.values())
        adiadas = await session.scalar(
            select(func.count(Agenda.id))
            .join(Questao, Questao.id == Agenda.questao_id)
            .where(Agenda.estado == "adiada", _sem_banca_pausada())
        ) or 0
        dominadas = await session.scalar(
            select(func.count(Agenda.id))
            .join(Questao, Questao.id == Agenda.questao_id)
            .where(Agenda.estado == "dominada", _sem_banca_pausada())
        ) or 0
        # `date(timestamptz)` no Postgres converte pelo `TimeZone` da sessão,
        # que é UTC — e a conta viraria às 21h de Brasília. `AT TIME ZONE`
        # explícito faz "respondidas hoje" bater com o "hoje" da fila.
        respondidas_hoje = await session.scalar(
            select(func.count(Tentativa.id)).where(
                func.date(
                    func.timezone(settings.timezone, Tentativa.respondida_em)
                )
                == h
            )
        ) or 0

        return {
            "hoje": vencendo,
            "de_erro": por_estado.get("aprendendo", 0),
            "novas": por_estado.get("nova", 0),
            "adiadas": int(adiadas),
            "dominadas": int(dominadas),
            "total": int(total),
            "pausadas": int(pausadas),
            "respondidas_hoje": int(respondidas_hoje),
        }


async def modulos() -> list[dict]:
    """Módulos, tópicos e o quanto de cada um vence quando.

    Uma consulta agregada por tópico e a montagem em memória. Com dez módulos e
    setenta tópicos, ir ao banco por tópico seria setenta round-trips para
    desenhar uma tela.

    Os contadores são do que está **em estudo**: banca pausada sai de `questoes`,
    `hoje`, `dominadas` e `com_erro`, e reaparece sozinha em `pausadas`. Um
    tópico que ficou só com questão de banca pausada mostra "0 · 27 pausadas" —
    que é a verdade, e é diferente de "tópico vazio".
    """
    h = hoje()
    # Uma vez só: o predicado entra em cinco agregados da mesma consulta.
    ativa = _sem_banca_pausada()
    async with get_session() as session:
        mods = list(
            (
                await session.scalars(
                    select(Modulo).order_by(Modulo.ordem, Modulo.nome)
                )
            ).unique().all()
        )

        linhas = (
            await session.execute(
                select(
                    Topico.id,
                    func.count(Questao.id).filter(ativa),
                    func.count(Questao.id).filter(ativa, Agenda.proxima_em <= h),
                    func.count(Questao.id).filter(ativa, Agenda.estado == "dominada"),
                    func.count(Questao.id).filter(ativa, Agenda.total_erros > 0),
                    func.min(Agenda.proxima_em).filter(ativa),
                    func.count(Questao.id).filter(_de_banca_pausada()),
                )
                .select_from(Topico)
                .outerjoin(Questao, Questao.topico_id == Topico.id)
                .outerjoin(Agenda, Agenda.questao_id == Questao.id)
                .group_by(Topico.id)
            )
        ).all()
        por_topico = {
            tid: {
                "questoes": n,
                "hoje": venc,
                "dominadas": dom,
                "com_erro": erradas,
                "proxima_em": prox,
                "pausadas": paradas,
            }
            for tid, n, venc, dom, erradas, prox, paradas in linhas
        }

        saida = []
        for m in mods:
            topicos = []
            for t in sorted(m.topicos, key=lambda t: (t.ordem, t.nome)):
                d = por_topico.get(t.id, {})
                topicos.append(
                    {
                        "id": str(t.id),
                        "nome": t.nome,
                        "questoes": d.get("questoes", 0),
                        "hoje": d.get("hoje", 0),
                        "dominadas": d.get("dominadas", 0),
                        "com_erro": d.get("com_erro", 0),
                        "proxima_em": d.get("proxima_em"),
                        "pausadas": d.get("pausadas", 0),
                    }
                )
            proximas = [t["proxima_em"] for t in topicos if t["proxima_em"]]
            saida.append(
                {
                    "id": str(m.id),
                    "nome": m.nome,
                    "trilha": m.trilha,
                    "questoes": sum(t["questoes"] for t in topicos),
                    "hoje": sum(t["hoje"] for t in topicos),
                    "dominadas": sum(t["dominadas"] for t in topicos),
                    "com_erro": sum(t["com_erro"] for t in topicos),
                    "pausadas": sum(t["pausadas"] for t in topicos),
                    "proxima_em": min(proximas) if proximas else None,
                    "topicos": topicos,
                }
            )
        return saida


# ── Bancas ───────────────────────────────────────────────────────────────
#
# Nascem pelo `scripts/importar_questoes.py`, que cria a banca do arquivo que
# está entrando. O que a tela faz é o que o import não sabe fazer: decidir qual
# delas eu estou estudando agora.


async def bancas() -> list[dict]:
    """Quem aplica prova no acervo, com quanto cada uma pesa.

    Ordenadas com a ativa na frente: a tela de Módulos usa isto como filtro, e
    a banca do concurso que eu estou fazendo tem de ser a primeira coisa ali.
    """
    h = hoje()
    async with get_session() as session:
        linhas = (
            await session.execute(
                select(
                    Banca.id,
                    Banca.nome,
                    Banca.ativa,
                    Banca.ordem,
                    func.count(Questao.id),
                    func.count(Questao.id).filter(Agenda.proxima_em <= h),
                    func.count(Questao.id).filter(Agenda.estado == "dominada"),
                    func.count(Questao.id).filter(Agenda.total_erros > 0),
                )
                .select_from(Banca)
                .outerjoin(Questao, Questao.banca_id == Banca.id)
                .outerjoin(Agenda, Agenda.questao_id == Questao.id)
                .group_by(Banca.id, Banca.nome, Banca.ativa, Banca.ordem)
                .order_by(Banca.ativa.desc(), Banca.ordem, Banca.nome)
            )
        ).all()

        # As questões sem banca não somem da tela: são as inéditas, e elas nunca
        # são pausadas. Aparecem como uma linha própria, sem id — a tela usa a
        # ausência do id para não oferecer os botões de pausar e renomear.
        sem_banca = (
            await session.execute(
                select(
                    func.count(Questao.id),
                    func.count(Questao.id).filter(Agenda.proxima_em <= h),
                    func.count(Questao.id).filter(Agenda.estado == "dominada"),
                    func.count(Questao.id).filter(Agenda.total_erros > 0),
                )
                .select_from(Questao)
                .outerjoin(Agenda, Agenda.questao_id == Questao.id)
                .where(Questao.banca_id.is_(None))
            )
        ).one()

        saida = [
            {
                "id": str(bid),
                "nome": nome,
                "ativa": ativa,
                "ordem": ordem,
                "questoes": n,
                "hoje": venc,
                "dominadas": dom,
                "com_erro": erradas,
            }
            for bid, nome, ativa, ordem, n, venc, dom, erradas in linhas
        ]
        if sem_banca[0]:
            saida.append(
                {
                    "id": None,
                    "nome": "Sem banca (inéditas)",
                    "ativa": True,
                    "ordem": 999,
                    "questoes": sem_banca[0],
                    "hoje": sem_banca[1],
                    "dominadas": sem_banca[2],
                    "com_erro": sem_banca[3],
                }
            )
        return saida


async def criar_banca(*, nome: str, ativa: bool = True, ordem: int = 0) -> Banca:
    nome = (nome or "").strip()
    if not nome:
        raise RespostaInvalida("A banca precisa de um nome.")
    async with get_session() as session:
        if await session.scalar(
            select(Banca).where(func.lower(Banca.nome) == nome.lower())
        ):
            raise NomeEmUso(f"Já existe uma banca chamada '{nome}'.")
        banca = Banca(nome=nome, ativa=ativa, ordem=ordem)
        session.add(banca)
        try:
            await session.commit()
        except IntegrityError as e:
            raise NomeEmUso(f"Já existe uma banca chamada '{nome}'.") from e
        return banca


async def atualizar_banca(banca_id: uuid.UUID, campos: dict) -> Banca:
    """Renomeia, reordena e — o que importa — pausa e retoma.

    `ativa` é o único campo aqui que muda o que eu vou ver amanhã de manhã, e é
    reversível: pausar não encosta em questão, agenda nem tentativa.
    """
    async with get_session() as session:
        banca = await session.scalar(select(Banca).where(Banca.id == banca_id))
        if banca is None:
            raise QuestaoNaoEncontrada(f"Banca {banca_id} não existe.")
        for k, v in campos.items():
            if v is not None:
                setattr(banca, k, v.strip() if isinstance(v, str) else v)
        try:
            await session.commit()
        except IntegrityError as e:
            raise NomeEmUso("Já existe uma banca com esse nome.") from e
        logger.info(
            f"Estudo: banca '{banca.nome}' agora está "
            f"{'ativa' if banca.ativa else 'pausada'}"
        )
        return banca


async def focar_banca(banca_id: uuid.UUID) -> dict:
    """Deixa só uma banca em estudo — pausa todas as outras de uma vez.

    Pausar uma a uma é a operação certa quando eu descarto uma prova; trocar de
    concurso é outra coisa, e são dez cliques para dizer uma frase só ("agora é
    esta"). O efeito é exatamente o de pausar cada uma à mão: nada é apagado, e
    `ativar_todas` desfaz no mesmo clique.

    Volta o que mudou, porque uma ação em massa precisa dizer o tamanho do que
    fez — "9 bancas pausadas, 32 questões fora da fila" é a diferença entre
    conferir e desconfiar.
    """
    async with get_session() as session:
        alvo = await session.scalar(select(Banca).where(Banca.id == banca_id))
        if alvo is None:
            raise QuestaoNaoEncontrada(f"Banca {banca_id} não existe.")

        outras = list(
            (await session.scalars(select(Banca).where(Banca.id != banca_id))).all()
        )
        pausadas = [b for b in outras if b.ativa]
        for b in outras:
            b.ativa = False
        alvo.ativa = True

        questoes = int(
            await session.scalar(
                select(func.count(Questao.id)).where(
                    Questao.banca_id.in_([b.id for b in pausadas])
                )
            )
            or 0
        ) if pausadas else 0

        await session.commit()
        logger.info(
            f"Estudo: foco em '{alvo.nome}' — {len(pausadas)} banca(s) pausada(s)"
        )
        return {
            "banca": alvo.nome,
            "bancas_pausadas": len(pausadas),
            "questoes_pausadas": questoes,
        }


async def ativar_todas() -> int:
    """Devolve todas as bancas ao estudo. O desfazer de `focar_banca`."""
    async with get_session() as session:
        pausadas = list(
            (await session.scalars(select(Banca).where(Banca.ativa.is_(False)))).all()
        )
        for b in pausadas:
            b.ativa = True
        await session.commit()
        logger.info(f"Estudo: {len(pausadas)} banca(s) de volta ao estudo")
        return len(pausadas)


async def apagar_banca(banca_id: uuid.UUID, *, forcar: bool = False) -> int:
    """Apaga o rótulo, nunca o acervo.

    O `SET NULL` da FK deixa as questões onde estão, sem banca. Ainda assim a
    remoção recusa por padrão quando há questões: perder a procedência de 96
    itens é perder a única coisa que me deixa reabrir o PDF e desconfiar do
    gabarito. Para tirar a banca da tela sem perder nada, o caminho é pausar.
    """
    async with get_session() as session:
        banca = await session.scalar(select(Banca).where(Banca.id == banca_id))
        if banca is None:
            raise QuestaoNaoEncontrada(f"Banca {banca_id} não existe.")
        n = int(
            await session.scalar(
                select(func.count(Questao.id)).where(Questao.banca_id == banca_id)
            )
            or 0
        )
        if n and not forcar:
            raise NaoVazio(
                f"'{banca.nome}' tem {n} questão(ões). Apagar não as apaga, mas "
                "elas perdem a procedência — para tirá-la do estudo, pause."
            )
        await session.delete(banca)
        await session.commit()
        return n


# ── Módulos e tópicos ────────────────────────────────────────────────────
#
# Até aqui os dois só nasciam pelo `scripts/importar_questoes.py`, o que fazia
# sentido enquanto o acervo vinha inteiro de PDF — e deixou de fazer no minuto
# em que cadastrar questão pela tela virou possível: dá para pôr a questão num
# tópico que existe, e não dá para criar o tópico. A tela pedia um passo que
# ela não oferecia.

async def criar_modulo(*, nome: str, trilha: str = "concurso", ordem: int = 0) -> Modulo:
    nome = (nome or "").strip()
    if not nome:
        raise RespostaInvalida("O módulo precisa de um nome.")
    if trilha not in TRILHAS:
        raise RespostaInvalida(f"Trilha '{trilha}' desconhecida. Use uma de {list(TRILHAS)}.")

    async with get_session() as session:
        # Checagem antes do insert para dar erro legível; a `UNIQUE` no banco é
        # que garante de verdade, contra duas abas salvando ao mesmo tempo.
        if await session.scalar(select(Modulo).where(func.lower(Modulo.nome) == nome.lower())):
            raise NomeEmUso(f"Já existe um módulo chamado '{nome}'.")
        modulo = Modulo(nome=nome, trilha=trilha, ordem=ordem)
        session.add(modulo)
        try:
            await session.commit()
        except IntegrityError as e:
            raise NomeEmUso(f"Já existe um módulo chamado '{nome}'.") from e
        return modulo


async def criar_topico(*, modulo_id: uuid.UUID, nome: str, ordem: int = 0) -> Topico:
    nome = (nome or "").strip()
    if not nome:
        raise RespostaInvalida("O tópico precisa de um nome.")

    async with get_session() as session:
        if await session.scalar(select(Modulo).where(Modulo.id == modulo_id)) is None:
            raise QuestaoNaoEncontrada(f"Módulo {modulo_id} não existe.")
        existente = await session.scalar(
            select(Topico).where(
                Topico.modulo_id == modulo_id, func.lower(Topico.nome) == nome.lower()
            )
        )
        if existente is not None:
            raise NomeEmUso(f"'{nome}' já é um tópico desse módulo.")
        topico = Topico(modulo_id=modulo_id, nome=nome, ordem=ordem)
        session.add(topico)
        try:
            await session.commit()
        except IntegrityError as e:
            raise NomeEmUso(f"'{nome}' já é um tópico desse módulo.") from e
        return topico


async def atualizar_modulo(modulo_id: uuid.UUID, campos: dict) -> Modulo:
    async with get_session() as session:
        modulo = await session.scalar(select(Modulo).where(Modulo.id == modulo_id))
        if modulo is None:
            raise QuestaoNaoEncontrada(f"Módulo {modulo_id} não existe.")
        if (t := campos.get("trilha")) and t not in TRILHAS:
            raise RespostaInvalida(f"Trilha '{t}' desconhecida. Use uma de {list(TRILHAS)}.")
        for k, v in campos.items():
            if v is not None:
                setattr(modulo, k, v.strip() if isinstance(v, str) else v)
        try:
            await session.commit()
        except IntegrityError as e:
            raise NomeEmUso("Já existe um módulo com esse nome.") from e
        return modulo


async def atualizar_topico(topico_id: uuid.UUID, campos: dict) -> Topico:
    async with get_session() as session:
        topico = await session.scalar(select(Topico).where(Topico.id == topico_id))
        if topico is None:
            raise QuestaoNaoEncontrada(f"Tópico {topico_id} não existe.")
        for k, v in campos.items():
            if v is not None:
                setattr(topico, k, v.strip() if isinstance(v, str) else v)
        try:
            await session.commit()
        except IntegrityError as e:
            raise NomeEmUso("Esse nome já é um tópico do módulo.") from e
        return topico


async def _contar_questoes(session, *, modulo_id=None, topico_id=None) -> int:
    stmt = select(func.count(Questao.id)).join(Topico, Topico.id == Questao.topico_id)
    if modulo_id:
        stmt = stmt.where(Topico.modulo_id == modulo_id)
    if topico_id:
        stmt = stmt.where(Questao.topico_id == topico_id)
    return int(await session.scalar(stmt) or 0)


async def apagar_modulo(modulo_id: uuid.UUID, *, forcar: bool = False) -> int:
    """Apaga o módulo. Recusa se houver questões, salvo `forcar`.

    O `ON DELETE CASCADE` leva tópicos, questões, agendas e **todo o histórico
    de tentativas** junto. Deixar isso acontecer por um clique distraído seria
    perder meses de repetição espaçada — que é a única coisa aqui que não se
    refaz. Por isso o padrão é recusar dizendo quantas questões seriam perdidas.
    """
    async with get_session() as session:
        modulo = await session.scalar(select(Modulo).where(Modulo.id == modulo_id))
        if modulo is None:
            raise QuestaoNaoEncontrada(f"Módulo {modulo_id} não existe.")
        n = await _contar_questoes(session, modulo_id=modulo_id)
        if n and not forcar:
            raise NaoVazio(
                f"'{modulo.nome}' tem {n} questão(ões), e apagá-lo leva junto o "
                "histórico de respostas delas."
            )
        await session.delete(modulo)
        await session.commit()
        return n


async def apagar_topico(topico_id: uuid.UUID, *, forcar: bool = False) -> int:
    async with get_session() as session:
        topico = await session.scalar(select(Topico).where(Topico.id == topico_id))
        if topico is None:
            raise QuestaoNaoEncontrada(f"Tópico {topico_id} não existe.")
        n = await _contar_questoes(session, topico_id=topico_id)
        if n and not forcar:
            raise NaoVazio(
                f"'{topico.nome}' tem {n} questão(ões), e apagá-lo leva junto o "
                "histórico de respostas delas."
            )
        await session.delete(topico)
        await session.commit()
        return n


# ── Responder ────────────────────────────────────────────────────────────

async def obter(questao_id: uuid.UUID) -> Questao:
    async with get_session() as session:
        q = await session.scalar(
            _com_relacoes(select(Questao)).where(Questao.id == questao_id)
        )
        if q is None:
            raise QuestaoNaoEncontrada(f"Questão {questao_id} não existe.")
        return q


def _valida_resposta(questao: Questao, resposta: str) -> str:
    r = (resposta or "").strip().upper()
    validas = ("C", "E") if questao.formato == "certo_errado" else LETRAS
    if r not in validas:
        raise RespostaInvalida(
            f"Resposta '{resposta}' inválida para {questao.formato}. "
            f"Use uma de {list(validas)}."
        )
    return r


async def responder(
    questao_id: uuid.UUID,
    *,
    resposta: str,
    tentativa_n: int = 1,
    segundos: int | None = None,
) -> dict:
    """Grava a tentativa e, se for a primeira do bloco, reagenda.

    Devolve o gabarito e a nova data — a tela precisa dos dois para dizer
    "Certo. Volta em 7 dias, 28 de agosto" numa só resposta do servidor.
    """
    agora = datetime.now(UTC)
    async with get_session() as session:
        questao = await session.scalar(
            _com_relacoes(select(Questao)).where(Questao.id == questao_id)
        )
        if questao is None:
            raise QuestaoNaoEncontrada(f"Questão {questao_id} não existe.")

        r = _valida_resposta(questao, resposta)
        acertou = r == questao.gabarito.upper()

        session.add(
            Tentativa(
                questao_id=questao.id,
                acertou=acertou,
                resposta=r,
                tentativa_n=max(1, tentativa_n),
                segundos=segundos,
                respondida_em=agora,
            )
        )

        agenda = questao.agenda
        if agenda is None:
            agenda = Agenda(
                questao_id=questao.id, **_como_colunas(agendamento.inicial(hoje()))
            )
            session.add(agenda)

        reagendou = tentativa_n <= 1
        if reagendou:
            _aplicar(
                agenda,
                agendamento.proximo_estado(_estado(agenda), acertou=acertou, hoje=hoje()),
                quando=agora,
            )

        await session.commit()
        logger.info(
            f"Estudo: questão {str(questao.id)[:8]} "
            f"{'certa' if acertou else 'errada'} (tentativa {tentativa_n})"
        )
        return {
            "acertou": acertou,
            "gabarito": questao.gabarito.upper(),
            "explicacao": questao.explicacao,
            "reagendou": reagendou,
            "proxima_em": agenda.proxima_em,
            "intervalo_dias": agenda.intervalo_dias,
            "estado": agenda.estado,
        }


async def adiar(questao_id: uuid.UUID, *, dias: int | None = None) -> dict:
    agora = datetime.now(UTC)
    async with get_session() as session:
        questao = await session.scalar(
            _com_relacoes(select(Questao)).where(Questao.id == questao_id)
        )
        if questao is None:
            raise QuestaoNaoEncontrada(f"Questão {questao_id} não existe.")

        agenda = questao.agenda
        if agenda is None:
            agenda = Agenda(
                questao_id=questao.id, **_como_colunas(agendamento.inicial(hoje()))
            )
            session.add(agenda)

        novo = (
            agendamento.adiada(_estado(agenda), hoje=hoje(), dias=dias)
            if dias
            else agendamento.adiada(_estado(agenda), hoje=hoje())
        )
        _aplicar(agenda, novo, quando=agora)
        await session.commit()
        return {
            "proxima_em": agenda.proxima_em,
            "intervalo_dias": agenda.intervalo_dias,
            "estado": agenda.estado,
        }


async def historico(questao_id: uuid.UUID, *, limite: int = 50) -> Sequence[Tentativa]:
    async with get_session() as session:
        return (
            await session.scalars(
                select(Tentativa)
                .where(Tentativa.questao_id == questao_id)
                .order_by(Tentativa.respondida_em.desc())
                .limit(limite)
            )
        ).all()


# ── Cadastro ─────────────────────────────────────────────────────────────

def _como_colunas(e: agendamento.Estado) -> dict:
    return {
        "proxima_em": e.proxima_em,
        "intervalo_dias": e.intervalo_dias,
        "acertos_seguidos": e.acertos_seguidos,
        "total_acertos": e.total_acertos,
        "total_erros": e.total_erros,
        "estado": e.estado,
    }


async def listar(
    *,
    topico_id: uuid.UUID | None = None,
    modulo_id: uuid.UUID | None = None,
    banca_id: uuid.UUID | None = None,
    busca: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[int, list[Questao]]:
    """O acervo — e aqui banca pausada **aparece**.

    É a única consulta que não filtra pela pausa, e de propósito: esta é a tela
    onde eu confiro gabarito e escrevo explicação. Sumir com a questão de quem
    foi procurá-la seria mentir sobre o que existe no banco. Quem quiser separar
    passa `banca_id`.
    """
    async with get_session() as session:
        stmt = _com_relacoes(select(Questao)).join(
            Topico, Topico.id == Questao.topico_id
        )
        conta = select(func.count(Questao.id)).join(
            Topico, Topico.id == Questao.topico_id
        )
        if topico_id:
            stmt = stmt.where(Questao.topico_id == topico_id)
            conta = conta.where(Questao.topico_id == topico_id)
        if modulo_id:
            stmt = stmt.where(Topico.modulo_id == modulo_id)
            conta = conta.where(Topico.modulo_id == modulo_id)
        if banca_id:
            stmt = stmt.where(Questao.banca_id == banca_id)
            conta = conta.where(Questao.banca_id == banca_id)
        if busca:
            alvo = f"%{busca.strip()}%"
            stmt = stmt.where(Questao.enunciado.ilike(alvo))
            conta = conta.where(Questao.enunciado.ilike(alvo))

        total = await session.scalar(conta) or 0
        itens = (
            await session.scalars(
                stmt.order_by(Questao.created_at.desc()).limit(limite).offset(offset)
            )
        ).unique().all()
        return int(total), list(itens)


def _confere_imagem(nome: str | None) -> None:
    """A figura tem de existir em disco antes de a questão existir no banco.

    Falhar aqui é barato; falhar na tela é caro. A questão "que tipo de
    topologia é a da imagem?" sem a imagem não é uma questão difícil, é uma
    questão impossível — e ela apareceria no meio de uma sessão cronometrada,
    quando não há o que fazer a respeito.
    """
    if not nome:
        return
    caminho = BASE_DIR / IMAGENS_DIR / nome
    if not caminho.is_file():
        raise ImagemInexistente(
            f"A imagem '{nome}' não está em {IMAGENS_DIR}/. "
            "Ponha o arquivo lá antes de cadastrar a questão."
        )


async def criar_questao(dados: dict) -> Questao:
    """Cadastra a questão e já a coloca vencendo hoje.

    Questão nova nasce na fila. O contrário — nascer agendada para daqui a uma
    semana — significaria cadastrar hoje e só ver na tela semana que vem, que é
    o jeito mais rápido de eu parar de cadastrar.
    """
    if dados["formato"] not in FORMATOS:
        raise RespostaInvalida(
            f"Formato '{dados['formato']}' desconhecido. Use um de {list(FORMATOS)}."
        )
    _confere_imagem(dados.get("imagem"))
    async with get_session() as session:
        questao = Questao(**dados)
        session.add(questao)
        await session.flush()
        session.add(
            Agenda(questao_id=questao.id, **_como_colunas(agendamento.inicial(hoje())))
        )
        await session.commit()
        return await session.scalar(
            _com_relacoes(select(Questao)).where(Questao.id == questao.id)
        )


async def apagar_questao(questao_id: uuid.UUID) -> int:
    """Apaga uma questão só, e devolve quantas tentativas foram junto.

    Sem `forcar`, ao contrário de módulo e tópico. Lá o alvo é um contêiner: o
    clique apaga um acervo cujo tamanho eu não estou vendo, e por isso a API
    recusa até eu confirmar com o número na mão. Aqui o alvo é a questão que
    está aberta na gaveta, com o histórico dela na tela logo abaixo — o número
    já está à vista antes do clique. A conta volta mesmo assim, para o aviso
    poder dizer o que sumiu.

    O que se perde é o histórico de tentativas: o `ON DELETE CASCADE` leva
    agenda e tentativas. Questão errada de importação é para **reimportar** —
    `scripts/importar_questoes.py` atualiza pela `origem` sem tocar no
    agendamento. Apagar é para a questão que não devia existir.
    """
    async with get_session() as session:
        questao = await session.scalar(select(Questao).where(Questao.id == questao_id))
        if questao is None:
            raise QuestaoNaoEncontrada(f"Questão {questao_id} não existe.")
        n = int(
            await session.scalar(
                select(func.count(Tentativa.id)).where(
                    Tentativa.questao_id == questao_id
                )
            )
            or 0
        )
        await session.delete(questao)
        await session.commit()
        return n


async def atualizar_questao(questao_id: uuid.UUID, campos: dict) -> Questao:
    """Corrige a questão sem tocar no agendamento.

    É por aqui que a explicação entra depois: o acervo importado dos PDFs vem
    sem justificativa da banca, e eu escrevo a minha quando errar a questão e
    entender por quê.
    """
    _confere_imagem(campos.get("imagem"))
    async with get_session() as session:
        questao = await session.scalar(select(Questao).where(Questao.id == questao_id))
        if questao is None:
            raise QuestaoNaoEncontrada(f"Questão {questao_id} não existe.")
        for k, v in campos.items():
            if v is not None:
                setattr(questao, k, v)
        await session.commit()
        return await session.scalar(
            _com_relacoes(select(Questao)).where(Questao.id == questao_id)
        )
