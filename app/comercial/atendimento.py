"""O que o bot comercial responde a uma mensagem de lead.

Hoje, o eco do passo 1 (`docs/bot-comercial/07`): prova que o caminho inteiro
funciona (WhatsApp → Chatwoot → Copiloto → Chatwoot) antes de pôr LLM no meio.
O passo 3 tira a resposta daqui do request e a leva para a fila, com debounce
e a barreira de envio; o passo 4 troca o eco pelo Gemini.
"""
from __future__ import annotations

from app.comercial.canal.chatwoot import Chatwoot, MensagemEntrada

_SEM_TEXTO = {
    "audio": "(recebi um áudio)",
    "imagem": "(recebi uma imagem)",
    "arquivo": "(recebi um arquivo)",
}


def resposta(msg: MensagemEntrada) -> str:
    return f"eco: {msg.texto}" if msg.texto else f"eco: {_SEM_TEXTO.get(msg.tipo, '(sem texto)')}"


async def atender(msg: MensagemEntrada, canal: Chatwoot | None = None) -> str | None:
    """Responde, se a conversa está com o bot. Devolve o texto enviado."""
    if not msg.com_o_bot:
        return None
    texto = resposta(msg)
    await (canal or Chatwoot()).enviar_texto(msg.conversa_id, texto)
    return texto
