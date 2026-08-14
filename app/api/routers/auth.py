"""Rotas de autenticação — /api/auth/*."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.dependencies.auth import usuario_atual
from app.api.schemas.auth import (
    LoginRequest,
    MensagemResponse,
    TrocaSenhaRequest,
    UsuarioResponse,
)
from app.api.services.auth import (
    login_service,
    senha_service,
    sessao_service,
    usuario_service,
)
from app.api.services.auth.cookie import (
    clear_session_cookie,
    cookie_name,
    set_session_cookie,
)
from app.api.services.auth.csrf import set_csrf_cookie
from app.api.services.auth.login_service import Bloqueado, CredenciaisInvalidas
from app.api.services.auth.senha_service import SenhaFraca
from app.db.models.auth.usuario import Usuario
from app.db.session import get_session

# Annotated evita o Depends() em default de argumento (B008) e é o idioma
# recomendado pelo FastAPI desde a 0.95.
UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UsuarioResponse, summary="Login (email+senha)")
async def login(body: LoginRequest, request: Request, response: Response) -> UsuarioResponse:
    try:
        token, usuario = await login_service.login(
            body.email,
            body.senha,
            ip=usuario_service.ip_do_request(request),
            user_agent=usuario_service.user_agent_do_request(request),
        )
    except Bloqueado as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except CredenciaisInvalidas as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    set_session_cookie(response, token)
    set_csrf_cookie(response)  # par do double-submit, legível pelo JS
    return usuario_service.to_response(usuario)


@router.get("/me", response_model=UsuarioResponse, summary="Usuário logado")
async def me(response: Response, usuario: UsuarioLogado) -> UsuarioResponse:
    set_csrf_cookie(response)  # garante o cookie CSRF a cada carga do app
    return usuario_service.to_response(usuario)


@router.post(
    "/senha",
    response_model=MensagemResponse,
    summary="Troca a senha (revoga as outras sessões)",
)
async def trocar_senha(
    body: TrocaSenhaRequest,
    request: Request,
    usuario: UsuarioLogado,
) -> MensagemResponse:
    async with get_session() as session:
        u = await session.get(Usuario, usuario.id)
        if u is None or not senha_service.conferir_senha(u.senha_hash, body.senha_atual):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")
        try:
            senha_service.validar_forca(body.senha_nova)
        except SenhaFraca as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        u.senha_hash = senha_service.hash_senha(body.senha_nova)
        n = await sessao_service.revogar_outras(
            session, u.id, request.cookies.get(cookie_name())
        )
        await session.commit()

    return MensagemResponse(
        ok=True, mensagem=f"Senha alterada. {n} outra(s) sessão(ões) encerrada(s)."
    )


@router.post("/logout", response_model=MensagemResponse, summary="Encerra a sessão atual")
async def logout(request: Request, response: Response) -> MensagemResponse:
    token = request.cookies.get(cookie_name())
    if token:
        async with get_session() as session:
            await sessao_service.revogar_token(session, token)
            await session.commit()
    clear_session_cookie(response)
    return MensagemResponse(ok=True, mensagem="Sessão encerrada.")
