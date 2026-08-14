"""Schemas (Pydantic) do módulo auth."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(..., description="Email do usuário")
    senha: str = Field(..., description="Senha em texto (vai por HTTPS)")


class TrocaSenhaRequest(BaseModel):
    senha_atual: str = Field(..., description="Senha atual (confirmação)")
    senha_nova: str = Field(..., description="Nova senha (validada por força)")


class UsuarioResponse(BaseModel):
    id: str
    email: str
    nome: str
    ativo: bool
    ultimo_login: str | None = None


class MensagemResponse(BaseModel):
    ok: bool = True
    mensagem: str = ""
