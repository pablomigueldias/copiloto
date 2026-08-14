"""Endpoints de observabilidade — o que a tela vai consumir."""
from __future__ import annotations

import pytest

from app.db.observability import AiCallRecord, registrar_ai_call, registrar_evento


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


@pytest.fixture
async def com_dados():
    await registrar_ai_call(
        AiCallRecord(
            agente="vaga",
            tarefa="extrair",
            provider="ollama",
            modelo="phi4-mini",
            prompt="prompt secreto",
            resposta="resposta",
            tokens_input=10,
            tokens_output=20,
            latencia_ms=800,
        )
    )
    await registrar_ai_call(
        AiCallRecord(
            agente="candidatura",
            tarefa="redigir",
            provider="ollama",
            modelo="qwen3:4b",
            sucesso=False,
            erro="LLMIndisponivel: fora do ar",
        )
    )
    await registrar_evento("ingestao", status="ok", duracao_ms=15)


async def test_tudo_exige_sessao(client, com_dados):
    for rota in ("/stats", "/ai-calls", "/eventos"):
        assert (await client.get(f"/api/observabilidade{rota}")).status_code == 401


async def test_stats(logado, com_dados):
    r = await logado.get("/api/observabilidade/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["ai_calls_total"] == 2
    assert d["ai_calls_falhas"] == 1
    assert d["tokens_total"] == 30
    assert d["pipeline_events_total"] == 1


async def test_lista_nao_devolve_payload(logado, com_dados):
    r = await logado.get("/api/observabilidade/ai-calls")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 2
    # Prompt e resposta pesam megabytes numa lista — só no detalhe.
    assert "prompt" not in d["itens"][0]
    assert d["itens"][0]["prompt_chars"] is not None or d["itens"][0]["agente"] == "candidatura"


async def test_filtros(logado, com_dados):
    assert (await logado.get("/api/observabilidade/ai-calls?agente=vaga")).json()["total"] == 1
    assert (await logado.get("/api/observabilidade/ai-calls?tarefa=redigir")).json()["total"] == 1
    falhas = (await logado.get("/api/observabilidade/ai-calls?sucesso=false")).json()
    assert falhas["total"] == 1
    assert "LLMIndisponivel" in falhas["itens"][0]["error_message"]


async def test_detalhe_traz_prompt_e_resposta(logado, com_dados):
    lista = (await logado.get("/api/observabilidade/ai-calls?agente=vaga")).json()
    call_id = lista["itens"][0]["id"]

    r = await logado.get(f"/api/observabilidade/ai-calls/{call_id}")
    assert r.status_code == 200
    assert r.json()["prompt"] == "prompt secreto"


async def test_detalhe_inexistente_da_404(logado):
    r = await logado.get("/api/observabilidade/ai-calls/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_eventos(logado, com_dados):
    d = (await logado.get("/api/observabilidade/eventos")).json()
    assert d["total"] == 1
    assert d["itens"][0]["evento"] == "ingestao"
    assert (await logado.get("/api/observabilidade/eventos?status=erro")).json()["total"] == 0


async def test_paginacao(logado, com_dados):
    d = (await logado.get("/api/observabilidade/ai-calls?limite=1")).json()
    assert d["total"] == 2 and len(d["itens"]) == 1
    assert (await logado.get("/api/observabilidade/ai-calls?limite=999")).status_code == 422
