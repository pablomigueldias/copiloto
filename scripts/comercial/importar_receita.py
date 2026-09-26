"""Importa advocacia, imobiliárias e clínicas da base aberta do CNPJ.

    python scripts/comercial/importar_receita.py PASTA [MUNICIPIO_RECEITA]

PASTA tem os zips de um mês baixados da Receita (Estabelecimentos*.zip,
Empresas*.zip, Simples.zip). O download é passo à parte (P16 do 1.2.8). O
município usa o código da **Receita**: a capital de SP é 7107.

Sócios não são lidos, e o CPF no nome do empresário individual sai antes de
gravar (1.2.6 §4).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.comercial.prospeccao import receita
from app.comercial.prospeccao.importacao import importar
from app.db.session import dispose_engine, get_session


async def main() -> int:
    if len(sys.argv) < 2 or not Path(sys.argv[1]).is_dir():
        print(__doc__)
        return 2
    pasta = Path(sys.argv[1])
    municipio = sys.argv[2] if len(sys.argv) > 2 else "7107"

    estabs = list(receita.estabelecimentos(sorted(pasta.glob("Estabelecimentos*.zip")), municipio))
    basicos = {e[receita.E_BASICO] for e in estabs}
    empresas = receita.por_basico(sorted(pasta.glob("Empresas*.zip")), basicos)
    simples = receita.por_basico(sorted(pasta.glob("Simples*.zip")), basicos)
    registros = (
        receita.para_registro(e, empresas.get(e[receita.E_BASICO]), simples.get(e[receita.E_BASICO])) for e in estabs
    )
    # Sem o mês: é a mesma importação repetida todo mês, e é isso que deixa
    # marcar como inativo quem sumiu da base em dois meses seguidos.
    parametros = {"municipio_receita": municipio, "classes": sorted(receita.CLASSES)}
    try:
        async with get_session() as session:
            imp = await importar(session, "receita_cnpj", parametros, registros)
    finally:
        await dispose_engine()
    print(
        f"importação {imp.id}: {imp.lidos} lidos, {imp.inseridos} inseridos, {imp.atualizados} atualizados, "
        f"{imp.sem_mudanca} sem mudança, {imp.marcados_inativos} marcados inativos, {imp.suprimidos} suprimidos"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
