from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class TentativaLogin(Base, UUIDPrimaryKeyMixin):
    """Log de tentativas de login — base do rate limit e do lockout.

    Uma linha por tentativa (sucesso ou falha). Sem ``updated_at``: é log, nunca
    atualiza. Consultado por janela de tempo, por email e por ip.
    """

    __tablename__ = "tentativas_login"

    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_auth_tentativas_email_created", "email", "created_at"),
        Index("ix_auth_tentativas_ip_created", "ip", "created_at"),
        {"schema": "auth"},
    )
