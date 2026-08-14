from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Sessao(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sessão opaca no servidor — a fonte de verdade do "está logado".

    Em vez de JWT, o token aleatório vai num cookie httpOnly e aqui fica só o
    ``sha256(token)``. Se o banco vazar, os hashes não logam ninguém. Logout =
    ``revogada=True``, com efeito imediato (JWT não tem isso).

    Expiração dupla: ``expira_em`` (absoluta) e inatividade (``ultimo_uso``
    renova a cada request; o service expira se ficar parado tempo demais).
    """

    __tablename__ = "sessoes"

    usuario_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "auth.usuarios.id", ondelete="CASCADE", name="fk_auth_sessoes_usuario"
        ),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ultimo_uso: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    revogada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=expression.false()
    )

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)

    __table_args__ = (
        Index("ix_auth_sessoes_usuario_id", "usuario_id"),
        {"schema": "auth"},
    )

    def __repr__(self) -> str:
        return f"<Sessao id={self.id} usuario_id={self.usuario_id} revogada={self.revogada}>"
