"""Observabilidade — toda chamada de LLM e todo evento de pipeline gravados.

Diferença deliberada em relação ao repo antigo: aqui é **async nativo**. Lá
havia uma ponte `thread + asyncio.run()` e um engine `NullPool` paralelo
(`sync_bridge`) só porque o pipeline era síncrono e gravava de fora do event
loop. Nesta base tudo é async (FastAPI + worker), então some a ponte inteira.

Registrar nunca pode derrubar quem chamou: falha aqui vira warning no log.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from app.config import settings
from app.db.models.ai_call import AiCall
from app.db.models.pipeline_event import PipelineEvent
from app.db.session import get_session
from app.utils.logger import get_logger

logger = get_logger()

# Preço por 1M de tokens, por modelo. Modelo local custa zero — a tabela só
# ganha linha durante a fase de coleta com API externa (§7 do plano).
PRECOS_USD_1M: dict[str, dict[str, float]] = {}


def _estimar_custo(modelo: str, ti: int | None, to: int | None) -> float | None:
    p = PRECOS_USD_1M.get(modelo)
    if not p or ti is None or to is None:
        return None
    return round((ti / 1_000_000) * p["input"] + (to / 1_000_000) * p["output"], 6)


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
                    custo_usd=_estimar_custo(rec.modelo, ti, to),
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
        custo = await session.scalar(select(func.coalesce(func.sum(AiCall.custo_usd), 0))) or 0
        lat_media = await session.scalar(select(func.avg(AiCall.latencia_ms)))
        eventos = await session.scalar(select(func.count(PipelineEvent.id))) or 0

    return {
        "ai_calls_total": int(total),
        "ai_calls_falhas": int(falhas),
        "tokens_total": int(tokens),
        "custo_usd_estimado": float(custo),
        "latencia_media_ms": round(float(lat_media)) if lat_media else None,
        "pipeline_events_total": int(eventos),
    }
