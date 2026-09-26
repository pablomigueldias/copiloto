"""Importa as pendências do Pablo de `docs/PENDENCIAS.md` para o quadro `/pendencias`.

    python scripts/importar_pendencias.py            # importa
    python scripts/importar_pendencias.py --ver      # só mostra o que leu

Não duplica: cartão com o mesmo título já no quadro fica como está.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date

from app.config import BASE_DIR
from app.pendencias import importacao

ARQUIVO = BASE_DIR / "docs" / "PENDENCIAS.md"


async def main() -> int:
    if not ARQUIVO.exists():
        print(f"não achei {ARQUIVO}", file=sys.stderr)
        return 1
    texto = ARQUIVO.read_text(encoding="utf-8")
    hoje = date.today()

    if "--ver" in sys.argv:
        for c in importacao.ler(texto, hoje=hoje):
            prazo = c.prazo.strftime("%d/%m/%Y") if c.prazo else "—"
            print(f"[{c.topico}] {c.titulo} · quando: {c.quando or '—'} · prazo: {prazo}")
        return 0

    criados, existiam = await importacao.importar(texto, hoje=hoje)
    print(f"{criados} cartão(ões) criado(s); {existiam} já estava(m) no quadro")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
