"""Endpoints da candidatura — /api/vagas/*.

Sem Ollama: o provider falso devolve JSON fixo. O que se verifica é o contrato
da API, incluindo o 409 quando não há Perfil Mestre — sem perfil não há
currículo, e o erro precisa dizer isso em vez de gerar página em branco.
"""
from __future__ import annotations

import json

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.candidatura import vagas
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.session import get_session
from app.llm import gateway
from app.llm.tipos import RespostaCrua

JD = """Analista de Automação e IA (Pleno)
Requisitos: Python, FastAPI, PostgreSQL. Desejável: Docker.
Envie para talentos@nexus.dev
"""

RESPOSTAS = {
    "obrigatorios": ["Python", "FastAPI"],
    "desejaveis": ["Docker"],
    "stack": ["Python", "FastAPI", "PostgreSQL"],
    "senioridade": "pleno",
    "modelo": "remoto",
    "resumo": "Automatizar processos com Python.",
    "cobertos": [],
    "titulo": "Analista de Automação e IA",
    "competencias": [{"categoria": "Backend", "itens": ["Python", "FastAPI"]}],
    "experiencias": [{"empresa": "Sechat", "bullets": ["Administrei o Zoho One"]}],
    "projetos": [{"nome": "Copiloto", "bullets": ["Construí a API em FastAPI"]}],
}


class LLMFalso:
    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        return RespostaCrua(texto=json.dumps(RESPOSTAS, ensure_ascii=False), modelo=modelo)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def sem_ollama():
    gateway.usar_provider(LLMFalso())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
async def perfil():
    async with get_session() as s:
        p = PerfilMestre(
            nome="Pablo",
            resumo="Dev Python.",
            contato={"email": "pablo@exemplo.dev"},
            habilidades=[{"nome": "Python"}, {"nome": "FastAPI"}, {"nome": "PostgreSQL"}],
            projetos=[{"nome": "Copiloto", "descricao": "RAG local",
                       "stack": ["Python", "FastAPI"]}],
            experiencias=[{"empresa": "Sechat", "cargo": "Analista",
                           "periodo": "jan/2025 – dez/2025", "descricao": "Zoho One"}],
        )
        s.add(p)
        await s.commit()
    return p


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


def _csrf(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}


async def test_tudo_exige_sessao(client):
    assert (await client.get("/api/vagas")).status_code == 401
    assert (await client.post("/api/vagas", json={"descricao": JD * 2})).status_code == 401
    assert (await client.get("/api/vagas/metricas")).status_code == 401


async def test_colar_vaga(logado):
    r = await logado.post(
        "/api/vagas", json={"descricao": JD, "empresa": "Nexus"}, headers=_csrf(logado)
    )
    assert r.status_code == 201

    corpo = r.json()
    assert corpo["status"] == "quero_candidatar"
    assert corpo["contato_email"] == "talentos@nexus.dev"
    assert corpo["empresa"] == "Nexus"


async def test_descricao_curta_e_422(logado):
    r = await logado.post("/api/vagas", json={"descricao": "dev"}, headers=_csrf(logado))
    assert r.status_code == 422


async def test_analisar_preenche_requisitos_e_match(logado, perfil):
    vaga = await vagas.criar(descricao=JD)
    r = await logado.post(f"/api/vagas/{vaga.id}/analisar", headers=_csrf(logado))
    assert r.status_code == 200

    corpo = r.json()
    assert corpo["analise_json"]["obrigatorios"] == ["Python", "FastAPI"]
    assert corpo["match_score"] > 0
    assert corpo["senioridade"] == "pleno"


async def test_gerar_curriculo_devolve_pdf_e_acao(logado, perfil):
    vaga = await vagas.criar(descricao=JD)
    r = await logado.post(f"/api/vagas/{vaga.id}/curriculo", headers=_csrf(logado))
    assert r.status_code == 200

    corpo = r.json()
    assert corpo["pdf"].endswith(".pdf")
    assert corpo["acao_id"], "o currículo entra na fila para eu decidir"
    assert corpo["curriculo"]["projetos"][0]["nome"] == "Copiloto"
    assert corpo["rejeitados"] == []


async def test_sem_perfil_mestre_e_409(logado):
    vaga = await vagas.criar(descricao=JD)
    r = await logado.post(f"/api/vagas/{vaga.id}/analisar", headers=_csrf(logado))
    # Sem perfil não há currículo — e o erro precisa dizer o que fazer.
    assert r.status_code == 409 and "importar_perfil" in r.json()["detail"]


async def test_registrar_evento_move_o_status(logado, perfil):
    vaga = await vagas.criar(descricao=JD)
    r = await logado.post(
        f"/api/vagas/{vaga.id}/evento", json={"evento": "enviada"}, headers=_csrf(logado)
    )
    assert r.json()["status"] == "candidatei"


async def test_evento_invalido_e_422(logado):
    vaga = await vagas.criar(descricao=JD)
    r = await logado.post(
        f"/api/vagas/{vaga.id}/evento", json={"evento": "contratado"}, headers=_csrf(logado)
    )
    assert r.status_code == 422


async def test_detalhe_traz_historico(logado):
    vaga = await vagas.criar(descricao=JD)
    corpo = (await logado.get(f"/api/vagas/{vaga.id}")).json()
    assert corpo["descricao"].startswith("Analista")
    assert [e["evento"] for e in corpo["historico"]] == ["salva"]


async def test_vaga_inexistente_e_404(logado):
    import uuid

    assert (await logado.get(f"/api/vagas/{uuid.uuid4()}")).status_code == 404


async def test_metricas(logado, perfil):
    vaga = await vagas.criar(descricao=JD)
    await vagas.registrar_evento(vaga.id, "enviada")

    corpo = (await logado.get("/api/vagas/metricas")).json()
    assert corpo["funil"]["enviada"] == 1
    assert corpo["por_status"] == {"candidatei": 1}
