"""Senhas — hashing Argon2id + validação de força.

Regras (ver plano, seção 2):
- Hash **Argon2id** (lib testada `argon2-cffi`); nunca inventar cripto própria.
- **Anti-timing**: se o email não existe, ainda rodamos um verify contra um hash
  "dummy" pra o tempo de resposta não denunciar quais emails existem.
- **Força**: mínimo 12 caracteres + recusa as senhas mais óbvias.
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Parâmetros sólidos (plano: time_cost=3, memory=64MB, parallelism=4).
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # KiB → 64 MB
    parallelism=4,
)

# Hash de uma senha qualquer, calculado uma vez no import. Serve só pra gastar
# o mesmo tempo de CPU de um verify real quando o usuário não existe.
_DUMMY_HASH = _ph.hash("anti-timing-dummy-password")

TAMANHO_MINIMO = 12

# Lista curta das senhas mais batidas. Não é o zxcvbn completo, mas corta o
# pior caso sem dependência nova. Comparação case-insensitive.
_SENHAS_COMUNS = {
    "password", "senha", "123456", "12345678", "123456789", "1234567890",
    "qwerty", "abc123", "111111", "000000", "iloveyou", "admin", "letmein",
    "welcome", "monkey", "dragon", "senha123", "password123", "mudar123",
}


class SenhaFraca(Exception):
    """Senha não passou na validação de força — vira HTTP 400 no router."""


def validar_forca(senha: str) -> None:
    """Levanta SenhaFraca se a senha for fraca demais pra ser aceita."""
    if len(senha) < TAMANHO_MINIMO:
        raise SenhaFraca(
            f"A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres."
        )
    if senha.lower() in _SENHAS_COMUNS:
        raise SenhaFraca("Essa senha é fácil demais. Escolha outra.")
    if senha.isdigit():
        raise SenhaFraca("A senha não pode ser só números.")
    if len(set(senha)) < 4:
        raise SenhaFraca("A senha tem repetição demais. Varie os caracteres.")


def hash_senha(senha: str) -> str:
    """Gera o hash Argon2id pra guardar no banco. NÃO valida força aqui."""
    return _ph.hash(senha)


def conferir_senha(hash_armazenado: str | None, senha: str) -> bool:
    """Confere a senha contra o hash. Anti-timing embutido: se o hash for None
    (usuário inexistente), gasta o mesmo tempo verificando contra o dummy e
    retorna False — sem vazar pelo tempo se o email existe."""
    if hash_armazenado is None:
        try:
            _ph.verify(_DUMMY_HASH, senha)
        except VerifyMismatchError:
            pass
        return False
    try:
        _ph.verify(hash_armazenado, senha)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def precisa_rehash(hash_armazenado: str) -> bool:
    """True se o hash foi gerado com parâmetros antigos (rehash no próximo login)."""
    return _ph.check_needs_rehash(hash_armazenado)
