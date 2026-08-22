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

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models.estudo.agenda import Agenda, Tentativa
from app.db.models.estudo.questao import (
    FORMATOS,
    LETRAS,
    TRILHAS,
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


# ── A fila do dia ────────────────────────────────────────────────────────

async def fila(
    *,
    topico_id: uuid.UUID | None = None,
    modulo_id: uuid.UUID | None = None,
    questao_id: uuid.UUID | None = None,
    todas: bool = False,
    limite: int = 24,
) -> list[Questao]:
    """O que volta hoje, o que errei primeiro.

    A ordem não é cronológica: `total_erros` desc antes de `proxima_em` asc.
    Quem já errou entra na frente porque é onde a revisão rende — deixar as
    erradas para o fim da sessão é deixá-las para quando o cansaço chega.

    `todas=True` ignora o agendamento. Existe porque abrir um tópico e não poder
    responder nada — porque o algoritmo decidiu que hoje não é o dia — é a tela
    dizendo não a quem quer estudar. Responder fora da data **conta igual**: a
    tentativa entra no log e reagenda. A repetição espaçada me diz o mínimo que
    eu preciso rever, não o máximo que eu posso.
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
        if topico_id:
            stmt = stmt.where(Questao.topico_id == topico_id)
        if modulo_id:
            stmt = stmt.join(Topico, Topico.id == Questao.topico_id).where(
                Topico.modulo_id == modulo_id
            )
        return list((await session.scalars(stmt)).unique().all())


async def resumo() -> dict:
    """Os números do topo da tela inicial."""
    h = hoje()
    async with get_session() as session:
        total = await session.scalar(select(func.count(Questao.id))) or 0

        linhas = (
            await session.execute(
                select(Agenda.estado, func.count(Agenda.id))
                .where(Agenda.proxima_em <= h)
                .group_by(Agenda.estado)
            )
        ).all()
        por_estado = {estado: n for estado, n in linhas}

        vencendo = sum(por_estado.values())
        adiadas = await session.scalar(
            select(func.count(Agenda.id)).where(Agenda.estado == "adiada")
        ) or 0
        dominadas = await session.scalar(
            select(func.count(Agenda.id)).where(Agenda.estado == "dominada")
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
            "respondidas_hoje": int(respondidas_hoje),
        }


async def modulos() -> list[dict]:
    """Módulos, tópicos e o quanto de cada um vence quando.

    Uma consulta agregada por tópico e a montagem em memória. Com dez módulos e
    setenta tópicos, ir ao banco por tópico seria setenta round-trips para
    desenhar uma tela.
    """
    h = hoje()
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
                    func.count(Questao.id),
                    func.count(Questao.id).filter(Agenda.proxima_em <= h),
                    func.count(Questao.id).filter(Agenda.estado == "dominada"),
                    func.count(Questao.id).filter(Agenda.total_erros > 0),
                    func.min(Agenda.proxima_em),
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
            }
            for tid, n, venc, dom, erradas, prox in linhas
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
                    "proxima_em": min(proximas) if proximas else None,
                    "topicos": topicos,
                }
            )
        return saida


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
    busca: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[int, list[Questao]]:
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


async def atualizar_questao(questao_id: uuid.UUID, campos: dict) -> Questao:
    """Corrige a questão sem tocar no agendamento.

    É por aqui que a explicação entra depois: o acervo importado dos PDFs vem
    sem justificativa da banca, e eu escrevo a minha quando errar a questão e
    entender por quê.
    """
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
