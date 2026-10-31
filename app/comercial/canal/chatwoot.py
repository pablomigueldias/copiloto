"""O Chatwoot como canal do bot comercial (passo 1 do `docs/bot-comercial/07`).

O WhatsApp (Cloud API) entrega a mensagem ao **Chatwoot**, que guarda a conversa
e a mostra para mim; o Copiloto entra como **Agent Bot**: o Chatwoot chama o
webhook a cada evento, e o bot responde pela API com o token dele (P27).

Duas regras que vieram do teste da P27 e moram aqui:

- **O bot só age com a conversa em `pending`.** O Chatwoot continua mandando as
  mensagens para o bot depois que a conversa passa para uma pessoa (`open`);
  responder aí seria atropelar quem está atendendo.
- **Passar para uma pessoa é mudar a conversa para `open`.** Devolver ao bot é
  mudar para `pending`, e isso é coisa que eu faço no Chatwoot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

PENDENTE = "pending"
ABERTA = "open"

# O Chatwoot manda `message_type` como texto no webhook e como número na API.
_ENTRADA = {"incoming", 0}


@dataclass(frozen=True)
class MensagemEntrada:
    """Uma mensagem de lead, já sem o formato do Chatwoot."""

    provedor_id: str
    conversa_id: int
    contato_id: int | None
    telefone: str | None
    nome: str | None
    # texto | audio | imagem | arquivo: o bot só entende texto por enquanto
    # (o áudio transcrito é o passo 15), mas sabe o que recebeu.
    tipo: str
    texto: str | None
    status: str
    caixa_id: int | None

    @property
    def com_o_bot(self) -> bool:
        return self.status == PENDENTE


def _tipo(anexos: list[dict[str, Any]]) -> str:
    if not anexos:
        return "texto"
    tipo = (anexos[0].get("file_type") or "").lower()
    return {"audio": "audio", "image": "imagem"}.get(tipo, "arquivo")


def normalizar(evento: dict[str, Any]) -> MensagemEntrada | None:
    """A mensagem de entrada do evento, ou `None` quando não é o que o bot trata.

    Fica de fora: evento que não é `message_created`, mensagem de saída (a do
    próprio bot e a minha), nota privada, e mensagem sem texto nem anexo.
    """
    if evento.get("event") != "message_created":
        return None
    if evento.get("message_type") not in _ENTRADA or evento.get("private"):
        return None
    conversa = evento.get("conversation") or {}
    if not conversa.get("id"):
        return None
    anexos = evento.get("attachments") or []
    texto = (evento.get("content") or "").strip() or None
    if texto is None and not anexos:
        return None
    remetente = evento.get("sender") or {}
    return MensagemEntrada(
        provedor_id=str(evento["id"]),
        conversa_id=int(conversa["id"]),
        contato_id=remetente.get("id"),
        telefone=remetente.get("phone_number") or None,
        nome=remetente.get("name") or None,
        tipo=_tipo(anexos),
        texto=texto,
        status=conversa.get("status") or "",
        caixa_id=(evento.get("inbox") or {}).get("id") or conversa.get("inbox_id"),
    )


class ChatwootErro(Exception):
    pass


class Chatwoot:
    """O que o bot faz no Chatwoot: responder e passar para uma pessoa."""

    def __init__(
        self,
        url: str | None = None,
        conta_id: int | None = None,
        token: str | None = None,
        transporte: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = f"{(url or settings.chatwoot_url).rstrip('/')}/api/v1/accounts/{conta_id or settings.chatwoot_conta_id}"
        self._token = token or settings.chatwoot_bot_token
        self._transporte = transporte

    async def _post(self, caminho: str, corpo: dict[str, Any]) -> dict[str, Any]:
        if not self._token:
            raise ChatwootErro("CHATWOOT_BOT_TOKEN vazio: rode scripts/comercial/chatwoot.py setup")
        async with httpx.AsyncClient(timeout=10, transport=self._transporte) as c:
            r = await c.post(f"{self._base}{caminho}", json=corpo, headers={"api_access_token": self._token})
        if r.status_code >= 400:
            raise ChatwootErro(f"Chatwoot {r.status_code} em {caminho}: {r.text[:200]}")
        return r.json() if r.content else {}

    async def enviar_texto(self, conversa_id: int, texto: str) -> str:
        """Responde na conversa. Devolve o id da mensagem no Chatwoot."""
        r = await self._post(
            f"/conversations/{conversa_id}/messages", {"content": texto, "message_type": "outgoing"}
        )
        return str(r.get("id", ""))

    async def passar_para_pessoa(self, conversa_id: int) -> None:
        await self._post(f"/conversations/{conversa_id}/toggle_status", {"status": ABERTA})
