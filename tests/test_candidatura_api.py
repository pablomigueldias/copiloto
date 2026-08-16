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


# ── Baixar o PDF ──────────────────────────────────────────────────


async def test_baixar_pdf_do_curriculo(logado, perfil):
    vaga = await vagas.criar(descricao=JD, empresa="Nexus")
    await logado.post(f"/api/vagas/{vaga.id}/curriculo", headers=_csrf(logado))

    r = await logado.get(f"/api/vagas/{vaga.id}/curriculo.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    # PDF de verdade começa com %PDF — se vier HTML de erro, o teste pega.
    assert r.content[:4] == b"%PDF"
    assert "curriculo-pablo" in r.headers["content-disposition"]


async def test_pdf_e_reimpresso_mesmo_se_o_arquivo_sumiu(logado, perfil):
    from pathlib import Path

    vaga = await vagas.criar(descricao=JD)
    corpo = (await logado.post(f"/api/vagas/{vaga.id}/curriculo", headers=_csrf(logado))).json()
    Path(corpo["pdf"]).unlink()

    # O texto vive no banco; o arquivo em disco é cache.
    r = await logado.get(f"/api/vagas/{vaga.id}/curriculo.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


async def test_pdf_de_vaga_sem_curriculo_e_409(logado, perfil):
    vaga = await vagas.criar(descricao=JD)
    r = await logado.get(f"/api/vagas/{vaga.id}/curriculo.pdf")
    assert r.status_code == 409 and "ainda não tem currículo" in r.json()["detail"]


async def test_pdf_exige_sessao(client, perfil):
    vaga = await vagas.criar(descricao=JD)
    assert (await client.get(f"/api/vagas/{vaga.id}/curriculo.pdf")).status_code == 401


# ── PATCH: editar a vaga pela tela ──────────────────────────────


async def test_patch_edita_so_o_que_veio(logado):
    vaga = (await logado.post("/api/vagas", json={"descricao": JD, "empresa": "Nexus"},
                              headers=_csrf(logado))).json()

    r = await logado.patch(
        f"/api/vagas/{vaga['id']}",
        json={"senioridade": "pleno", "modelo": "remoto"},
        headers=_csrf(logado),
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["senioridade"] == "pleno"
    assert corpo["modelo"] == "remoto"
    # O que não foi enviado continua onde estava — é PATCH, não PUT.
    assert corpo["empresa"] == "Nexus"


async def test_patch_registra_no_historico(logado):
    vaga = (await logado.post("/api/vagas", json={"descricao": JD},
                              headers=_csrf(logado))).json()
    await logado.patch(f"/api/vagas/{vaga['id']}", json={"empresa": "Acme"},
                       headers=_csrf(logado))

    detalhe = (await logado.get(f"/api/vagas/{vaga['id']}")).json()
    eventos = [e["evento"] for e in detalhe["historico"]]
    assert "editada" in eventos


async def test_patch_recusa_campo_que_nao_e_meu(logado):
    """`match_score` é saída do pipeline: editar à mão faria a métrica mentir."""
    vaga = (await logado.post("/api/vagas", json={"descricao": JD},
                              headers=_csrf(logado))).json()
    r = await logado.patch(f"/api/vagas/{vaga['id']}", json={"match_score": 99},
                           headers=_csrf(logado))
    # Pydantic ignora o desconhecido; sobra um corpo vazio, que é 422.
    assert r.status_code == 422


async def test_patch_recusa_status_invalido(logado):
    vaga = (await logado.post("/api/vagas", json={"descricao": JD},
                              headers=_csrf(logado))).json()
    r = await logado.patch(f"/api/vagas/{vaga['id']}", json={"status": "inventado"},
                           headers=_csrf(logado))
    assert r.status_code == 422


async def test_patch_em_vaga_inexistente_e_404(logado):
    r = await logado.patch(
        "/api/vagas/00000000-0000-0000-0000-000000000000",
        json={"empresa": "Acme"},
        headers=_csrf(logado),
    )
    assert r.status_code == 404


async def test_gerar_com_reanalisar_devolve_a_vaga_junto(logado, perfil):
    """O botão 'analisar + gerar': uma chamada, score novo na mesma resposta."""
    vaga = (await logado.post("/api/vagas", json={"descricao": JD},
                              headers=_csrf(logado))).json()

    r = await logado.post(
        f"/api/vagas/{vaga['id']}/curriculo?reanalisar=true", headers=_csrf(logado)
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["curriculo"]["titulo"]
    assert corpo["vaga"] is not None
    assert corpo["vaga"]["match_score"] is not None
    assert corpo["vaga"]["curriculo_gerado_em"] is not None


async def test_apagar_vaga_leva_o_historico_junto(logado):
    """Vaga colada errada ficava para sempre — e sujava a métrica de funil."""
    vaga = (await logado.post("/api/vagas", json={"descricao": JD},
                              headers=_csrf(logado))).json()

    r = await logado.delete(f"/api/vagas/{vaga['id']}", headers=_csrf(logado))
    assert r.status_code == 204

    assert (await logado.get(f"/api/vagas/{vaga['id']}")).status_code == 404
    # O evento 'salva' existia; o CASCADE tem que ter levado.
    from sqlalchemy import func, select

    from app.db.models.pessoal.candidatura_evento import CandidaturaEvento
    from app.db.session import get_session

    async with get_session() as s:
        sobraram = await s.scalar(select(func.count(CandidaturaEvento.id)))
    assert sobraram == 0


async def test_apagar_vaga_inexistente_e_404(logado):
    r = await logado.delete(
        "/api/vagas/00000000-0000-0000-0000-000000000000", headers=_csrf(logado)
    )
    assert r.status_code == 404


async def test_listagem_nao_manda_os_blocos_json(logado, perfil):
    """87% do payload eram `curriculo_json` e amigos, que a tabela não usa."""
    vaga = (await logado.post("/api/vagas", json={"descricao": JD},
                              headers=_csrf(logado))).json()
    await logado.post(f"/api/vagas/{vaga['id']}/curriculo", headers=_csrf(logado))

    linha = (await logado.get("/api/vagas")).json()["itens"][0]
    assert "curriculo_json" not in linha
    assert "match_json" not in linha
    assert "analise_json" not in linha
    # O que a tabela precisa continua lá — inclusive o ✓ de currículo pronto.
    assert linha["tem_curriculo"] is True
    assert linha["titulo"]

    # E o detalhe, que a gaveta usa, continua trazendo tudo.
    detalhe = (await logado.get(f"/api/vagas/{vaga['id']}")).json()
    assert detalhe["curriculo_json"] and detalhe["analise_json"]
