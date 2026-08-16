"""O worker do Copiloto — trabalho de fundo, fora do processo da API.

    arq app.worker.main.WorkerSettings

Roda junto do PC ligado (§2 do plano): não há servidor 24/7, e isso é decisão,
não limitação. O que o worker garante é que, quando eu abro a máquina, o que
precisava acontecer desde a última sessão já aconteceu.

Por que fora da API: uma varredura de índice leva segundos a minutos e prende a
GPU. Dentro do processo do Uvicorn, isso é latência no request de outra pessoa —
e foi o APScheduler in-process do repo antigo que provou como isso apodrece.

**Uma inferência por vez continua valendo.** O semáforo do gateway é de
processo, então worker e API são dois processos disputando a mesma 2060. Daí
`max_jobs=1`: o worker nunca roda dois jobs ao mesmo tempo, e o pior caso é uma
inferência dele contra uma da API — que é o mesmo pior caso de hoje.
"""
from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.config import settings
from app.db.session import dispose_engine
from app.utils.logger import get_logger
from app.worker.jobs import bater_ponto, embedar_exemplos, marcar_followup, reindexar

logger = get_logger()


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def startup(ctx: dict) -> None:
    logger.info(
        f"Worker subindo · redis={settings.redis_url} · "
        f"reindexa a cada {settings.worker_reindexar_minutos} min"
    )


async def shutdown(ctx: dict) -> None:
    # O engine é singleton de módulo e o pool fica preso ao loop que o criou.
    await dispose_engine()
    logger.info("Worker encerrando.")


def _minutos(intervalo: int) -> set[int]:
    """`{0, 10, 20, ...}` para um intervalo de 10 — o formato que o `cron` quer."""
    intervalo = max(1, min(intervalo, 60))
    return set(range(0, 60, intervalo))


class WorkerSettings:
    redis_settings = redis_settings()
    functions = [bater_ponto, reindexar, embedar_exemplos, marcar_followup]
    cron_jobs = [
        # De minuto em minuto, para o painel notar rápido que o worker caiu. É
        # um SET no Redis: mais barato que o cron que o agenda.
        cron(bater_ponto, minute=set(range(60)), run_at_startup=True),
        # O índice se atualiza sozinho: salvei a nota, ela entra. Não é watcher
        # de filesystem de propósito — ver §2 de docs/fase04.md.
        cron(reindexar, minute=_minutos(settings.worker_reindexar_minutos), run_at_startup=True),
        # Barato e idempotente: se não há exemplo novo, é um SELECT que volta vazio.
        cron(embedar_exemplos, minute=_minutos(5)),
        # Uma vez por dia, de manhã: quem venceu o prazo aparece na lista antes
        # de eu abrir o terminal.
        cron(marcar_followup, hour={8}, minute={5}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    # A GPU é uma só. Ver docstring do módulo.
    max_jobs = 1
    job_timeout = 900  # varredura completa com PDF grande passa de 60 s
    keep_result = 3600
