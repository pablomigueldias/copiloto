"""Exporta o dataset de preferência que o uso normal produziu.

    python scripts/exportar_dataset.py                 # para data/dataset/
    python scripts/exportar_dataset.py --tipo email_frio
    python scripts/exportar_dataset.py --tudo          # sem curadoria

Cada ação que eu **editei** antes de aprovar é um par:

    texto_gerado  o que o modelo escreveu
    texto_final   o que eu de fato mandei

A curadoria da F9.2 acontece aqui, na origem: edição com menos de 20% de
diferença é typo, nome ou data — não é ensinamento sobre estilo, e infla a
contagem de "quantos pares eu tenho" com material que não treina nada.

O plano manda não começar a F9 antes de ~300 pares **curados**. Este script é o
que diz o número honesto.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select

from app.config import DATA_DIR
from app.db.models.acao_pendente import AcaoPendente
from app.db.session import dispose_engine, get_session

# Abaixo disto a edição não muda o estilo, só conserta detalhe.
DIFERENCA_MINIMA = 0.20


def diferenca(gerado: str, final: str) -> float:
    """0 = idênticos, 1 = nada em comum."""
    return 1.0 - SequenceMatcher(None, gerado, final).ratio()


async def _pares(tipo: str | None) -> list[AcaoPendente]:
    filtros = [AcaoPendente.status == "editada"]
    if tipo:
        filtros.append(AcaoPendente.tipo == tipo)
    async with get_session() as session:
        return list(
            (
                await session.scalars(
                    select(AcaoPendente).where(*filtros).order_by(AcaoPendente.decidida_em)
                )
            ).all()
        )


async def main() -> int:
    p = argparse.ArgumentParser(description="Exporta os pares de preferência.")
    p.add_argument("--tipo", help="Só de um tipo de ação (email_frio, msg_recrutador...).")
    p.add_argument("--tudo", action="store_true", help="Sem curadoria: inclui typo e ajuste mínimo.")
    p.add_argument("--saida", type=Path, help="Arquivo .jsonl (padrão: data/dataset/<data>.jsonl).")
    args = p.parse_args()

    try:
        acoes = await _pares(args.tipo)
        if not acoes:
            print("Nenhuma ação editada ainda. O dataset nasce do uso — edite e aprove.")
            return 0

        linhas, descartados = [], 0
        for a in acoes:
            gerado, final = (a.texto_gerado or "").strip(), (a.texto_final or "").strip()
            if not gerado or not final:
                continue
            d = diferenca(gerado, final)
            if not args.tudo and d < DIFERENCA_MINIMA:
                descartados += 1
                continue
            linhas.append(
                {
                    "tarefa": a.tipo,
                    "contexto": a.contexto or a.titulo,
                    "gerado": gerado,
                    "final": final,
                    "diferenca": round(d, 3),
                    "decidida_em": a.decidida_em.isoformat() if a.decidida_em else None,
                }
            )

        saida = args.saida or (
            DATA_DIR / "dataset" / f"{datetime.now(UTC):%Y-%m-%d}-preferencia.jsonl"
        )
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in linhas), encoding="utf-8"
        )

        print(f"{len(linhas)} pares → {saida}")
        if descartados:
            print(f"{descartados} descartado(s) por diferença < {DIFERENCA_MINIMA:.0%} (typo, nome, data)")
        faltam = 300 - len(linhas)
        print(
            f"faltam ~{faltam} para a F9 valer a pena" if faltam > 0
            else "já dá para pensar em QLoRA (>= 300 pares curados)"
        )
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
