"""Cookie de sessão — nome e flags num lugar só.

Produção (HTTPS via Caddy): ``__Host-sessao`` com Secure. O prefixo ``__Host-``
força Secure + Path=/ + sem Domain — o cookie mais difícil de forjar. Em dev
sobre http puro o browser rejeita ``__Host-``/Secure, então caímos pra ``sessao``
sem Secure quando ``SESSION_COOKIE_SECURE=false``.
"""
from __future__ import annotations

from fastapi import Response

from app.config import settings


def cookie_name() -> str:
    return "__Host-sessao" if settings.session_cookie_secure else "sessao"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=cookie_name(),
        value=token,
        max_age=settings.session_dias_absoluto * 24 * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=cookie_name(),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
