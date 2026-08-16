"""Endpoints da fila — /api/fila/*.

O teste que mais importa aqui é o 409: decidir duas vezes tem que falhar pela
API também, não só no serviço. Se a rota deixasse passar, o par de treino
mudaria de valor depois de contado.
"""
from __future__ import annotations

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.fila import servico
from app.llm import gateway

GERADO = "Vi a vaga de vocês e trabalhei com Airflow por dois anos."
MEU = "Rodei Airflow em produção por dois anos. Vi que vocês abriram a vaga."


class SemLLM:
    """A fila não gera texto nem embeda no caminho do request."""

    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("a fila não gera texto")

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def sem_llm():
    gateway.usar_provider(SemLLM())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


@pytest.fixture
async def acao():
    return await servico.criar(
        agente="outreach",
        tipo="email_frio",
        titulo="E-mail para a Acme",
        texto_gerado=GERADO,
        contexto="agência que pediu orçamento",
        payload={"para": "contato@acme.dev"},
    )


def _csrf(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}


async def test_tudo_exige_sessao(client, acao):
    assert (await client.get("/api/fila")).status_code == 401
    assert (await client.get(f"/api/fila/{acao.id}")).status_code == 401
    r = await client.post(f"/api/fila/{acao.id}/decidir", json={"decisao": "aprovar"})
    assert r.status_code == 401


async def test_lista_pendentes(logado, acao):
    corpo = (await logado.get("/api/fila")).json()

    assert corpo["total"] == 1
    assert corpo["por_status"] == {"pendente": 1}
    (item,) = corpo["itens"]
    assert item["titulo"] == "E-mail para a Acme"
    assert item["texto_gerado"] == GERADO
    assert item["payload"] == {"para": "contato@acme.dev"}


async def test_status_invalido(logado, acao):
    r = await logado.get("/api/fila", params={"status": "quase"})
    assert r.status_code == 422


async def test_detalhe_e_404(logado, acao):
    import uuid

    assert (await logado.get(f"/api/fila/{acao.id}")).status_code == 200
    assert (await logado.get(f"/api/fila/{uuid.uuid4()}")).status_code == 404


async def test_aprovar_pela_api(logado, acao):
    r = await logado.post(
        f"/api/fila/{acao.id}/decidir", json={"decisao": "aprovar"}, headers=_csrf(logado)
    )
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["status"] == "aprovada" and corpo["decidida_em"]


async def test_aprovar_com_texto_proprio_vira_editada(logado, acao):
    r = await logado.post(
        f"/api/fila/{acao.id}/decidir",
        json={"decisao": "aprovar", "texto_final": MEU},
        headers=_csrf(logado),
    )
    corpo = r.json()
    assert corpo["status"] == "editada"
    # O par que a F9 vai treinar.
    assert corpo["texto_gerado"] == GERADO and corpo["texto_final"] == MEU


async def test_decidir_duas_vezes_e_409(logado, acao):
    primeira = await logado.post(
        f"/api/fila/{acao.id}/decidir", json={"decisao": "aprovar"}, headers=_csrf(logado)
    )
    assert primeira.status_code == 200

    segunda = await logado.post(
        f"/api/fila/{acao.id}/decidir",
        json={"decisao": "rejeitar", "motivo": "mudei de ideia"},
        headers=_csrf(logado),
    )
    assert segunda.status_code == 409


async def test_decidir_exige_csrf(logado, acao):
    r = await logado.post(f"/api/fila/{acao.id}/decidir", json={"decisao": "aprovar"})
    assert r.status_code == 403


async def test_decisao_invalida(logado, acao):
    r = await logado.post(
        f"/api/fila/{acao.id}/decidir", json={"decisao": "adiar"}, headers=_csrf(logado)
    )
    assert r.status_code == 422
