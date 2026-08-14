"""Sessões opacas no servidor.

O cookie carrega um token aleatório (256 bits); no banco guardamos só o
``sha256(token)``. Validar = achar a sessão pelo hash, conferir que não está
revogada nem expirada (absoluta + inatividade) e renovar ``ultimo_uso``.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.auth.sessao import Sessao
from app.db.models.auth.usuario import Usuario


def _agora() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def gerar_token() -> str:
    """Token de sessão com 256 bits de entropia."""
    return secrets.token_urlsafe(32)


async def criar_sessao(
    session: AsyncSession,
    usuario_id: uuid.UUID,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> str:
    """Cria uma sessão nova e devolve o token EM TEXTO (vai pro cookie).
    Só o hash fica no banco. Não faz commit — quem chama controla a transação."""
    token = gerar_token()
    sessao = Sessao(
        usuario_id=usuario_id,
        token_hash=hash_token(token),
        expira_em=_agora() + timedelta(days=settings.session_dias_absoluto),
        ip=(ip or None),
        user_agent=(user_agent[:400] if user_agent else None),
    )
    session.add(sessao)
    await session.flush()
    return token


async def validar_token(
    session: AsyncSession, token: str
) -> Usuario | None:
    """Devolve o Usuario dono de uma sessão válida, ou None.

    Inválido = não existe / revogada / passou da expiração absoluta / ficou
    parada além da janela de inatividade. Em sessão válida, renova ``ultimo_uso``.
    """
    if not token:
        return None
    sessao = await session.scalar(
        select(Sessao).where(Sessao.token_hash == hash_token(token))
    )
    if sessao is None or sessao.revogada:
        return None

    agora = _agora()
    if sessao.expira_em <= agora:
        return None
    limite_inatividade = sessao.ultimo_uso + timedelta(
        hours=settings.session_horas_inatividade
    )
    if limite_inatividade <= agora:
        return None

    usuario = await session.scalar(
        select(Usuario).where(Usuario.id == sessao.usuario_id)
    )
    if usuario is None or not usuario.ativo:
        return None

    sessao.ultimo_uso = agora
    await session.flush()
    return usuario


async def revogar_token(session: AsyncSession, token: str) -> uuid.UUID | None:
    """Revoga a sessão do token (logout). Devolve o usuario_id revogado, ou None."""
    sessao = await session.scalar(
        select(Sessao).where(Sessao.token_hash == hash_token(token))
    )
    if sessao is None or sessao.revogada:
        return None
    sessao.revogada = True
    await session.flush()
    return sessao.usuario_id


async def revogar_outras(
    session: AsyncSession, usuario_id: uuid.UUID, token_atual: str | None
) -> int:
    """Revoga todas as sessões do usuário MENOS a do token atual (troca de senha)."""
    stmt = update(Sessao).where(
        Sessao.usuario_id == usuario_id, Sessao.revogada.is_(False)
    )
    if token_atual:
        stmt = stmt.where(Sessao.token_hash != hash_token(token_atual))
    res = await session.execute(stmt.values(revogada=True))
    await session.flush()
    return res.rowcount or 0


async def revogar_todas(session: AsyncSession, usuario_id: uuid.UUID) -> int:
    """Revoga TODAS as sessões ativas do usuário ('sair de todos os dispositivos')."""
    res = await session.execute(
        update(Sessao)
        .where(Sessao.usuario_id == usuario_id, Sessao.revogada.is_(False))
        .values(revogada=True)
    )
    await session.flush()
    return res.rowcount or 0
