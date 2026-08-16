"""Indexa as fontes de conhecimento configuradas no .env.

    python scripts/ingerir.py                              # tudo
    python scripts/ingerir.py --fonte nota                 # só as notas
    python scripts/ingerir.py --fonte nota --caminho ~/x   # só esta pasta
    python scripts/ingerir.py --forcar                     # ignora o hash
    python scripts/ingerir.py --listar                     # o que já está indexado

Precisa do Ollama no ar (o embedder) e do Postgres. A segunda execução deve
mostrar tudo como "inalterado" — se não mostrar, o incremental está quebrado, e
isso é mais importante que a velocidade da primeira.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.conhecimento.indexador import inventario, totais_por_tipo
from app.conhecimento.varredura import TIPOS, caminhos_configurados, ingerir
from app.db.session import dispose_engine


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Indexa o conhecimento no Postgres.")
    p.add_argument(
        "--fonte",
        action="append",
        choices=TIPOS,
        help="Tipo de fonte (pode repetir). Padrão: todas.",
    )
    p.add_argument("--caminho", help="Varre só este arquivo/pasta (não remove nada do índice).")
    p.add_argument("--forcar", action="store_true", help="Reindexa mesmo sem mudança de hash.")
    p.add_argument("--listar", action="store_true", help="Só mostra o que está indexado.")
    return p.parse_args()


async def _listar() -> int:
    total, fontes = await inventario(limite=500)
    if not fontes:
        print("Índice vazio. Rode `python scripts/ingerir.py`.")
        return 0

    print(f"{total} fontes indexadas\n")
    print(f"{'TIPO':<8} {'CHUNKS':>7}  {'ATUALIZADO':<17} FONTE")
    for f in fontes:
        print(
            f"{f.fonte_tipo:<8} {f.chunks:>7}  "
            f"{f.atualizado_em:%d/%m/%Y %H:%M}  {f.fonte_ref}"
        )
    print("\nchunks por tipo:", ", ".join(f"{t}={n}" for t, n in sorted((await totais_por_tipo()).items())))
    return 0


async def _ingerir(args: argparse.Namespace) -> int:
    tipos = args.fonte or list(TIPOS)
    if not args.caminho:
        for tipo in tipos:
            if tipo in ("nota", "repo", "pdf") and not caminhos_configurados(tipo):
                print(f"aviso: nenhuma pasta configurada para '{tipo}' em CONHECIMENTO_FONTES")

    resultados = await ingerir(tipos=tipos, caminho=args.caminho, forcar=args.forcar)
    if not resultados:
        print("Nada a fazer.")
        return 0

    print()
    for tipo, r in resultados.items():
        print(f"{tipo:<8} {r}")
    return 1 if any(r.erros for r in resultados.values()) else 0


async def main() -> int:
    args = _argumentos()
    try:
        return await (_listar() if args.listar else _ingerir(args))
    finally:
        # Mesmo event loop do engine — dispor fora dele derruba conexões asyncpg
        # com warning.
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
