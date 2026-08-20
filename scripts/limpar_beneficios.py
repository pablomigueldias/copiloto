"""Tira os benefícios das vagas que foram analisadas antes do filtro existir.

O `_sem_beneficios` entrou no `extrator` em 20/08/2026 (§8.1 da Fase C), mas ele
só age na análise **nova**. O que já estava gravado continua com "Gympass" e
"Auxílio creche" entre os requisitos — e daí sobe para a lista de estudo do
painel, que é onde eu vi o problema.

Não há LLM aqui, e não precisa haver: a decisão difícil (o perfil cobre este
requisito?) já foi tomada e está no `match_json`. O que este script faz é
**remover linhas** e refazer uma média — as duas coisas determinísticas.

    python scripts/limpar_beneficios.py            # mostra o que faria
    python scripts/limpar_beneficios.py --gravar   # grava
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.candidatura.extrator import _sem_beneficios
from app.candidatura.match import Item, Match, _score
from app.db.models.pessoal.vaga import Vaga
from app.db.session import dispose_engine, get_session
from app.utils.logger import get_logger

logger = get_logger()


def _limpar_analise(analise: dict) -> tuple[dict, list[str]]:
    """Tira benefício de `obrigatorios` e `desejaveis`. `stack` não se mexe."""
    saiu: list[str] = []
    novo = dict(analise)
    for campo in ("obrigatorios", "desejaveis"):
        fica, sai = _sem_beneficios(list(analise.get(campo) or []))
        novo[campo] = fica
        saiu += sai
    return novo, saiu


def _limpar_match(match: dict) -> tuple[dict, int]:
    """Tira os itens de benefício e **recalcula o score** com o `_score` real.

    Reconstruir o `Match` em vez de fazer a conta à mão é o que garante que o
    score do backfill e o score de uma análise nova saiam da mesma função. Duas
    implementações da mesma regra divergem no primeiro dia.
    """
    novo = dict(match)
    for campo in ("obrigatorios", "desejaveis"):
        itens = list(match.get(campo) or [])
        novo[campo] = [i for i in itens if not _sem_beneficios([i.get("requisito", "")])[1]]

    fica, _ = _sem_beneficios(list(match.get("gaps") or []))
    novo["gaps"] = fica

    reconstruido = Match(
        obrigatorios=[Item(**i) for i in novo["obrigatorios"]],
        desejaveis=[Item(**i) for i in novo["desejaveis"]],
    )
    novo["score"] = _score(reconstruido)
    novo["veredito"] = reconstruido.veredito
    return novo, novo["score"]


async def limpar(*, gravar: bool) -> None:
    async with get_session() as session:
        vagas = (await session.scalars(select(Vaga))).all()

        for v in vagas:
            if not v.analise_json:
                continue
            analise, saiu = _limpar_analise(v.analise_json)
            if not saiu:
                print(f"  {v.empresa or '?'} · {v.titulo[:40]}: nada a tirar")
                continue

            antes = v.match_score
            v.analise_json = analise
            if v.match_json:
                v.match_json, v.match_score = _limpar_match(v.match_json)

            print(
                f"  {v.empresa or '?'} · {v.titulo[:40]}\n"
                f"    {len(saiu)} benefício(s) fora: {', '.join(s[:28] for s in saiu[:4])}…\n"
                f"    score {antes} → {v.match_score}"
            )

        if gravar:
            await session.commit()

    print("\ngravado." if gravar else "\n(simulação — use --gravar para escrever)")


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gravar", action="store_true", help="escreve no banco")
    a = p.parse_args()
    try:
        await limpar(gravar=a.gravar)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
