"""Rate limit + lockout do login (base: tabela auth.tentativas_login).

Duas barreiras independentes, ambas por janela de tempo:
- **por IP**: trava um IP que dispara muitas falhas (scan/brute force distribuído
  numa conta só não passa, mas brute force de um IP em várias contas trava aqui).
- **por conta (email)**: trava a conta após N falhas seguidas, com lockout
  **progressivo** (cada falha extra aumenta o tempo de espera).

Suficiente em Postgres pra poucos usuários (o plano prevê migrar pra Redis se
crescer). A mensagem de bloqueio pode ser específica (não vaza se o email existe
— qualquer email muito tentado trava igual).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth.tentativa_login import TentativaLogin

JANELA = timedelta(minutes=15)        # janela de contagem
LIMITE_IP = 10                         # falhas/janela por IP → bloqueia
LIMITE_CONTA = 5                       # falhas/janela por conta → lockout
LOCKOUT_BASE_MIN = 5                   # 1ª trava de conta (minutos)
LOCKOUT_MAX_MIN = 120                  # teto do lockout progressivo


class Bloqueado(Exception):
    """Login barrado por rate limit/lockout — vira HTTP 429."""


def _agora() -> datetime:
    return datetime.now(UTC)


async def registrar(
    session: AsyncSession,
    email: str | None,
    ip: str | None,
    *,
    sucesso: bool,
) -> None:
    session.add(TentativaLogin(email=email, ip=ip, sucesso=sucesso))
    await session.flush()


async def _conta_falhas(session, *, coluna, valor, desde) -> int:
    if not valor:
        return 0
    return int(
        await session.scalar(
            select(func.count())
            .select_from(TentativaLogin)
            .where(
                coluna == valor,
                TentativaLogin.sucesso.is_(False),
                TentativaLogin.created_at >= desde,
            )
        )
        or 0
    )


async def checar(
    session: AsyncSession, email: str | None, ip: str | None
) -> None:
    """Levanta Bloqueado se o IP ou a conta estourou o limite. Não registra nada."""
    agora = _agora()
    janela_inicio = agora - JANELA

    # ── por IP ───────────────────────────────────────────────────────
    falhas_ip = await _conta_falhas(
        session, coluna=TentativaLogin.ip, valor=ip, desde=janela_inicio
    )
    if falhas_ip >= LIMITE_IP:
        raise Bloqueado("Muitas tentativas. Tente novamente em alguns minutos.")

    # ── por conta (desde o último sucesso, dentro da janela) ─────────
    if not email:
        return
    ultimo_sucesso = await session.scalar(
        select(func.max(TentativaLogin.created_at)).where(
            TentativaLogin.email == email,
            TentativaLogin.sucesso.is_(True),
            TentativaLogin.created_at >= janela_inicio,
        )
    )
    corte = max(janela_inicio, ultimo_sucesso) if ultimo_sucesso else janela_inicio

    falhas_conta = int(
        await session.scalar(
            select(func.count())
            .select_from(TentativaLogin)
            .where(
                TentativaLogin.email == email,
                TentativaLogin.sucesso.is_(False),
                TentativaLogin.created_at > corte,
            )
        )
        or 0
    )
    if falhas_conta < LIMITE_CONTA:
        return

    ultima_falha = await session.scalar(
        select(func.max(TentativaLogin.created_at)).where(
            TentativaLogin.email == email,
            TentativaLogin.sucesso.is_(False),
            TentativaLogin.created_at > corte,
        )
    )
    # Lockout progressivo: dobra a cada falha além do limite, com teto.
    minutos = min(
        LOCKOUT_BASE_MIN * (2 ** (falhas_conta - LIMITE_CONTA)), LOCKOUT_MAX_MIN
    )
    if ultima_falha and agora < ultima_falha + timedelta(minutes=minutos):
        raise Bloqueado(
            "Conta temporariamente bloqueada por excesso de tentativas. "
            "Tente novamente mais tarde."
        )
