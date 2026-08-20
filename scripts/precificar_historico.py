"""Preenche o `custo_usd` das chamadas que foram gravadas antes da tabela existir.

`PRECOS_USD_1M` estava vazia até 20/08/2026 (§6.2 da Fase C), então toda chamada
anterior tem `custo_usd = NULL` — inclusive as externas, que custaram dinheiro
de verdade. O painel somava isso com `coalesce(..., 0)` e mostrava "US$ 0,00",
que é pior que não ter o número: parece uma medição.

O cálculo é determinístico a partir do que já está gravado (provider, modelo,
tokens), então recalcular não inventa nada. Duas ressalvas honestas:

- o preço aplicado é o de **hoje**, não o da data da chamada. Para as linhas
  que existem isso é indiferente (a promoção do 3.7-flash vale até 31/12/2026 e
  todas são de agosto), mas rodar isto em 2027 sobre linhas de 2026 aplicaria o
  preço errado — por isso o `--ate` existe;
- chamada sem contagem de token continua NULL. Não dá para precificar o que não
  foi medido.

    python scripts/precificar_historico.py            # mostra o que faria
    python scripts/precificar_historico.py --gravar   # grava
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import date

from sqlalchemy import select

from app.db.models.ai_call import AiCall
from app.db.observability import _estimar_custo
from app.db.session import dispose_engine, get_session


async def precificar(*, gravar: bool, ate: date | None) -> None:
    resumo: dict[tuple[str, str], list] = defaultdict(lambda: [0, 0.0, 0])
    async with get_session() as session:
        linhas = (
            await session.scalars(select(AiCall).where(AiCall.custo_usd.is_(None)))
        ).all()

        for c in linhas:
            if ate and c.created_at and c.created_at.date() > ate:
                continue
            custo = _estimar_custo(c.provider, c.modelo, c.tokens_input, c.tokens_output)
            chave = (c.provider, c.modelo)
            if custo is None:
                resumo[chave][2] += 1
                continue
            resumo[chave][0] += 1
            resumo[chave][1] += float(custo)
            if gravar:
                c.custo_usd = custo

        if gravar:
            await session.commit()

    print(f"{'provider/modelo':34} {'precificadas':>12} {'US$':>10} {'sem preço':>10}")
    total = 0.0
    for (provider, modelo), (n, soma, faltam) in sorted(resumo.items()):
        print(f"{provider + '/' + modelo:34} {n:>12} {soma:>10.6f} {faltam:>10}")
        total += soma
    print(f"{'TOTAL':34} {'':>12} {total:>10.6f}")
    print("\n(simulação — use --gravar para escrever)" if not gravar else "\ngravado.")


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gravar", action="store_true", help="escreve no banco")
    p.add_argument("--ate", help="só chamadas até esta data (AAAA-MM-DD)")
    a = p.parse_args()
    try:
        await precificar(gravar=a.gravar, ate=date.fromisoformat(a.ate) if a.ate else None)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
