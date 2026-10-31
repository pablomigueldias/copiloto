"""O que falta escrever: cada reforço sem questão, com o erro que o abriu.

    .venv/bin/python scripts/simulado/reforco_pendente.py

É o insumo de quem escreve as 5 de cada assunto (eu, a pedido do Pablo: "gera o
reforço"). Mostra a questão errada inteira, o que ele marcou e o gabarito —
o reforço tem de mirar no engano que aconteceu, não no assunto em abstrato.
Da rodada 2 em diante, entram também as erradas do reforço anterior, e as
origens já usadas, para não repetir questão.
"""
from __future__ import annotations

import asyncio

from app.db.session import dispose_engine
from app.estudo import simulado


def _alternativas(q) -> str:
    return "\n".join(f"      {a['letra']}) {a['texto']}" for a in (q.alternativas or []))


async def main() -> int:
    try:
        pendentes = await simulado.para_escrever()
    finally:
        await dispose_engine()
    if not pendentes:
        print("Nenhum reforço aguardando questões.")
        return 0
    print(f"{len(pendentes)} reforço(s) aguardando questões.\n")
    for p in pendentes:
        print("=" * 78)
        print(f"simulado nº {p['simulado']} · {p['materia']} · {p['assunto']} · rodada {p['rodada']}")
        for e in p["erros"]:
            q = e["questao"]
            print(f"\n  [{e['onde']}] marcou {e['marcou'] or '(em branco)'} · gabarito {q.gabarito}")
            if q.texto_base:
                print(f"    texto: {q.texto_base[:300]}…")
            if q.codigo:
                print(f"    código: {q.codigo}")
            print(f"    {q.comando + ' ' if q.comando else ''}{q.enunciado}")
            for i, a in enumerate(q.afirmacoes or [], 1):
                print(f"      {'I' * i if i < 4 else i}. {a}")
            print(_alternativas(q))
        if p["origens_ja_usadas"]:
            print("\n  já usadas em rodadas anteriores:")
            for o in p["origens_ja_usadas"]:
                print(f"    - {o}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
