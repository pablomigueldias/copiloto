"""O gerador de currículo — e a regra que impede o currículo de mentir.

Os testes de rejeição são os mais importantes do projeto inteiro: um bullet com
"Kubernetes" que eu nunca usei não é bug de formatação, é reprovação em
entrevista técnica com a minha cara na frente.
"""
from __future__ import annotations

import json

import pytest

from app.candidatura import curriculo as cur
from app.candidatura.extrator import Requisitos
from app.candidatura.match import Match
from app.candidatura.perfil import montar_fatos
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.llm import gateway
from app.llm.tipos import LLMIndisponivel, RespostaCrua

PERFIL = PerfilMestre(
    nome="Pablo Miguel Dias Ortiz",
    resumo="Desenvolvedor Python com foco em APIs e LLMs.",
    contato={"email": "pablo@exemplo.dev"},
    habilidades=[
        {"nome": "Python"}, {"nome": "FastAPI"}, {"nome": "PostgreSQL"}, {"nome": "Docker"},
    ],
    projetos=[
        {
            "nome": "Copiloto",
            "descricao": "Assistente local com RAG",
            "prova": "1.773 chunks indexados, 216 testes",
            "stack": ["Python", "FastAPI", "PostgreSQL", "pgvector"],
        },
        {"nome": "Churn Prediction", "descricao": "ML de evasão",
         "stack": ["pandas", "scikit-learn"]},
    ],
    experiencias=[{"empresa": "Sechat", "cargo": "Analista de Sistemas", "periodo": "2025",
                   "descricao": "Zoho One e site em Next.js"}],
    formacao=[{"instituicao": "Impacta", "curso": "ADS", "periodo": "2026"}],
    certificacoes=[
        {"nome": "SQL 2016 - T-SQL", "tema": "banco de dados"},
        {"nome": "Fundamentos de Machine Learning", "tema": "machine learning"},
    ],
)
FATOS = montar_fatos(PERFIL)
REQ = Requisitos(obrigatorios=["Python", "FastAPI"], stack=["PostgreSQL"], resumo="APIs")
MATCH = Match(score=80, destaques=["Copiloto"])


class LLMFalso:
    nome = "falso"

    def __init__(self, resposta: dict | None = None, quebrado: bool = False) -> None:
        self.resposta = resposta or {}
        self.quebrado = quebrado
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        if self.quebrado:
            raise LLMIndisponivel("fora do ar")
        return RespostaCrua(texto=json.dumps(self.resposta, ensure_ascii=False), modelo=modelo)

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


async def gerar(resposta: dict, **kw):
    usar(resposta=resposta)
    return await cur.gerar(
        fatos=FATOS, requisitos=REQ, match=MATCH,
        titulo_vaga="Dev Python Pleno", descricao_vaga="Vaga de API em Python",
        usar_few_shot=False, **kw,
    )


BOA = {
    "titulo": "Desenvolvedor Python Pleno",
    "resumo": "Construí APIs em FastAPI com PostgreSQL e integrei modelos locais.",
    "competencias": [
        {"categoria": "Linguagens", "itens": ["Python"]},
        {"categoria": "Backend", "itens": ["FastAPI", "PostgreSQL"]},
    ],
    "experiencias": [
        {"empresa": "Sechat", "bullets": ["Mantive o site em Next.js", "Integrei módulos do Zoho One"]}
    ],
    "projetos": [
        {"nome": "Copiloto", "bullets": [
            "Indexei 1.773 chunks em PostgreSQL com pgvector",
            "Construí a API em FastAPI com testes automatizados",
        ]}
    ],
}


# ── Caminho feliz ─────────────────────────────────────────────────


async def test_gera_curriculo_a_partir_do_perfil():
    c = await gerar(BOA)

    assert c.resumo.startswith("Construí APIs")
    assert c.titulo == "Desenvolvedor Python Pleno"
    # Competências agrupadas — herdado do gerador do Prospector.
    assert c.competencias[0] == {"categoria": "Linguagens", "itens": ["Python"]}
    assert c.competencias_planas == ["Python", "FastAPI", "PostgreSQL"]
    assert c.projetos[0]["nome"] == "Copiloto" and len(c.projetos[0]["bullets"]) == 2
    assert c.rejeitados == []
    # Fatos que não passam pelo modelo: vêm direto do perfil.
    assert c.experiencias[0]["empresa"] == "Sechat"
    assert c.experiencias[0]["cargo"] == "Analista de Sistemas"
    assert c.experiencias[0]["bullets"][0] == "Mantive o site em Next.js"
    assert c.formacao[0]["instituicao"] == "Impacta"


async def test_numero_do_perfil_sobrevive():
    c = await gerar(BOA)
    assert "1.773" in c.projetos[0]["bullets"][0]


# ── Anti-alucinação ───────────────────────────────────────────────


async def test_bullet_com_tecnologia_inventada_e_derrubado():
    c = await gerar({
        **BOA,
        "projetos": [{"nome": "Copiloto", "bullets": [
            "Orquestrei os serviços com Kubernetes em produção",
            "Construí a API em FastAPI",
        ]}],
    })

    assert c.projetos[0]["bullets"] == ["Construí a API em FastAPI"]
    assert any("Kubernetes" in r or "kubernetes" in r for r in c.rejeitados)


async def test_projeto_inexistente_e_derrubado():
    c = await gerar({
        **BOA,
        "projetos": [
            {"nome": "Sistema Bancário XP", "bullets": ["Liderei a migração"]},
            {"nome": "Copiloto", "bullets": ["Construí a API em FastAPI"]},
        ],
    })

    assert [p["nome"] for p in c.projetos] == ["Copiloto"]
    assert any("Sistema Bancário XP" in r for r in c.rejeitados)


async def test_competencia_inventada_nao_entra():
    c = await gerar({**BOA, "competencias": [
        {"categoria": "Infra", "itens": ["Python", "Kubernetes", "Salesforce"]}
    ]})
    # A seção mais lida pelo ATS é a mais fácil de inventar.
    assert c.competencias == [{"categoria": "Infra", "itens": ["Python"]}]


async def test_experiencia_inventada_e_derrubada():
    c = await gerar({**BOA, "experiencias": [
        {"empresa": "Google", "bullets": ["Liderei o time de busca"]}
    ]})
    # A empresa que existe continua no currículo (fato do perfil); a inventada
    # não entra de jeito nenhum.
    assert [e["empresa"] for e in c.experiencias] == ["Sechat"]
    assert any("Google" in r for r in c.rejeitados)


async def test_bullet_de_experiencia_com_invencao_e_derrubado():
    c = await gerar({**BOA, "experiencias": [
        {"empresa": "Sechat", "bullets": ["Migrei tudo para AWS Lambda", "Mantive o site"]}
    ]})
    assert c.experiencias[0]["bullets"] == ["Mantive o site"]


async def test_experiencia_sem_bullet_aprovado_usa_o_perfil():
    c = await gerar({**BOA, "experiencias": []})
    # Melhor a descrição do perfil que uma experiência sem uma linha sequer.
    assert c.experiencias[0]["bullets"] == ["Zoho One e site em Next.js"]


async def test_avisa_experiencia_sem_mes():
    c = await gerar(BOA)
    # Parte dos ATS de 2026 recusa automaticamente entrada sem data completa.
    assert any("sem mês" in a for a in c.avisos)


async def test_resumo_com_invencao_cai_para_o_do_perfil():
    c = await gerar({**BOA, "resumo": "Especialista em Kubernetes e Terraform."})
    assert c.resumo == PERFIL.resumo
    assert any("resumo" in r for r in c.rejeitados)


async def test_tudo_rejeitado_ainda_produz_curriculo():
    c = await gerar({**BOA, "projetos": [
        {"nome": "Inventado", "bullets": ["fiz coisas com Kubernetes"]}
    ]})
    # Página em branco é pior que o texto do próprio perfil.
    assert c.projetos and c.projetos[0]["nome"] == "Copiloto"


def test_verificar_aponta_a_primeira_invencao():
    assert cur.verificar("Usei FastAPI e Kubernetes", FATOS) == "kubernetes"
    assert cur.verificar("Usei FastAPI com PostgreSQL", FATOS) is None


def test_verificar_nao_confunde_portugues_com_tecnologia():
    # Sem isto, "Desenvolvi" e "Automatizei" virariam "tecnologia inventada".
    assert cur.verificar("Desenvolvi APIs REST e automatizei o Pipeline", FATOS) is None


# ── Degradação ────────────────────────────────────────────────────


async def test_llm_fora_do_ar_devolve_o_perfil_cru():
    usar(quebrado=True)
    c = await cur.gerar(
        fatos=FATOS, requisitos=REQ, match=MATCH, titulo_vaga="Dev Python",
        descricao_vaga="x", usar_few_shot=False,
    )
    assert c.resumo == PERFIL.resumo and c.projetos
    assert "Python" in c.competencias_planas


# ── Saída ─────────────────────────────────────────────────────────


async def test_texto_tem_as_secoes_na_ordem_que_o_ats_espera():
    texto = cur.como_texto(await gerar(BOA), FATOS)

    posicoes = [
        texto.index(s)
        for s in ("RESUMO", "COMPETÊNCIAS", "EXPERIÊNCIA PROFISSIONAL", "PROJETOS", "FORMAÇÃO")
    ]
    assert posicoes == sorted(posicoes)
    assert "pablo@exemplo.dev" in texto


async def test_certificacoes_relevantes_primeiro():
    c = await gerar(BOA)
    # Vaga de banco de dados: a certificação de SQL vem antes da de ML.
    assert c.certificacoes[0]["nome"].startswith("SQL")
