"""O que o worker faz. Cada job é uma função async normal.

Regra de job neste projeto: **função fina que chama serviço**. A lógica mora em
`app/conhecimento/` e `app/fila/`, e o job só orquestra e mede. Assim o mesmo
trabalho roda pela CLI, pelo teste e pelo worker sem três implementações.

Os dois desta fase são de manutenção — ninguém pediu, mas sem eles o sistema
envelhece: o índice fica velho e os exemplos ficam sem vetor.
"""
from __future__ import annotations

import time

from app.conhecimento import varredura
from app.db.observability import registrar_evento
from app.fila import exemplos
from app.utils.logger import get_logger

logger = get_logger()


async def reindexar(ctx: dict, *, forcar: bool = False) -> dict:
    """A dívida da F2.10: o índice se atualiza sozinho.

    Varredura completa, mas incremental: arquivo sem mudança não é lido nem
    embedado. Quando nada mudou, é o custo de calcular hashes — segundos.
    """
    t0 = time.perf_counter()
    resultados = await varredura.ingerir(forcar=forcar)
    duracao = int((time.perf_counter() - t0) * 1000)

    resumo = {
        tipo: {"indexados": r.indexados, "chunks": r.chunks, "removidos": r.removidos}
        for tipo, r in resultados.items()
    }
    mudou = sum(r.indexados + r.removidos for r in resultados.values())
    erros = sum(r.erros for r in resultados.values())

    # Só registra evento quando algo mudou ou falhou: um job de 10 em 10 minutos
    # que sempre grava enche `pipeline_events` com 144 linhas por dia dizendo
    # "nada aconteceu".
    if mudou or erros:
        await registrar_evento(
            "worker.reindexar",
            status="erro" if erros else "ok",
            detalhe=str(resumo),
            duracao_ms=duracao,
        )
    logger.info(f"reindexar: {mudou} mudança(s) em {duracao} ms")
    return {"duracao_ms": duracao, "mudou": mudou, "erros": erros, "resumo": resumo}


async def embedar_exemplos(ctx: dict) -> int:
    """Preenche o vetor dos exemplos aprovados desde a última passada."""
    return await exemplos.embedar_pendentes()
