"""O canal Chatwoot do bot comercial (passo 1): normalizar, responder, o webhook.

As fixtures são payloads reais do Chatwoot 4.18 CE local, capturados em
2026-09-27 com leads simulados pela caixa API (`scripts/comercial/chatwoot.py`).
O que mais importa: o bot só responde com a conversa em `pending`, e nunca
responde a si mesmo, a mim ou a uma nota privada.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.comercial import atendimento
from app.comercial.canal import chatwoot
from app.config import settings

FIXTURES = Path(__file__).parent / "fixtures" / "chatwoot"


def _ev(nome: str) -> dict:
    return json.loads((FIXTURES / f"{nome}.json").read_text())


# ── normalizar ────────────────────────────────────────────────────────


def test_entrada_do_lead_vira_mensagem():
    m = chatwoot.normalizar(_ev("entrada_pendente"))
    assert m is not None
    assert (m.texto, m.tipo, m.status, m.com_o_bot) == ("quanto custa?", "texto", "pending", True)
    assert (m.nome, m.telefone, m.conversa_id) == ("Bia Teste", "+5511987654321", 2)
    assert m.provedor_id == "3"


def test_entrada_com_a_conversa_aberta_nao_e_do_bot():
    m = chatwoot.normalizar(_ev("entrada_aberta"))
    assert m is not None and not m.com_o_bot


@pytest.mark.parametrize("nome", ["saida_do_bot", "saida_minha", "nota_privada", "status_aberta"])
def test_o_que_nao_e_entrada_de_lead_fica_de_fora(nome):
    assert chatwoot.normalizar(_ev(nome)) is None


def test_audio_sem_texto_e_entrada_do_tipo_audio():
    ev = _ev("entrada_pendente") | {"content": None, "attachments": [{"file_type": "audio"}]}
    m = chatwoot.normalizar(ev)
    assert (m.tipo, m.texto) == ("audio", None)
    assert atendimento.resposta(m) == "eco: (recebi um áudio)"


def test_mensagem_vazia_sem_anexo_fica_de_fora():
    assert chatwoot.normalizar(_ev("entrada_pendente") | {"content": "  "}) is None


# ── responder ─────────────────────────────────────────────────────────


class _Chatwoot:
    """Um Chatwoot de mentira: grava o que o bot pediu e responde como o de verdade."""

    def __init__(self, status: int = 200):
        self.pedidos: list[tuple[str, dict]] = []
        self.status = status

    def transporte(self) -> httpx.MockTransport:
        def lidar(req: httpx.Request) -> httpx.Response:
            self.pedidos.append((req.url.path, json.loads(req.content), req.headers.get("api_access_token")))
            return httpx.Response(self.status, json={"id": 99})

        return httpx.MockTransport(lidar)


async def test_eco_vai_para_a_conversa_com_o_token_do_bot():
    falso = _Chatwoot()
    canal = chatwoot.Chatwoot("http://cw", 1, "tok", transporte=falso.transporte())
    enviado = await atendimento.atender(chatwoot.normalizar(_ev("entrada_pendente")), canal)
    assert enviado == "eco: quanto custa?"
    assert falso.pedidos == [
        ("/api/v1/accounts/1/conversations/2/messages", {"content": "eco: quanto custa?", "message_type": "outgoing"}, "tok")
    ]


async def test_conversa_com_uma_pessoa_nao_recebe_nada():
    falso = _Chatwoot()
    canal = chatwoot.Chatwoot("http://cw", 1, "tok", transporte=falso.transporte())
    assert await atendimento.atender(chatwoot.normalizar(_ev("entrada_aberta")), canal) is None
    assert falso.pedidos == []


async def test_passar_para_pessoa_abre_a_conversa():
    falso = _Chatwoot()
    await chatwoot.Chatwoot("http://cw", 1, "tok", transporte=falso.transporte()).passar_para_pessoa(2)
    assert falso.pedidos[0][:2] == ("/api/v1/accounts/1/conversations/2/toggle_status", {"status": "open"})


async def test_erro_do_chatwoot_vira_chatwooterro():
    canal = chatwoot.Chatwoot("http://cw", 1, "tok", transporte=_Chatwoot(status=500).transporte())
    with pytest.raises(chatwoot.ChatwootErro):
        await canal.enviar_texto(2, "oi")


# ── webhook ───────────────────────────────────────────────────────────


@pytest.fixture
def segredo(monkeypatch):
    monkeypatch.setattr(settings, "chatwoot_webhook_segredo", "s3gr3do")
    return "s3gr3do"


URL = "/api/comercial/chatwoot/webhook"


async def test_webhook_sem_token_ou_com_token_errado_e_401(client, segredo):
    assert (await client.post(URL, json=_ev("entrada_pendente"))).status_code == 401
    assert (await client.post(f"{URL}?token=errado", json=_ev("entrada_pendente"))).status_code == 401


async def test_webhook_sem_segredo_configurado_recusa_tudo(client, monkeypatch):
    monkeypatch.setattr(settings, "chatwoot_webhook_segredo", "")
    assert (await client.post(f"{URL}?token=", json={})).status_code == 401


async def test_webhook_responde_so_a_conversa_com_o_bot(client, segredo, monkeypatch):
    enviados = []

    async def enviar(self, conversa_id, texto):
        enviados.append((conversa_id, texto))
        return "1"

    monkeypatch.setattr(chatwoot.Chatwoot, "enviar_texto", enviar)
    r = await client.post(f"{URL}?token={segredo}", json=_ev("entrada_pendente"))
    assert r.json() == {"acao": "respondido"}
    r = await client.post(f"{URL}?token={segredo}", json=_ev("entrada_aberta"))
    assert r.json() == {"acao": "com_uma_pessoa"}
    r = await client.post(f"{URL}?token={segredo}", json=_ev("saida_do_bot"))
    assert r.json() == {"acao": "ignorado"}
    assert enviados == [(2, "eco: quanto custa?")]


async def test_webhook_que_nao_consegue_responder_devolve_erro(client, segredo, monkeypatch):
    """O erro faz o Chatwoot abrir a conversa para mim (P27, achado 1)."""

    async def falha(self, conversa_id, texto):
        raise chatwoot.ChatwootErro("fora do ar")

    monkeypatch.setattr(chatwoot.Chatwoot, "enviar_texto", falha)
    assert (await client.post(f"{URL}?token={segredo}", json=_ev("entrada_pendente"))).status_code == 502
