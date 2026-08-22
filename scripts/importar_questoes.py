"""Importa um arquivo de questões para o banco de estudo.

    python scripts/importar_questoes.py data/estudo/logica-proposicional.json

Idempotente pela **origem**: cada questão de prova traz "banca · concurso ano ·
cargo · item N", e essa string é única no mundo. Rodar de novo atualiza o
conteúdo da questão e **não toca no agendamento** — que é a razão de agenda e
questão serem tabelas separadas. Um gabarito alterado pela banca entra sem
apagar o histórico de quem já respondeu.

Questão importada nasce vencendo hoje: cadastrar e só ver na tela semana que
vem é o jeito mais rápido de parar de cadastrar.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.models.estudo.agenda import Agenda
from app.db.models.estudo.questao import FORMATOS, Modulo, Questao, Topico
from app.db.session import dispose_engine, get_session
from app.estudo import agendamento, servico

CAMPOS = (
    "formato", "comando", "enunciado", "texto_base", "texto_base_fonte",
    "codigo", "linguagem", "alternativas", "afirmacoes", "gabarito",
    "explicacao", "origem", "fonte", "dificuldade",
)


def _valida(q: dict, i: int) -> None:
    if q["formato"] not in FORMATOS:
        raise SystemExit(f"questão {i}: formato '{q['formato']}' desconhecido")
    if not q.get("origem"):
        raise SystemExit(
            f"questão {i}: sem `origem`. É ela que torna o import idempotente — "
            "e é o que me deixa conferir o gabarito no PDF quando ele parecer errado."
        )
    # A `origem` viaja no payload da fila, junto com a questão que eu estou
    # respondendo. O `gabarito` é omitido dali de propósito; escrever a resposta
    # dentro da origem seria entregá-la pelo DevTools antes de eu responder.
    if re.search(r"gabarito\s*[:=]", q["origem"], re.IGNORECASE):
        raise SystemExit(
            f"questão {i}: a `origem` não pode conter o gabarito — ela vai para a "
            "tela junto com a questão. Identifique o documento e pare aí:\n"
            f"  {q['origem']}"
        )
    esperado = ("C", "E") if q["formato"] == "certo_errado" else ("A", "B", "C", "D", "E")
    if q["gabarito"] not in esperado:
        raise SystemExit(f"questão {i}: gabarito '{q['gabarito']}' fora de {esperado}")
    if q["formato"] not in ("certo_errado", "flashcard") and len(q.get("alternativas", [])) != 5:
        raise SystemExit(f"questão {i}: prova de concurso tem cinco alternativas, não {len(q.get('alternativas', []))}")


async def _importar(caminho: Path) -> int:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    questoes = dados["questoes"]
    for i, q in enumerate(questoes, 1):
        _valida(q, i)

    hoje = servico.hoje()
    novas = atualizadas = 0

    async with get_session() as session:
        m = dados["modulo"]
        modulo = await session.scalar(select(Modulo).where(Modulo.nome == m["nome"]))
        if modulo is None:
            modulo = Modulo(nome=m["nome"], trilha=m.get("trilha", "concurso"), ordem=m.get("ordem", 0))
            session.add(modulo)
            await session.flush()

        t = dados["topico"]
        topico = await session.scalar(
            select(Topico).where(Topico.modulo_id == modulo.id, Topico.nome == t["nome"])
        )
        if topico is None:
            topico = Topico(modulo_id=modulo.id, nome=t["nome"], ordem=t.get("ordem", 0))
            session.add(topico)
            await session.flush()

        for q in questoes:
            campos = {k: q.get(k) for k in CAMPOS if k in q}
            campos.setdefault("alternativas", [])
            campos.setdefault("afirmacoes", [])
            campos.setdefault("dificuldade", 2)

            existente = await session.scalar(
                select(Questao).where(Questao.origem == q["origem"])
            )
            if existente is not None:
                for k, v in campos.items():
                    setattr(existente, k, v)
                existente.topico_id = topico.id
                atualizadas += 1
                continue

            questao = Questao(topico_id=topico.id, **campos)
            session.add(questao)
            await session.flush()
            e = agendamento.inicial(hoje)
            session.add(
                Agenda(
                    questao_id=questao.id,
                    proxima_em=e.proxima_em,
                    intervalo_dias=e.intervalo_dias,
                    acertos_seguidos=e.acertos_seguidos,
                    total_acertos=e.total_acertos,
                    total_erros=e.total_erros,
                    estado=e.estado,
                )
            )
            novas += 1

        await session.commit()

    print(f"{modulo.nome} / {topico.nome}: {novas} nova(s), {atualizadas} atualizada(s).")
    if atualizadas:
        print("Agendamento preservado — conteúdo e desempenho moram em tabelas diferentes.")
    return 0


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    caminho = Path(sys.argv[1])
    if not caminho.is_file():
        print(f"Arquivo não encontrado: {caminho}")
        return 2
    try:
        return await _importar(caminho)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
