"""Match e lista branca — o coração da regra anti-alucinação.

O que se protege aqui: o sistema alegar competência que o perfil não tem. Todo
teste de "não cobre" vale mais que os de "cobre" — o erro caro é o falso
positivo, que só aparece na entrevista técnica.
"""
from __future__ import annotations

import json

import pytest

from app.candidatura import match as m
from app.candidatura.extrator import Requisitos
from app.candidatura.perfil import montar_fatos, normalizar
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.llm import gateway
from app.llm.tipos import LLMIndisponivel, RespostaCrua

PERFIL = PerfilMestre(
    nome="Pablo",
    habilidades=[
        {"nome": "Python", "nivel": "avançado"},
        {"nome": "FastAPI", "nivel": "avançado"},
        {"nome": "PostgreSQL", "nivel": "avançado"},
        {"nome": "pgvector", "nivel": "intermediário"},
    ],
    projetos=[
        {"nome": "Copiloto", "stack": ["Python", "FastAPI", "PostgreSQL", "pgvector", "Docker"]},
        {"nome": "Churn Prediction", "stack": ["pandas", "scikit-learn", "FastAPI"]},
    ],
    experiencias=[{"empresa": "Sechat", "cargo": "Analista de Sistemas"}],
    certificacoes=[{"nome": "SQL 2016 - Programação em T-SQL", "tema": "banco de dados"}],
)
FATOS = montar_fatos(PERFIL)


class LLMFalso:
    nome = "falso"

    def __init__(self, cobertos: list[str] | None = None, quebrado: bool = False) -> None:
        self.cobertos = cobertos or []
        self.quebrado = quebrado
        self.chamadas = 0
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.chamadas += 1
        self.prompts.append(prompt)
        if self.quebrado:
            raise LLMIndisponivel("Ollama fora do ar")
        return RespostaCrua(
            texto=json.dumps({"cobertos": self.cobertos}, ensure_ascii=False), modelo=modelo
        )

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


def usar(**kw) -> LLMFalso:
    p = LLMFalso(**kw)
    gateway.usar_provider(p)
    return p


@pytest.fixture(autouse=True)
def restaura():
    yield
    gateway.usar_provider(gateway.OllamaProvider())


# ── Lista branca ──────────────────────────────────────────────────


def test_normaliza_acento_e_caixa():
    assert normalizar("Automação") == "automacao"
    assert normalizar("  PostgreSQL ") == "postgresql"


def test_sinonimo_resolve():
    assert normalizar("Postgres") == "postgresql"
    assert normalizar("bancos vetoriais") == "pgvector"


def test_conheco_o_que_esta_no_perfil():
    assert FATOS.conheco("Python") and FATOS.conheco("postgres")
    assert FATOS.conheco("3+ anos com Python")  # requisito com ruído em volta
    assert FATOS.conheco("Docker")              # veio da stack de um projeto


def test_nao_conheco_o_que_nao_esta():
    # O caso do plano: um 4B quer escrever "Kubernetes" porque combina.
    assert not FATOS.conheco("Kubernetes")
    assert not FATOS.conheco("Salesforce")


def test_palavra_de_ruido_nao_libera_tudo():
    # Se "experiência" contasse, qualquer requisito seria coberto.
    assert not FATOS.conheco("experiência")
    assert not FATOS.conheco("conhecimento avançado")


# ── Match ─────────────────────────────────────────────────────────


async def test_tudo_resolvido_pelo_codigo_nao_chama_llm():
    p = usar()
    req = Requisitos(obrigatorios=["Python", "FastAPI"], stack=["PostgreSQL"])

    r = await m.calcular(req, FATOS)
    assert r.score == 100 and r.gaps == []
    # Comparação normalizada é de graça; inferência não.
    assert p.chamadas == 0


async def test_o_que_o_codigo_nao_resolve_vai_numa_chamada_so():
    p = usar(cobertos=["vivência com arquitetura de dados"])
    req = Requisitos(
        obrigatorios=["Python", "vivência com arquitetura de dados", "Kubernetes em produção"]
    )

    r = await m.calcular(req, FATOS)
    assert p.chamadas == 1
    assert r.gaps == ["Kubernetes em produção"]


async def test_llm_fora_do_ar_vira_gap_e_nao_erro():
    usar(quebrado=True)
    req = Requisitos(obrigatorios=["Python", "vivência com dados"])

    r = await m.calcular(req, FATOS)
    # Modéstia custa menos que alegar o que não dá para provar.
    assert r.gaps == ["vivência com dados"]
    assert r.score == 50


async def test_llm_inventando_requisito_e_ignorado():
    usar(cobertos=["Rust", "Kubernetes"])  # nada disso foi perguntado
    req = Requisitos(obrigatorios=["Terraform"])

    r = await m.calcular(req, FATOS)
    assert r.gaps == ["Terraform"]


async def test_obrigatorio_pesa_mais_que_desejavel():
    usar()
    tenho_o_obrigatorio = await m.calcular(
        Requisitos(obrigatorios=["Python"], desejaveis=["Kubernetes"]), FATOS
    )
    tenho_o_desejavel = await m.calcular(
        Requisitos(obrigatorios=["Kubernetes"], desejaveis=["Python"]), FATOS
    )
    # 0,75 contra 0,25: ter o obrigatório e faltar o desejável é uma vaga
    # que vale tentar; o contrário é perder tempo.
    assert tenho_o_obrigatorio.score == 75 and tenho_o_obrigatorio.veredito == "forte"
    assert tenho_o_desejavel.score == 25 and tenho_o_desejavel.veredito == "fraco"


async def test_evidencia_diz_de_onde_saiu():
    usar()
    r = await m.calcular(Requisitos(obrigatorios=["Python", "Docker"]), FATOS)

    porta = {i.requisito: i.evidencia for i in r.obrigatorios}
    assert porta["Python"] == "habilidade: Python"
    assert "Copiloto" in porta["Docker"]


async def test_destaques_ordenam_os_projetos_pela_vaga():
    usar()
    r = await m.calcular(
        Requisitos(obrigatorios=["Python"], stack=["pandas", "scikit-learn"]), FATOS
    )
    # Vaga de ML: o projeto de ML vem primeiro.
    assert r.destaques[0] == "Churn Prediction"


async def test_vaga_sem_requisito_nao_da_score_falso():
    usar()
    r = await m.calcular(Requisitos(), FATOS)
    assert r.score == 0 and r.veredito == "fraco"
