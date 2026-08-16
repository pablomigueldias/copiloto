"""Vagas: entrada, máquina de estados e histórico.

A entrada é **texto colado**. O plano decidiu isso na §7: LinkedIn é o ambiente
mais hostil a automação que existe, e a assimetria é péssima — economiza minutos
por dia e arrisca o perfil profissional que levou anos para construir. Colar
sempre funciona, não quebra quando o site muda e não dá ban.

Quem move a candidatura de estado é **o código**, por ação minha ou por regra de
tempo. O LLM no máximo classifica *"esta resposta é um não?"* — e mesmo isso
vira sugestão na fila, não transição automática.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.db.models.pessoal.candidatura_evento import EVENTOS, CandidaturaEvento
from app.db.models.pessoal.vaga import STATUS_VAGA, Vaga
from app.db.session import get_session
from app.utils.logger import get_logger

logger = get_logger()

# Depois disto sem resposta, a candidatura entra na lista de follow-up. Sete
# dias é o do plano — tempo de o processo andar do outro lado sem virar
# insistência.
DIAS_PARA_FOLLOWUP = 7

# Para onde cada evento leva a vaga. O que não está aqui não muda status:
# 'visualizada' é informação, não progresso.
STATUS_POR_EVENTO = {
    "analisada": None,
    "gerada": None,
    "enviada": "candidatei",
    "respondida": "respondeu",
    "entrevista": "entrevista",
    "recusada": "fim",
    "sem_retorno": None,
}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class VagaErro(Exception):
    pass


class VagaNaoEncontrada(VagaErro):
    pass


def _titulo_provavel(texto: str) -> str:
    """A primeira linha com cara de título — chute honesto, corrigível depois.

    Pedir isso ao LLM seria gastar inferência para adivinhar o que a primeira
    linha quase sempre já diz.
    """
    for linha in texto.strip().splitlines():
        limpa = linha.strip(" #*-•\t")
        if 4 <= len(limpa) <= 120:
            return limpa
    return "Vaga sem título"


async def registrar_evento(
    vaga_id: UUID, evento: str, *, detalhe: str | None = None
) -> CandidaturaEvento:
    """Grava o evento e move o status, quando o evento move.

    Numa transação só: histórico e status que discordam são pior que qualquer
    um dos dois sozinho.
    """
    if evento not in EVENTOS:
        raise VagaErro(f"Evento desconhecido: {evento}. Use um de {list(EVENTOS)}.")

    async with get_session() as session:
        vaga = await session.get(Vaga, vaga_id)
        if vaga is None:
            raise VagaNaoEncontrada(f"Vaga {vaga_id} não existe.")

        novo = STATUS_POR_EVENTO.get(evento)
        if novo and novo in STATUS_VAGA:
            vaga.status = novo

        registro = CandidaturaEvento(vaga_id=vaga_id, evento=evento, detalhe=detalhe)
        session.add(registro)
        await session.commit()
        await session.refresh(registro)

    logger.info(f"Vaga {str(vaga_id)[:8]}: {evento}")
    return registro


async def criar(
    *,
    descricao: str,
    titulo: str | None = None,
    empresa: str | None = None,
    link: str | None = None,
    fonte: str | None = None,
    localizacao: str | None = None,
    modelo: str | None = None,
    senioridade: str | None = None,
    contato_email: str | None = None,
) -> Vaga:
    """Cola a descrição e a vaga existe. Todo o resto é opcional."""
    descricao = (descricao or "").strip()
    if len(descricao) < 50:
        raise VagaErro("Descrição curta demais para extrair requisitos (mínimo 50 caracteres).")

    async with get_session() as session:
        vaga = Vaga(
            titulo=(titulo or _titulo_provavel(descricao))[:300],
            empresa=empresa,
            link=link,
            fonte=fonte,
            localizacao=localizacao,
            modelo=modelo,
            senioridade=senioridade,
            # E-mail no corpo da vaga é o contato de candidatura em metade dos
            # casos — regex resolve, LLM seria desperdício.
            contato_email=contato_email or next(iter(_EMAIL.findall(descricao)), None),
            descricao=descricao,
        )
        session.add(vaga)
        await session.commit()
        await session.refresh(vaga)

    await registrar_evento(vaga.id, "salva")
    logger.info(f"Vaga salva: {vaga.titulo!r} ({vaga.empresa or 'sem empresa'})")
    return vaga


async def obter(vaga_id: UUID) -> Vaga:
    async with get_session() as session:
        vaga = await session.get(Vaga, vaga_id)
    if vaga is None:
        raise VagaNaoEncontrada(f"Vaga {vaga_id} não existe.")
    return vaga


async def listar(
    *,
    status: str | Sequence[str] | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[int, list[Vaga]]:
    filtros = []
    if status:
        alvos = [status] if isinstance(status, str) else list(status)
        filtros.append(Vaga.status.in_(alvos))

    async with get_session() as session:
        total = await session.scalar(select(func.count(Vaga.id)).where(*filtros)) or 0
        itens = (
            await session.scalars(
                select(Vaga)
                .where(*filtros)
                # Maior aderência primeiro; sem match calculado, a mais recente.
                .order_by(Vaga.match_score.desc().nullslast(), Vaga.created_at.desc())
                .limit(limite)
                .offset(offset)
            )
        ).all()
    return int(total), list(itens)


async def historico(vaga_id: UUID) -> list[CandidaturaEvento]:
    async with get_session() as session:
        return list(
            (
                await session.scalars(
                    select(CandidaturaEvento)
                    .where(CandidaturaEvento.vaga_id == vaga_id)
                    .order_by(CandidaturaEvento.ocorreu_em)
                )
            ).all()
        )


async def followup_vencido(*, dias: int = DIAS_PARA_FOLLOWUP) -> list[tuple[Vaga, int]]:
    """Candidaturas enviadas há mais de N dias sem nenhuma resposta.

    É a lista que justifica o projeto inteiro: currículo eu faço à mão em uma
    hora; lembrar da vaga de três semanas atrás, não.
    """
    limite = datetime.now(UTC) - timedelta(days=dias)

    async with get_session() as session:
        # Última vez que aconteceu qualquer coisa em cada vaga.
        ultimo = (
            select(
                CandidaturaEvento.vaga_id,
                func.max(CandidaturaEvento.ocorreu_em).label("em"),
            )
            .group_by(CandidaturaEvento.vaga_id)
            .subquery()
        )
        linhas = (
            await session.execute(
                select(Vaga, ultimo.c.em)
                .join(ultimo, ultimo.c.vaga_id == Vaga.id)
                .where(Vaga.status == "candidatei", ultimo.c.em < limite)
                .order_by(ultimo.c.em)
            )
        ).all()

    agora = datetime.now(UTC)
    return [(vaga, (agora - em).days) for vaga, em in linhas]


async def marcar_sem_retorno(*, dias: int = DIAS_PARA_FOLLOWUP) -> int:
    """Registra o vencimento — uma vez por vaga, não a cada passada do worker."""
    marcadas = 0
    for vaga, parada_ha in await followup_vencido(dias=dias):
        ja = [e for e in await historico(vaga.id) if e.evento == "sem_retorno"]
        if ja:
            continue
        await registrar_evento(
            vaga.id, "sem_retorno", detalhe=f"{parada_ha} dias sem resposta"
        )
        marcadas += 1
    return marcadas
