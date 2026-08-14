"""Proteção CSRF — double-submit cookie.

Como funciona: além do cookie de sessão (httpOnly), entregamos um cookie CSRF
**legível pelo JS**. Em toda mutação (POST/PUT/PATCH/DELETE) feita com cookie de
sessão, o front lê esse cookie e o reenvia no header ``X-CSRF-Token``. O servidor
exige que header == cookie.

Por que protege: um site malicioso até consegue fazer o browser enviar o cookie
de sessão (é automático), mas a Same-Origin Policy o impede de LER o cookie CSRF
pra montar o header. Sem o header certo → 403. Não precisa de estado no servidor.
"""
from __future__ import annotations

import secrets

from fastapi import Request, Response

from app.config import settings

_MAX_AGE = 7 * 24 * 3600


def csrf_cookie_name() -> str:
    return "__Host-csrf" if settings.session_cookie_secure else "csrf_token"


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    """Seta (ou renova) o cookie CSRF. httpOnly=False de propósito: o JS precisa
    ler pra reenviar no header."""
    token = token or gerar_token()
    response.set_cookie(
        key=csrf_cookie_name(),
        value=token,
        max_age=_MAX_AGE,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return token


def valido(request: Request) -> bool:
    header = request.headers.get("x-csrf-token")
    cookie = request.cookies.get(csrf_cookie_name())
    return bool(header and cookie and secrets.compare_digest(header, cookie))
