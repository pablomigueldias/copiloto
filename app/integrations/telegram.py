"""Telegram como controle remoto — por enquanto, só o aviso.

O plano (§12) quer aprovar do celular. Isso exige bot com polling ou webhook,
autenticação de quem manda o comando e uma máquina de conversa — trabalho que só
paga quando existe fila com volume. Hoje a fila tem o que a F5 ainda não produz.

O que **já** paga: saber que algo chegou sem estar olhando o terminal. É um POST
HTTP, e vale desde a primeira ação.

Desligado por padrão: sem `TELEGRAM_BOT_TOKEN` no `.env`, `avisar()` devolve
`False` e segue a vida. Integração que quebra o fluxo principal quando não está
configurada é integração mal feita — o aviso é conveniência, não requisito.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger()

API = "https://api.telegram.org"
TIMEOUT_S = 10.0


def configurado() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API, timeout=TIMEOUT_S)


async def avisar(texto: str, *, silencioso: bool = False) -> bool:
    """Manda uma mensagem. Devolve se saiu — e nunca levanta exceção.

    O chamador está no meio de outra coisa (criar ação, registrar falha de job);
    falhar o aviso não pode derrubar o que importava.
    """
    if not configurado():
        return False

    try:
        async with _client() as client:
            r = await client.post(
                f"/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": texto[:4000],  # limite da API é 4096
                    "parse_mode": "HTML",
                    "disable_notification": silencioso,
                },
            )
    except Exception as e:  # noqa: BLE001 — aviso é conveniência, não requisito
        logger.warning(f"Telegram indisponível ({type(e).__name__}: {e})")
        return False

    if r.status_code != 200:
        logger.warning(f"Telegram recusou ({r.status_code}): {r.text[:200]}")
        return False
    return True


async def avisar_acao_pendente(acao) -> bool:
    """O card que chega no celular quando algo entra na fila."""
    linhas = [
        f"<b>{acao.titulo}</b>",
        f"<i>{acao.agente} · {acao.tipo}</i>",
    ]
    if acao.texto_gerado:
        linhas.append(f"\n{acao.texto_gerado[:900]}")
    linhas.append(f"\n<code>python scripts/fila.py --ver {str(acao.id)[:8]}</code>")
    return await avisar("\n".join(linhas))
