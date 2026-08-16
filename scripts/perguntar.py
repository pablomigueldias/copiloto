"""Pergunta ao conhecimento indexado, pelo terminal.

    python scripts/perguntar.py "o que estudei sobre normalização?"
    python scripts/perguntar.py --fonte nota "..."     # só nas notas
    python scripts/perguntar.py --tag bd "..."         # só com essa tag
    python scripts/perguntar.py --trechos "..."        # mostra o que embasou
    python scripts/perguntar.py --so-busca "..."       # sem LLM, só a busca

É a interface da F3 até o front existir. Precisa do Postgres e do Ollama no ar.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.conhecimento.busca import buscar
from app.conhecimento.pergunta import perguntar
from app.db.session import dispose_engine

VERDE, VERMELHO, CINZA, FIM = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pergunta ao conhecimento indexado.")
    p.add_argument("pergunta", help="A pergunta, entre aspas.")
    p.add_argument("--fonte", action="append", help="Filtra por tipo de fonte (pode repetir).")
    p.add_argument("--tag", action="append", help="Filtra por tag (pode repetir).")
    p.add_argument("--limite", type=int, default=5, help="Quantos trechos embasam (padrão 5).")
    p.add_argument("--trechos", action="store_true", help="Mostra os trechos usados.")
    p.add_argument("--so-busca", action="store_true", help="Só a busca, sem chamar o LLM.")
    return p.parse_args()


def _mostrar_trechos(trechos, *, citados: set = frozenset()) -> None:
    print(f"\n{CINZA}--- trechos ---{FIM}")
    for i, t in enumerate(trechos, start=1):
        marca = "✓" if t.id in citados else " "
        distancia = f"{t.distancia:.3f}" if t.distancia is not None else "  —  "
        print(f"{marca} [{i}] {distancia} {t.origem:<8} {t.titulo or t.fonte_ref}")
        print(f"      {CINZA}{t.fonte_ref}{FIM}")


async def _so_busca(args: argparse.Namespace) -> int:
    trechos = await buscar(
        args.pergunta, limite=args.limite, fonte_tipo=args.fonte, tags=args.tag
    )
    if not trechos:
        print("Nada encontrado.")
        return 1
    _mostrar_trechos(trechos)
    return 0


async def _perguntar(args: argparse.Namespace) -> int:
    r = await perguntar(
        args.pergunta,
        limite=args.limite,
        fonte_tipo=args.fonte,
        tags=args.tag,
        agente="copiloto.cli",
    )

    print()
    if not r.respondeu:
        print(f"{VERMELHO}{r.texto}{FIM}  {CINZA}({r.motivo}){FIM}")
    else:
        print(r.texto)
        print(f"\n{VERDE}fontes:{FIM}")
        for t in r.fontes:
            print(f"  · {t.titulo or t.fonte_ref}\n    {CINZA}{t.fonte_ref}{FIM}")

    if args.trechos or not r.respondeu:
        _mostrar_trechos(r.trechos, citados={t.id for t in r.fontes})

    medida = [f"distância {r.distancia:.3f}"] if r.distancia is not None else []
    if r.latencia_ms:
        medida.append(f"{r.latencia_ms / 1000:.1f}s")
    if r.tokens:
        medida.append(f"{r.tokens} tokens")
    if r.modelo:
        medida.append(r.modelo)
    if medida:
        print(f"\n{CINZA}{' · '.join(medida)}{FIM}")

    return 0 if r.respondeu else 1


async def main() -> int:
    args = _argumentos()
    try:
        return await (_so_busca(args) if args.so_busca else _perguntar(args))
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
