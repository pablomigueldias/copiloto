"""Importa clínicas e consultórios do CNES para a base de prospecção.

    python scripts/comercial/importar_cnes.py            # capital de SP, tipos 36 e 22
    python scripts/comercial/importar_cnes.py 355030 36  # município e tipos à escolha

Idempotente: rodar de novo só atualiza o que mudou na fonte. Quem some da API
em duas importações seguidas (com os mesmos parâmetros) vira inativo.
"""
from __future__ import annotations

import asyncio
import sys

from app.comercial.prospeccao import cnes
from app.comercial.prospeccao.importacao import importar
from app.db.session import dispose_engine, get_session

MUNICIPIO_PADRAO = "355030"  # São Paulo, código de 6 dígitos que a API usa
TIPOS_PADRAO = (36, 22)
DDD_PADRAO = {"355030": "11"}


async def main() -> int:
    municipio = sys.argv[1] if len(sys.argv) > 1 else MUNICIPIO_PADRAO
    tipos = tuple(int(t) for t in sys.argv[2:]) or TIPOS_PADRAO
    ddd = DDD_PADRAO.get(municipio)
    parametros = {"municipio": municipio, "tipos": list(tipos), "so_ativos": True}
    try:
        async with get_session() as session:
            imp = await importar(session, "cnes", parametros, cnes.buscar(municipio, tipos, ddd))
    finally:
        await dispose_engine()
    print(
        f"importação {imp.id}: {imp.lidos} lidos, {imp.inseridos} inseridos, {imp.atualizados} atualizados, "
        f"{imp.sem_mudanca} sem mudança, {imp.marcados_inativos} marcados inativos, {imp.suprimidos} suprimidos"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
