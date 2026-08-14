from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Usuario(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Quem pode entrar. Sem cadastro público — o usuário nasce por script.

    A senha NUNCA é guardada em texto: ``senha_hash`` é Argon2id (ver
    ``app.api.services.auth.senha_service``). ``email`` é único e normalizado
    pra minúsculas no service.

    Sistema mono-usuário: não há papéis nem permissões. Se um dia houver, o
    RBAC volta como slice própria — não como coluna aqui.
    """

    __tablename__ = "usuarios"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)

    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=expression.true()
    )
    ultimo_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = ({"schema": "auth"},)

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email!r}>"
