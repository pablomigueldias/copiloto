"""Importa as questões de reforço e deixa cada reforço pronto para responder.

    .venv/bin/python scripts/simulado/importar_reforco.py data/estudo/reforco/simulado-01.json

O arquivo:

    {"simulado": 1,
     "reforcos": [{"assunto": "Triggers", "rodada": 1, "questoes": [5 questões]}]}

As questões vão para o módulo "Reforço do simulado", num tópico por matéria, e
esses tópicos nascem **pausados**: o reforço é respondido na tela do simulado,
não na revisão do dia, e uma questão de reforço que aparecesse depois na
revisão também deixaria de ser surpresa no simulado seguinte. Pela mesma razão
elas ficam fora do estoque (o simulado só sorteia de tópico ativo).

Idempotente pela origem: rodar de novo corrige o texto das questões; um
reforço que já está pronto não é vinculado duas vezes.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from importar_questoes import CAMPOS, _valida  # noqa: E402

from app.db.models.estudo.agenda import Agenda  # noqa: E402
from app.db.models.estudo.questao import Banca, Modulo, Questao, Topico  # noqa: E402
from app.db.models.estudo.simulado import (  # noqa: E402
    QUESTOES_POR_REFORCO,
    Reforco,
    Simulado,
)
from app.db.session import dispose_engine, get_session  # noqa: E402
from app.estudo import agendamento, servico, simulado  # noqa: E402
from app.estudo import assuntos as cat  # noqa: E402

MODULO = "Reforço do simulado"


async def _topico(s, materia: cat.Materia) -> Topico:
    modulo = await s.scalar(select(Modulo).where(Modulo.nome == MODULO))
    if modulo is None:
        modulo = Modulo(nome=MODULO, trilha="concurso", ordem=9)
        s.add(modulo)
        await s.flush()
    topico = await s.scalar(
        select(Topico).where(Topico.modulo_id == modulo.id, Topico.nome == materia.nome)
    )
    if topico is None:
        topico = Topico(modulo_id=modulo.id, nome=materia.nome, ativo=False,
                        ordem=[m.chave for m in cat.MATERIAS].index(materia.chave))
        s.add(topico)
        await s.flush()
    return topico


async def _importar(caminho: Path) -> int:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    numero = dados["simulado"]
    for bloco in dados["reforcos"]:
        if not cat.valido(bloco["assunto"]):
            raise SystemExit(f"assunto fora do catálogo: {bloco['assunto']}")
        if len(bloco["questoes"]) != QUESTOES_POR_REFORCO:
            raise SystemExit(
                f"{bloco['assunto']}: {len(bloco['questoes'])} questões; o reforço tem "
                f"{QUESTOES_POR_REFORCO}."
            )
        for i, q in enumerate(bloco["questoes"], 1):
            q["assunto"] = bloco["assunto"]
            q["origem"] = (f"Reforço (sem banca) · simulado nº {numero:02d} · "
                           f"{bloco['assunto']} · rodada {bloco['rodada']} · nº {i}")
            _valida(q, i)

    hoje = servico.hoje()
    prontos = 0
    async with get_session() as s:
        sim = await s.scalar(select(Simulado).where(Simulado.numero == numero))
        if sim is None:
            raise SystemExit(f"simulado nº {numero} não existe")
        banca = await s.scalar(select(Banca).where(Banca.nome == "Inéditas"))
        vincular: list[tuple[Reforco, list]] = []
        for bloco in dados["reforcos"]:
            reforco = await s.scalar(select(Reforco).where(
                Reforco.simulado_id == sim.id, Reforco.assunto == bloco["assunto"],
                Reforco.rodada == bloco["rodada"]))
            if reforco is None:
                raise SystemExit(
                    f"simulado nº {numero} não tem reforço de '{bloco['assunto']}' "
                    f"na rodada {bloco['rodada']}"
                )
            aberto = reforco.estado == "aguardando_questoes"
            topico = await _topico(s, cat.ONDE[bloco["assunto"]][0])
            ids = []
            for q in bloco["questoes"]:
                campos = {k: q.get(k) for k in (*CAMPOS, "assunto") if k in q}
                campos.setdefault("alternativas", [])
                campos.setdefault("afirmacoes", [])
                campos.setdefault("dificuldade", 2)
                existente = await s.scalar(select(Questao).where(Questao.origem == q["origem"]))
                if existente is not None:
                    for k, v in campos.items():
                        setattr(existente, k, v)
                    ids.append(existente.id)
                    continue
                if not aberto:
                    # Reforço já respondido não ganha questão nova: ela ficaria
                    # solta no banco, sem reforço que a mostre.
                    continue
                nova = Questao(topico_id=topico.id,
                               banca_id=banca.id if banca else None, **campos)
                s.add(nova)
                await s.flush()
                e = agendamento.inicial(hoje)
                s.add(Agenda(questao_id=nova.id, proxima_em=e.proxima_em,
                             intervalo_dias=e.intervalo_dias, estado=e.estado))
                ids.append(nova.id)
            if aberto:
                vincular.append((reforco, ids))
            else:
                print(f"  {bloco['assunto']} (rodada {bloco['rodada']}): já estava "
                      f"{reforco.estado} — só o texto das questões existentes foi atualizado")
        await s.commit()

    for reforco, ids in vincular:
        await simulado.vincular_reforco(reforco.id, ids)
        prontos += 1
        print(f"  {reforco.assunto} (rodada {reforco.rodada}): pronto, {len(ids)} questões")
    print(f"simulado nº {numero}: {prontos} reforço(s) liberado(s) na tela.")
    return 0


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    try:
        return await _importar(Path(sys.argv[1]))
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
