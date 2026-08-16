"""Avaliação da resposta ancorada — o bake-off da F3.

Doze perguntas fixas contra o índice real: oito que **têm** resposta nele e
quatro que **não têm**. Para cada uma, mede o que dá para medir sem opinião:

    caiu no piso?   citou?   citou a fonte esperada?   quanto demorou?

Não é teste de unidade (depende do Ollama, do índice desta máquina e do humor
do modelo). É evidência para decidir três coisas que hoje estão no chute:

1. o corte de 0,55 recusa pergunta que tinha resposta?
2. o modelo admite o vazio quando os trechos vêm perto mas não respondem?
3. o reranker é necessário — a fonte certa está entre os 5, mas mal colocada?

    python scripts/avaliar_pergunta.py
    python scripts/avaliar_pergunta.py --limite 3    # com menos trechos
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

from app.conhecimento.pergunta import DISTANCIA_MAXIMA, perguntar
from app.db.session import dispose_engine

# (pergunta, trecho esperado no caminho da fonte | None se não deve responder)
CASOS: tuple[tuple[str, str | None], ...] = (
    ("o que eu estudei sobre normalização de banco de dados?", "Normalização"),
    ("o que é overfitting e como evitar?", "Machine Learning"),
    ("o que é uma chave primária e uma chave estrangeira?", "Bancos de Dados"),
    ("quando um agente de IA atrapalha o gerenciamento de projeto?", "Agentes de IA"),
    ("quanto de VRAM tem a minha placa e quais modelos cabem juntos?", "fase1.md"),
    ("por que escolhi dois modelos especialistas em vez de um 8B?", "refatoracao.md"),
    ("como funciona a busca híbrida do copiloto e o que é RRF?", "fase02.md"),
    ("qual é a regra anti-alucinação do gerador de currículo?", "refatoracao.md"),
    # Sem resposta no índice — o certo é recusar.
    ("qual a capital da Mongólia?", None),
    ("receita de bolo de cenoura com cobertura de brigadeiro", None),
    ("como trocar o óleo do câmbio automático de um Corolla", None),
    ("quais são as regras do roque no xadrez?", None),
)


async def main() -> int:
    p = argparse.ArgumentParser(description="Avalia a resposta ancorada.")
    p.add_argument("--limite", type=int, default=5, help="Trechos por pergunta (padrão 5).")
    args = p.parse_args()

    acertos = erros = 0
    linhas: list[str] = []
    t_total = time.perf_counter()

    try:
        for pergunta, esperado in CASOS:
            t0 = time.perf_counter()
            r = await perguntar(pergunta, limite=args.limite, agente="avaliacao")
            segundos = time.perf_counter() - t0

            if esperado is None:
                ok = not r.respondeu
                situacao = "recusou" if ok else "RESPONDEU (devia recusar)"
            else:
                citou_certo = any(esperado.lower() in t.fonte_ref.lower() for t in r.fontes)
                achou_no_contexto = any(
                    esperado.lower() in t.fonte_ref.lower() for t in r.trechos
                )
                ok = r.respondeu and citou_certo
                if ok:
                    situacao = f"citou {len(r.fontes)} fonte(s)"
                elif not r.respondeu:
                    situacao = f"NÃO RESPONDEU ({r.motivo})"
                elif achou_no_contexto:
                    # O caso que justificaria reranker: a fonte veio na busca e
                    # o modelo citou outra.
                    situacao = "citou fonte ERRADA (a certa estava no contexto)"
                else:
                    situacao = "a fonte certa nem apareceu na busca"

            acertos, erros = (acertos + 1, erros) if ok else (acertos, erros + 1)
            distancia = f"{r.distancia:.3f}" if r.distancia is not None else "  —  "
            linhas.append(
                f"{'✓' if ok else '✗'} {distancia} {segundos:5.1f}s  "
                f"{pergunta[:52]:<52} {situacao}"
            )
            print(linhas[-1], flush=True)

        print(f"\n{'=' * 100}")
        print(f"{acertos}/{len(CASOS)} corretas · {erros} erradas · "
              f"{time.perf_counter() - t_total:.0f}s no total · corte {DISTANCIA_MAXIMA}")
        return 0 if erros == 0 else 1
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
