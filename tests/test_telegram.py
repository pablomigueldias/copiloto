"""O aviso no Telegram — e a regra de que ele nunca derruba o que importa.

Sem rede: `httpx.MockTransport` responde no lugar da API. O que se testa é o
contrato de integração opcional: desligada por padrão, silenciosa quando falha,
e jamais capaz de impedir uma ação de entrar na fila.
"""
from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.fila import servico
from app.integrations import telegram
from app.llm import gateway


class SemLLM:
    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("não deveria gerar")

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def sem_llm():
    gateway.usar_provider(SemLLM())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
def ligado(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "123:abc")
    monkeypatch.setattr(settings, "telegram_chat_id", "42")


def fingir(monkeypatch, resposta: httpx.Response | Exception) -> list[httpx.Request]:
    """Troca o cliente por um que responde `resposta` e guarda o que recebeu."""
    recebidos: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recebidos.append(request)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(
        telegram,
        "_client",
        lambda: httpx.AsyncClient(
            base_url=telegram.API, transport=httpx.MockTransport(handler)
        ),
    )
    return recebidos


async def test_desligado_sem_token():
    assert telegram.configurado() is False
    assert await telegram.avisar("oi") is False


async def test_manda_a_mensagem(ligado, monkeypatch):
    recebidos = fingir(monkeypatch, httpx.Response(200, json={"ok": True}))

    assert await telegram.avisar("chegou coisa") is True
    (req,) = recebidos
    assert req.url.path == "/bot123:abc/sendMessage"
    import json

    corpo = json.loads(req.content)
    assert corpo["chat_id"] == "42" and corpo["text"] == "chegou coisa"


async def test_api_recusando_nao_levanta(ligado, monkeypatch):
    fingir(monkeypatch, httpx.Response(400, text="chat not found"))
    assert await telegram.avisar("oi") is False


async def test_rede_caida_nao_levanta(ligado, monkeypatch):
    fingir(monkeypatch, httpx.ConnectError("sem rede"))
    assert await telegram.avisar("oi") is False


async def test_mensagem_gigante_e_cortada(ligado, monkeypatch):
    recebidos = fingir(monkeypatch, httpx.Response(200, json={"ok": True}))
    await telegram.avisar("x" * 9000)

    import json

    # O limite da API é 4096; estourar devolveria 400 e perderia o aviso.
    assert len(json.loads(recebidos[0].content)["text"]) == 4000


async def test_acao_nova_avisa_com_o_id_para_abrir(ligado, monkeypatch):
    recebidos = fingir(monkeypatch, httpx.Response(200, json={"ok": True}))
    acao = await servico.criar(
        agente="outreach", tipo="email_frio", titulo="E-mail para a Acme",
        texto_gerado="Texto gerado pelo modelo.",
    )

    import json

    texto = json.loads(recebidos[0].content)["text"]
    assert "E-mail para a Acme" in texto
    assert "Texto gerado pelo modelo." in texto
    assert str(acao.id)[:8] in texto


async def test_telegram_quebrado_nao_impede_a_acao_de_entrar(ligado, monkeypatch):
    fingir(monkeypatch, httpx.ConnectError("sem rede"))

    acao = await servico.criar(agente="outreach", tipo="email_frio", titulo="Acme")
    # A ação existe mesmo com o aviso falhando — é o ponto da integração opcional.
    assert (await servico.obter(acao.id)).status == "pendente"
