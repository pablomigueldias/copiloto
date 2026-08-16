"""Curadoria do dataset — o número que o script imprime precisa ser honesto.

O plano manda não começar a F9 antes de ~300 pares **curados**. Se typo e
correção de nome entrarem na conta, chega-se a 300 sem ter 300 — e treina-se
com material que não ensina estilo nenhum.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.fila import servico
from app.llm import gateway

_spec = importlib.util.spec_from_file_location(
    "exportar_dataset", Path(__file__).resolve().parent.parent / "scripts" / "exportar_dataset.py"
)
exportar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(exportar)

GERADO = (
    "Prezado recrutador, gostaria de me apresentar como candidato à vaga de "
    "engenheiro de dados anunciada recentemente pela sua empresa."
)
MEU = "Vi a vaga de engenheiro de dados. Rodei Airflow em produção por dois anos."


class SemLLM:
    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("export não gera texto")

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def sem_llm():
    gateway.usar_provider(SemLLM())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


async def editada(gerado: str, final: str):
    acao = await servico.criar(
        agente="outreach", tipo="email_frio", titulo="Acme", texto_gerado=gerado,
        contexto="agência que pediu orçamento",
    )
    return await servico.decidir(acao.id, decisao="aprovar", texto_final=final)


def test_diferenca_mede_reescrita_e_nao_typo():
    assert exportar.diferenca(GERADO, MEU) > 0.5
    assert exportar.diferenca("Olá Marcos, tudo bem?", "Olá Marcus, tudo bem?") < 0.1


async def test_exporta_so_as_reescritas_de_verdade(tmp_path):
    await editada(GERADO, MEU)                                  # reescrita
    await editada("Olá Marcos, tudo bem?", "Olá Marcus, tudo bem?")  # typo

    saida = tmp_path / "pares.jsonl"
    import sys

    sys.argv = ["exportar_dataset.py", "--saida", str(saida)]
    assert await exportar.main() == 0

    linhas = [json.loads(x) for x in saida.read_text(encoding="utf-8").splitlines()]
    assert len(linhas) == 1
    assert linhas[0]["gerado"] == GERADO and linhas[0]["final"] == MEU
    assert linhas[0]["tarefa"] == "email_frio"
    assert linhas[0]["contexto"] == "agência que pediu orçamento"


async def test_tudo_ignora_a_curadoria(tmp_path):
    await editada("Olá Marcos, tudo bem?", "Olá Marcus, tudo bem?")

    saida = tmp_path / "tudo.jsonl"
    import sys

    sys.argv = ["exportar_dataset.py", "--saida", str(saida), "--tudo"]
    await exportar.main()
    assert len(saida.read_text(encoding="utf-8").splitlines()) == 1


async def test_aprovada_sem_edicao_nao_e_par(tmp_path):
    acao = await servico.criar(
        agente="outreach", tipo="email_frio", titulo="Acme", texto_gerado=GERADO
    )
    await servico.decidir(acao.id, decisao="aprovar")

    saida = tmp_path / "vazio.jsonl"
    import sys

    sys.argv = ["exportar_dataset.py", "--saida", str(saida)]
    await exportar.main()
    # Sem edição não há preferência: "aprovei como veio" não ensina o que mudar.
    assert not saida.exists() or saida.read_text(encoding="utf-8") == ""
