"""O 503 do Gemini agora é esperado, não é motivo de queda imediata.

Medido em 20/08/2026: 16 falhas em 30 chamadas ao `gemini-3.7-flash`, todas
`503 "high demand ... usually temporary"`. A queda para o modelo local
funcionava — e era esse o problema. A rota híbrida existe porque o modelo local
erra a Lei de Morgan; cair para ele em metade das aulas devolve em silêncio a
qualidade que a medida reprovou.

Sem rede: `httpx.MockTransport` responde o que cada teste mandar.
"""
from __future__ import annotations

import httpx
import pytest

from app.llm.providers import gemini as mod
from app.llm.providers.gemini import GeminiProvider
from app.llm.tipos import LLMIndisponivel

OK = {
    "candidates": [{"content": {"parts": [{"text": "a nota"}]}, "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
}
SOBRECARGA = {
    "error": {
        "code": 503,
        "message": "This model is currently experiencing high demand.",
        "status": "UNAVAILABLE",
    }
}


def provider(respostas: list[httpx.Response], *, chave: str = "k") -> tuple:
    """Devolve (provider, chamadas) — `chamadas` conta os POSTs que saíram."""
    chamadas: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return respostas[min(len(chamadas) - 1, len(respostas) - 1)]

    return GeminiProvider(chave=chave, transport=httpx.MockTransport(responder)), chamadas


@pytest.fixture(autouse=True)
def sem_dormir_de_verdade(monkeypatch):
    """As esperas são reais em produção e instantâneas aqui.

    Sem isto a suíte pagaria ~3 s por teste de backoff — e o que se quer provar
    é a decisão de retentar, não a capacidade do asyncio de dormir.
    """
    dormidas: list[float] = []

    async def falso(s):
        dormidas.append(s)

    monkeypatch.setattr(mod.asyncio, "sleep", falso)
    return dormidas


async def test_503_e_retentado_e_a_segunda_vale():
    p, chamadas = provider([
        httpx.Response(503, json=SOBRECARGA),
        httpx.Response(200, json=OK),
    ])
    r = await p.gerar("oi", modelo="gemini-3.7-flash")

    assert r.texto == "a nota"
    assert len(chamadas) == 2


async def test_desiste_depois_do_teto_e_deixa_o_gateway_cair_para_o_local():
    p, chamadas = provider([httpx.Response(503, json=SOBRECARGA)])

    with pytest.raises(LLMIndisponivel) as e:
        await p.gerar("oi", modelo="gemini-3.7-flash")

    assert len(chamadas) == mod._TENTATIVAS
    # A mensagem tem que dizer que insistiu: no `ai_calls`, é o que separa
    # "a API piscou" de "a API está fora há minutos".
    assert "3 tentativa(s)" in str(e.value)


async def test_429_nao_e_retentado_porque_cota_nao_passa_em_dois_segundos():
    p, chamadas = provider([httpx.Response(429, json={"error": {"code": 429}})])

    with pytest.raises(LLMIndisponivel):
        await p.gerar("oi", modelo="gemini-3.7-flash")

    assert len(chamadas) == 1


async def test_recusa_nao_e_retentada():
    # 400 é prompt malformado: tentar de novo dá o mesmo 400, três vezes.
    p, chamadas = provider([httpx.Response(400, json={"error": {"code": 400}})])

    with pytest.raises(LLMIndisponivel, match="recusa"):
        await p.gerar("oi", modelo="gemini-3.7-flash")

    assert len(chamadas) == 1


async def test_espera_cresce_e_tem_jitter(sem_dormir_de_verdade):
    p, _ = provider([httpx.Response(503, json=SOBRECARGA)])
    with pytest.raises(LLMIndisponivel):
        await p.gerar("oi", modelo="gemini-3.7-flash")

    d1, d2 = sem_dormir_de_verdade
    # ~1 s e ~2 s, com jitter de ±25% — as faixas não se encostam.
    assert 0.75 <= d1 <= 1.25
    assert 1.5 <= d2 <= 2.5


def test_retry_after_curto_manda_e_longo_nao():
    # A API dizendo "2 s" é informação melhor que o meu chute.
    assert 1.5 <= mod._espera(1, {"Retry-After": "2"}) <= 2.5
    # "60 s" não é pedido de espera, é "não vai dar": o teto corta, e o gateway
    # cai para o local em segundos em vez de segurar a tela por um minuto.
    assert mod._espera(1, {"Retry-After": "60"}) <= mod._ESPERA_MAX_S * 1.25


def test_retry_after_lixo_nao_derruba():
    # O cabeçalho também aceita data HTTP, que `float()` não lê.
    assert mod._espera(1, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}) > 0
