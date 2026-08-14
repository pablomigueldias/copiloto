from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import expression


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    """PK uuid gerada pelo Postgres (`gen_random_uuid()`, nativo desde o pg13)."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=expression.text("gen_random_uuid()"),
    )


class TimestampMixin:
    """Sempre ``timestamptz``. Guardar timestamp sem fuso é o erro clássico de
    Postgres: some a informação de offset e a conta volta errada em qualquer
    máquina que não esteja em UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
