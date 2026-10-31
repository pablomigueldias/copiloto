"""O webhook do Agent Bot do Chatwoot — /api/comercial/chatwoot/*.

Sem login de sessão: quem chama é o Chatwoot. O Agent Bot não assina a chamada,
então o segredo vai na URL (`?token=`) e é conferido em tempo constante.

**Falha de envio devolve 502 de propósito.** Quando o webhook do bot falha, o
Chatwoot marca a conversa como aberta, e ela aparece para mim (P27, achado 1):
o lead nunca fica sem caminho para uma pessoa porque o bot caiu.
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request

from app.comercial import atendimento
from app.comercial.canal import chatwoot
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/api/comercial/chatwoot", tags=["comercial-bot"])


def _autorizado(token: str) -> bool:
    segredo = settings.chatwoot_webhook_segredo
    return bool(segredo) and hmac.compare_digest(token.encode(), segredo.encode())


@router.post("/webhook", summary="Evento do Agent Bot do Chatwoot")
async def webhook(request: Request, token: str = "") -> dict[str, str]:
    if not _autorizado(token):
        raise HTTPException(status_code=401, detail="token do webhook inválido")
    msg = chatwoot.normalizar(await request.json())
    if msg is None:
        return {"acao": "ignorado"}
    if not msg.com_o_bot:
        return {"acao": "com_uma_pessoa"}
    try:
        await atendimento.atender(msg)
    except chatwoot.ChatwootErro as e:
        logger.error(f"[comercial] não respondi a conversa {msg.conversa_id}: {e}")
        raise HTTPException(status_code=502, detail="não consegui responder pelo Chatwoot") from e
    return {"acao": "respondido"}
