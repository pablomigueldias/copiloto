"""Mapeamento Usuario → response e helpers de request (IP/UA)."""
from __future__ import annotations

from fastapi import Request

from app.api.schemas.auth import UsuarioResponse
from app.db.models.auth.usuario import Usuario


def to_response(usuario: Usuario) -> UsuarioResponse:
    return UsuarioResponse(
        id=str(usuario.id),
        email=usuario.email,
        nome=usuario.nome,
        ativo=usuario.ativo,
        ultimo_login=usuario.ultimo_login.isoformat() if usuario.ultimo_login else None,
    )


def ip_do_request(request: Request) -> str | None:
    """IP real do cliente. Atrás de proxy vem em X-Forwarded-For (1º da lista)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def user_agent_do_request(request: Request) -> str | None:
    return request.headers.get("user-agent")
