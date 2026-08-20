"""Extração de requisitos — com LLM falso.

O valor aqui não é testar o modelo (isso é o script de avaliação): é garantir
que o **normalizador** aguenta as três formas que um modelo pequeno usa para
responder a mesma pergunta, às vezes no mesmo dia.
"""
from __future__ import annotations

import json

import pytest

from app.candidatura.extrator import (
    PROMPT,
    Requisitos,
    _lista_de_textos,
    _sem_beneficios,
    extrair,
)
from app.llm import gateway
from app.llm.tipos import RespostaCrua

JD = "Vaga de dados. Requisitos: Python, Airflow. Desejável: dbt." * 3


class LLMFalso:
    nome = "falso"

    def __init__(self, resposta: dict) -> None:
        self.resposta = resposta
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        return RespostaCrua(
            texto=json.dumps(self.resposta, ensure_ascii=False), modelo=modelo,
            tokens_input=50, tokens_output=30,
        )

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


def usar(resposta: dict) -> LLMFalso:
    p = LLMFalso(resposta)
    gateway.usar_provider(p)
    return p


@pytest.fixture(autouse=True)
def restaura():
    yield
    gateway.usar_provider(gateway.OllamaProvider())


COMPLETA = {
    "obrigatorios": ["Python", "Airflow", "SQL avançado"],
    "desejaveis": ["dbt"],
    "stack": ["Python", "Airflow", "SQL", "dbt"],
    "senioridade": "pleno",
    "modelo": "remoto",
    "resumo": "Construir e manter pipelines de dados.",
}


async def test_extrai_e_normaliza():
    p = usar(COMPLETA)
    req = await extrair(JD, alvo_ref="vaga:1")

    assert req.obrigatorios == ["Python", "Airflow", "SQL avançado"]
    assert req.senioridade == "pleno" and req.modelo == "remoto"
    assert JD[:60] in p.prompts[0]


async def test_descricao_vazia_nao_chama_o_modelo():
    p = usar(COMPLETA)
    assert (await extrair("   ")).obrigatorios == []
    assert p.prompts == []


async def test_descricao_gigante_e_cortada():
    p = usar(COMPLETA)
    await extrair("x" * 20_000)
    # 8k de contexto: mandar 20 mil caracteres é estourar e perder o fim.
    assert len(p.prompts[0]) < 8_000


def test_normaliza_lista_de_dicts():
    # O phi4-mini responde isto quando está inspirado.
    assert _lista_de_textos([{"nome": "Python"}, {"requisito": "SQL"}]) == ["Python", "SQL"]


def test_normaliza_string_com_virgula():
    assert _lista_de_textos("Python, SQL, Docker") == ["Python", "SQL", "Docker"]


def test_normaliza_marcadores_e_duplicatas():
    assert _lista_de_textos(["- Python", "• python", "Python"]) == ["Python"]


def test_normaliza_lixo():
    assert _lista_de_textos(None) == [] and _lista_de_textos(42) == []


def test_como_json_e_o_que_vai_para_o_banco():
    d = Requisitos(obrigatorios=["Python"]).como_json()
    assert d["obrigatorios"] == ["Python"] and d["stack"] == []


# ── Benefício não é requisito (§6.1 da Fase C) ────────────────────
#
# A vaga real que motivou o filtro: "Engenheiro de Dados - IA/ML" da Accenture,
# cujos 12 desejáveis eram todos benefícios. O score caía 9 pontos de graça e o
# painel mandava estudar Gympass.
ACCENTURE = [
    "Assistência médica", "Vale refeição", "Seguro de vida", "Previdência privada",
    "Gympass", "Opção de compra de ações", "Desconto em farmácia", "Auxílio creche",
    "escola de idiomas", "Licença maternidade", "PPR",
]


def test_beneficio_sai_dos_desejaveis():
    fica, sai = _sem_beneficios(ACCENTURE)
    assert fica == [] and len(sai) == 11


def test_requisito_tecnico_fica():
    fica, sai = _sem_beneficios(["ECS/Fargate", "Terraform", "OpenTelemetry", "LangChain"])
    assert sai == [] and len(fica) == 4


def test_termo_generico_nao_derruba_requisito_honesto():
    # O caro é o falso positivo: apagar exigência real da vaga. "seguro de vida"
    # é benefício, "segurança da informação" não; "escola de idiomas" é
    # benefício, "inglês avançado" não.
    fica, sai = _sem_beneficios(
        ["Segurança da informação", "Inglês avançado", "Análise de dados", "AWS"]
    )
    assert sai == []


def test_hifen_e_acento_nao_escondem_o_beneficio():
    _, sai = _sem_beneficios(["Vale-refeição", "vale alimentacao", "PLR", "Day off"])
    assert len(sai) == 4


async def test_extrair_devolve_desejaveis_sem_beneficio():
    usar({**COMPLETA, "desejaveis": ["dbt", *ACCENTURE], "obrigatorios": ["Python", "Gympass"]})
    req = await extrair(JD)

    assert req.desejaveis == ["dbt"]
    assert req.obrigatorios == ["Python"]


def test_prompt_manda_ignorar_beneficio():
    # A primeira linha de defesa: o modelo pequeno copia a forma da lista de
    # bullets, e a seção de benefícios tem a mesma cara da de requisitos.
    assert "Benefício NÃO é requisito" in PROMPT
