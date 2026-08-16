"""O worker está vivo? — batimento com TTL no Redis.

O worker existe desde a F4 e nunca tinha sido iniciado. Ninguém percebeu porque
nada na tela contava: 42 PDFs ficaram 14 h fora do índice, e o sintoma ("a busca
não acha meus certificados") não parecia ter relação com a causa.

**Redis e não `pipeline_events`** porque a expiração da chave *é* a semântica
que se quer — sumiu, o worker morreu — sem relógio para comparar nem tabela de
auditoria virando log de heartbeat (144 linhas/dia dizendo "nada aconteceu").

Se o Redis cair, o worker cai junto: "sem chave" e "sem worker" continuam
significando a mesma coisa.
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger()

CHAVE = "copiloto:worker:vivo"

# Três ciclos de folga: uma passada demorada ou um reload não podem acender o
# alarme, mas três intervalos de silêncio já são um worker parado.
CICLOS_DE_TOLERANCIA = 3


def _ttl_segundos() -> int:
    return CICLOS_DE_TOLERANCIA * max(1, settings.worker_reindexar_minutos) * 60


async def marcar_vivo(quando_iso: str) -> None:
    """O worker diz "estou aqui" — chamado a cada passada, custe o que custar."""
    try:
        redis = Redis.from_url(settings.redis_url)
        try:
            await redis.set(CHAVE, quando_iso, ex=_ttl_segundos())
        finally:
            await redis.aclose()
    except Exception as e:  # noqa: BLE001 — heartbeat não pode derrubar o job
        logger.warning(f"Não consegui gravar o batimento do worker: {type(e).__name__}: {e}")


async def visto_em() -> str | None:
    """Quando o worker deu sinal pela última vez, ou `None` se ele não está de pé.

    Nunca levanta: o painel precisa abrir mesmo com o Redis fora — é justamente
    quando essa informação é mais útil.
    """
    try:
        redis = Redis.from_url(settings.redis_url)
        try:
            valor = await redis.get(CHAVE)
        finally:
            await redis.aclose()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Redis fora ao checar o worker: {type(e).__name__}: {e}")
        return None
    return valor.decode() if valor else None
