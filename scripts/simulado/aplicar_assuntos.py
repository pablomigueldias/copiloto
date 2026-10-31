"""Grava o `assunto` do mapa `data/estudo/assuntos.json` nas questões do banco.

    .venv/bin/python scripts/simulado/aplicar_assuntos.py

Mexe **só** na coluna `assunto`. Reimportar os JSON também poria o assunto,
mas reescreveria junto a explicação que eu corrigi pela tela — e este script
existe exatamente para não pagar esse preço por um rótulo.
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import update

from app.config import BASE_DIR
from app.db.models.estudo.questao import Questao
from app.db.session import dispose_engine, get_session
from app.estudo import assuntos

MAPA = BASE_DIR / "data" / "estudo" / "assuntos.json"


async def main() -> int:
    mapa: dict[str, str] = json.loads(MAPA.read_text(encoding="utf-8"))["assuntos"]
    fora = sorted({a for a in mapa.values() if not assuntos.valido(a)})
    if fora:
        raise SystemExit(f"fora do catálogo: {fora}")
    gravadas = 0
    try:
        async with get_session() as s:
            for origem, assunto in mapa.items():
                r = await s.execute(
                    update(Questao).where(Questao.origem == origem).values(assunto=assunto)
                )
                gravadas += r.rowcount
            await s.commit()
    finally:
        await dispose_engine()
    print(f"{gravadas} questão(ões) com assunto; {len(mapa) - gravadas} origem(ns) do mapa sem questão no banco.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
