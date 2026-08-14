"""Login — confere credenciais e abre sessão.

A mensagem de erro é SEMPRE genérica ("email ou senha inválidos") para não
denunciar quais emails existem. O anti-timing correspondente fica no
``senha_service``: mesmo sem usuário, gasta-se o mesmo tempo de CPU.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.api.services.auth import rate_limit, senha_service, sessao_service
from app.api.services.auth.rate_limit import Bloqueado  # noqa: F401 — re-export pro router
from app.db.models.auth.usuario import Usuario
from app.db.session import get_session


class CredenciaisInvalidas(Exception):
    """Login falhou. Vira HTTP 401 com mensagem genérica."""


async def login(
    email: str,
    senha: str,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, Usuario]:
    """Valida email+senha e devolve ``(token_de_sessão, usuario)``."""
    email_norm = (email or "").strip().lower()

    async with get_session() as session:
        # Barreira de força bruta — levanta Bloqueado (→ 429) antes de tudo.
        await rate_limit.checar(session, email_norm, ip)

        usuario = await session.scalar(select(Usuario).where(Usuario.email == email_norm))
        hash_armazenado = usuario.senha_hash if usuario else None
        senha_ok = (
            senha_service.conferir_senha(hash_armazenado, senha)
            and usuario is not None
            and usuario.ativo
        )
        if not senha_ok:
            await rate_limit.registrar(session, email_norm, ip, sucesso=False)
            await session.commit()  # persiste a tentativa falha (alimenta o lockout)
            raise CredenciaisInvalidas("Email ou senha inválidos.")

        await rate_limit.registrar(session, email_norm, ip, sucesso=True)

        # Rehash transparente se os parâmetros do Argon2 mudaram desde o cadastro.
        if senha_service.precisa_rehash(usuario.senha_hash):
            usuario.senha_hash = senha_service.hash_senha(senha)

        usuario.ultimo_login = datetime.now(UTC)
        token = await sessao_service.criar_sessao(
            session, usuario.id, ip=ip, user_agent=user_agent
        )
        await session.commit()
        await session.refresh(usuario)
        return token, usuario
