"""Dependency de autenticação.

``usuario_atual`` é o guarda das rotas protegidas: lê o cookie de sessão, valida
no banco (não revogada, não expirada, renova a inatividade) e devolve o Usuario.
Sem sessão válida → 401.

Não há ``require_permission``: o sistema é mono-usuário. Se o RBAC voltar, volta
como slice própria — não como flag guardando código que não existe.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from app.api.services.auth import sessao_service
from app.api.services.auth.cookie import cookie_name
from app.db.models.auth.usuario import Usuario
from app.db.session import get_session


async def usuario_atual(request: Request) -> Usuario:
    token = request.cookies.get(cookie_name())
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado.")
    async with get_session() as session:
        usuario = await sessao_service.validar_token(session, token)
        if usuario is None:
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
        await session.commit()  # persiste a renovação de ultimo_uso
        return usuario
