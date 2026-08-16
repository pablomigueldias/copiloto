"""O painel: o funil, o que está parado, e o que o mercado pede que eu não tenho.

A última é a mais valiosa e a menos óbvia. Trinta candidaturas produzem uma
lista de gaps repetidos — e essa lista **é** o plano de estudo, derivado do que
o mercado realmente pediu, não do que parece importante.

Tudo sai de `candidatura_evento` e de `match_json`. Nenhuma inferência: contar é
trabalho de banco, e um LLM aqui só teria como acrescentar erro.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.candidatura.vagas import DIAS_PARA_FOLLOWUP, followup_vencido
from app.db.models.pessoal.candidatura_evento import CandidaturaEvento
from app.db.models.pessoal.vaga import Vaga
from app.db.session import get_session

# A ordem do funil. Cada etapa conta as vagas que **chegaram** ali, mesmo que já
# tenham avançado: "10 enviadas, 3 responderam" só faz sentido assim.
FUNIL = ("salva", "analisada", "gerada", "enviada", "respondida", "entrevista")


@dataclass(slots=True)
class Metricas:
    funil: dict[str, int] = field(default_factory=dict)
    por_status: dict[str, int] = field(default_factory=dict)
    taxa_resposta: float | None = None
    dias_ate_resposta: float | None = None
    followup_vencido: int = 0
    paradas: list[dict] = field(default_factory=list)
    gaps_frequentes: list[dict] = field(default_factory=list)
    score_medio: float | None = None

    def como_json(self) -> dict:
        return asdict(self)


async def _funil() -> dict[str, int]:
    async with get_session() as session:
        linhas = await session.execute(
            select(
                CandidaturaEvento.evento,
                func.count(func.distinct(CandidaturaEvento.vaga_id)),
            ).group_by(CandidaturaEvento.evento)
        )
    contagem = {evento: int(n) for evento, n in linhas}
    return {etapa: contagem.get(etapa, 0) for etapa in FUNIL}


async def _tempo_ate_resposta() -> float | None:
    """Média de dias entre enviar e receber a primeira resposta.

    Só das que responderam — misturar as sem resposta puxaria a média para o
    infinito e esconderia a informação.
    """
    async with get_session() as session:
        envios = (
            select(
                CandidaturaEvento.vaga_id,
                func.min(CandidaturaEvento.ocorreu_em).label("em"),
            )
            .where(CandidaturaEvento.evento == "enviada")
            .group_by(CandidaturaEvento.vaga_id)
            .subquery()
        )
        respostas = (
            select(
                CandidaturaEvento.vaga_id,
                func.min(CandidaturaEvento.ocorreu_em).label("em"),
            )
            .where(CandidaturaEvento.evento.in_(("respondida", "entrevista")))
            .group_by(CandidaturaEvento.vaga_id)
            .subquery()
        )
        media = await session.scalar(
            select(func.avg(respostas.c.em - envios.c.em))
            .select_from(envios)
            .join(respostas, respostas.c.vaga_id == envios.c.vaga_id)
        )
    return round(media.total_seconds() / 86400, 1) if media else None


async def _paradas(*, dias: int = 14, limite: int = 10) -> list[dict]:
    """Vagas sem nenhum evento há muito tempo — o que caiu do radar."""
    corte = datetime.now(UTC) - timedelta(days=dias)

    async with get_session() as session:
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
                .where(Vaga.status.notin_(("fim", "entrevista")), ultimo.c.em < corte)
                .order_by(ultimo.c.em)
                .limit(limite)
            )
        ).all()

    agora = datetime.now(UTC)
    return [
        {
            "vaga_id": str(v.id),
            "titulo": v.titulo,
            "empresa": v.empresa,
            "status": v.status,
            "parada_ha_dias": (agora - em).days,
        }
        for v, em in linhas
    ]


async def _gaps_frequentes(*, limite: int = 12) -> list[dict]:
    """O que mais me faltou, somando todas as vagas analisadas.

    Vira lista de estudo: se "Kubernetes" apareceu em 8 das 12 vagas, ele deixou
    de ser opinião sobre o mercado e virou dado sobre ele.
    """
    async with get_session() as session:
        matches = (
            await session.scalars(select(Vaga.match_json).where(Vaga.match_json.is_not(None)))
        ).all()

    contagem: Counter[str] = Counter()
    for m in matches:
        for gap in (m or {}).get("gaps") or []:
            contagem[str(gap).strip().lower()] += 1

    total = len(matches) or 1
    return [
        {"requisito": g, "vezes": n, "das_vagas": round(100 * n / total)}
        for g, n in contagem.most_common(limite)
    ]


async def calcular() -> Metricas:
    funil = await _funil()
    enviadas = funil.get("enviada", 0)
    responderam = funil.get("respondida", 0) + funil.get("entrevista", 0)

    async with get_session() as session:
        por_status = {
            s: int(n)
            for s, n in await session.execute(
                select(Vaga.status, func.count()).group_by(Vaga.status)
            )
        }
        score_medio = await session.scalar(
            select(func.avg(Vaga.match_score)).where(Vaga.match_score.is_not(None))
        )

    return Metricas(
        funil=funil,
        por_status=por_status,
        taxa_resposta=round(100 * responderam / enviadas, 1) if enviadas else None,
        dias_ate_resposta=await _tempo_ate_resposta(),
        followup_vencido=len(await followup_vencido(dias=DIAS_PARA_FOLLOWUP)),
        paradas=await _paradas(),
        gaps_frequentes=await _gaps_frequentes(),
        score_medio=round(float(score_medio), 1) if score_medio is not None else None,
    )
