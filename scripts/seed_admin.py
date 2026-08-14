"""Cria (ou reativa) o usuário inicial a partir de ADMIN_EMAIL/ADMIN_SENHA_INICIAL.

Idempotente: rodar de novo não duplica nem sobrescreve a senha de um usuário
que já existe. Senha nunca é hardcoded — sai do .env.

    python scripts/seed_admin.py
"""
from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from app.api.services.auth import senha_service
from app.config import settings
from app.db.models.auth.usuario import Usuario
from app.db.session import dispose_engine, get_session


async def main() -> int:
    try:
        return await _seed()
    finally:
        # Mesmo event loop do engine — dispor fora dele derruba conexões asyncpg
        # com warning.
        await dispose_engine()


async def _seed() -> int:
    email = (settings.admin_email or "").strip().lower()
    senha = settings.admin_senha_inicial

    if not email or not senha:
        print("Defina ADMIN_EMAIL e ADMIN_SENHA_INICIAL no .env.")
        return 1
    try:
        senha_service.validar_forca(senha)
    except senha_service.SenhaFraca as e:
        print(f"Senha recusada: {e}")
        return 1

    async with get_session() as session:
        existente = await session.scalar(select(Usuario).where(Usuario.email == email))
        if existente:
            print(f"Usuário {email} já existe — nada a fazer.")
            return 0
        session.add(
            Usuario(
                email=email,
                nome=email.split("@")[0],
                senha_hash=senha_service.hash_senha(senha),
            )
        )
        await session.commit()

    print(f"Usuário {email} criado.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
