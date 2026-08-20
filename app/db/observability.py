"""Observabilidade — toda chamada de LLM e todo evento de pipeline gravados.

Diferença deliberada em relação ao repo antigo: aqui é **async nativo**. Lá
havia uma ponte `thread + asyncio.run()` e um engine `NullPool` paralelo
(`sync_bridge`) só porque o pipeline era síncrono e gravava de fora do event
loop. Nesta base tudo é async (FastAPI + worker), então some a ponte inteira.

Registrar nunca pode derrubar quem chamou: falha aqui vira warning no log.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select

from app.config import settings
from app.db.models.ai_call import AiCall
from app.db.models.pipeline_event import PipelineEvent
from app.db.session import get_session
from app.utils.logger import get_logger

logger = get_logger()

# ── Custo ─────────────────────────────────────────────────────────
#
# Três estados, e confundi-los foi o defeito: **zero** (rodou local, custou
# nada), **um número** (rodou fora e o preço é conhecido) e **não sei** (rodou
# fora e o modelo não está na tabela). Antes os três viravam `custo_usd = 0` no
# painel, o que é pior que não ter o número — parece uma medição.
#
# Preços do paid tier em ai.google.dev/gemini-api/docs/pricing, conferidos em
# 20/08/2026. Nada aqui é estimado de cabeça: chutar preço é o mesmo erro que a
# Fase C passou o dia tirando do currículo.

PROVIDERS_LOCAIS = frozenset({"ollama"})


@dataclass(frozen=True, slots=True)
class Preco:
    """USD por 1M de tokens, com as duas pegadinhas da tabela do Google.

    A **faixa longa**: prompt acima de `acima_de` tokens muda o preço da entrada
    E o da saída (o 2.5-pro dobra a entrada e sobe a saída em 50%). A
    **promoção com prazo**: o 3.7-flash custa metade até 31/12/2026 e dobra em
    01/01/2027. Guardar só o preço promocional faria a conta mentir sozinha na
    virada do ano, sem ninguém tocar em código.
    """

    input: float
    output: float
    acima_de: int | None = None
    input_longo: float | None = None
    output_longo: float | None = None
    ate: date | None = None
    depois: Preco | None = None

    def vigente_em(self, dia: date) -> Preco:
        p = self
        while p.ate and dia > p.ate and p.depois:
            p = p.depois
        return p

    def custo(self, ti: int, to: int, *, dia: date) -> float:
        p = self.vigente_em(dia)
        entrada, saida = p.input, p.output
        if p.acima_de is not None and ti > p.acima_de:
            entrada, saida = p.input_longo, p.output_longo
        return round((ti / 1_000_000) * entrada + (to / 1_000_000) * saida, 6)


PRECOS_USD_1M: dict[str, Preco] = {
    # O pesado do currículo — as 4 chamadas medidas na Fase C (22.664 tokens).
    "gemini-2.5-pro": Preco(
        input=1.25, output=10.00,
        acima_de=200_000, input_longo=2.50, output_longo=15.00,
    ),
    # O `GEMINI_MODEL` padrão. Preço promocional até o fim de 2026.
    "gemini-3.7-flash": Preco(
        input=0.75, output=3.75,
        ate=date(2026, 12, 31), depois=Preco(input=1.50, output=7.50),
    ),
    "gemini-2.5-flash": Preco(input=0.30, output=2.50),
    "gemini-2.5-flash-lite": Preco(input=0.10, output=0.40),
    # Avaliado e recusado na F1 (o 2.5-pro acertou igual e custa menos), mas
    # está no `.env` de quem quiser testar.
    "gemini-3.1-pro-preview": Preco(
        input=2.00, output=12.00,
        acima_de=200_000, input_longo=4.00, output_longo=18.00,
    ),
}


def _estimar_custo(
    provider: str, modelo: str, ti: int | None, to: int | None
) -> float | None:
    """`None` quando o custo é desconhecido — nunca zero por falta de tabela."""
    if provider in PROVIDERS_LOCAIS:
        return 0.0
    p = PRECOS_USD_1M.get(modelo)
    if not p or ti is None or to is None:
        return None
    return p.custo(ti, to, dia=date.today())


@dataclass(slots=True)
class AiCallRecord:
    agente: str = "desconhecido"
    tarefa: str | None = None
    provider: str = "?"
    modelo: str = "?"
    prompt: str | None = None
    resposta: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    latencia_ms: int | None = None
    sucesso: bool = True
    finish_reason: str | None = None
    erro: str | None = None
    alvo_ref: str | None = None


async def registrar_ai_call(rec: AiCallRecord) -> None:
    if not settings.observer_enabled:
        return
    guardar = settings.observ_store_payloads
    ti, to = rec.tokens_input, rec.tokens_output
    total = (ti or 0) + (to or 0) if (ti is not None or to is not None) else None
    try:
        async with get_session() as session:
            session.add(
                AiCall(
                    agente=rec.agente,
                    tarefa=rec.tarefa,
                    provider=rec.provider,
                    modelo=rec.modelo,
                    prompt=rec.prompt if guardar else None,
                    resposta=rec.resposta if guardar else None,
                    prompt_chars=len(rec.prompt) if rec.prompt else None,
                    resposta_chars=len(rec.resposta) if rec.resposta else None,
                    tokens_input=ti,
                    tokens_output=to,
                    tokens_total=total,
                    custo_usd=_estimar_custo(rec.provider, rec.modelo, ti, to),
                    latencia_ms=rec.latencia_ms,
                    finish_reason=rec.finish_reason,
                    sucesso=rec.sucesso,
                    error_message=rec.erro,
                    alvo_ref=rec.alvo_ref,
                )
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001 — observabilidade nunca derruba o caller
        logger.warning(f"Observabilidade: falha ao gravar ai_call: {type(e).__name__}: {e}")


async def registrar_evento(
    evento: str,
    *,
    status: str = "ok",
    detalhe: str | None = None,
    alvo_ref: str | None = None,
    duracao_ms: int | None = None,
) -> None:
    if not settings.observer_enabled:
        return
    try:
        async with get_session() as session:
            session.add(
                PipelineEvent(
                    evento=evento,
                    status=status,
                    detalhe=detalhe,
                    alvo_ref=alvo_ref,
                    duracao_ms=duracao_ms,
                )
            )
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Observabilidade: falha ao gravar evento '{evento}': {type(e).__name__}: {e}"
        )


async def stats() -> dict:
    """Números do painel de observabilidade (F1.7)."""
    async with get_session() as session:
        total = await session.scalar(select(func.count(AiCall.id))) or 0
        falhas = (
            await session.scalar(
                select(func.count(AiCall.id)).where(AiCall.sucesso.is_(False))
            )
            or 0
        )
        tokens = (
            await session.scalar(select(func.coalesce(func.sum(AiCall.tokens_total), 0))) or 0
        )
        # Sem `coalesce`: a soma de zero linhas é NULL e tem que continuar
        # NULL até aqui em cima. Zero é uma afirmação — "rodou e não custou".
        custo = await session.scalar(select(func.sum(AiCall.custo_usd)))
        sem_preco = (
            await session.scalar(
                select(func.count(AiCall.id)).where(AiCall.custo_usd.is_(None))
            )
            or 0
        )
        lat_media = await session.scalar(select(func.avg(AiCall.latencia_ms)))
        eventos = await session.scalar(select(func.count(PipelineEvent.id))) or 0

    return {
        "ai_calls_total": int(total),
        "ai_calls_falhas": int(falhas),
        "tokens_total": int(tokens),
        # O custo das chamadas que TÊM preço, e quantas ficaram de fora da
        # conta. Sem o segundo número o primeiro não se interpreta: R$ 0,00
        # pode ser "tudo local" ou "a tabela de preços está furada".
        "custo_usd_estimado": float(custo) if custo is not None else None,
        "ai_calls_sem_preco": int(sem_preco),
        "latencia_media_ms": round(float(lat_media)) if lat_media else None,
        "pipeline_events_total": int(eventos),
    }
