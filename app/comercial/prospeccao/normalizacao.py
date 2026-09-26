"""Normalização dos valores que chegam das fontes.

O mesmo telefone vem "(11) 3333-4444" do CNES e "11" + "33334444" da Receita. Sem
normalizar, vira duas linhas e a supressão de uma não pega a outra. Tudo aqui é
função pura: a fonte entra suja, sai o valor canônico e se ele é válido.

Valor inválido **não é descartado**: entra com `valido=False` e o original ao
lado, para dar para auditar a fonte depois.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.db.models.comercial.prospeccao import TipoCanal

UF_POR_CODIGO = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
    "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
_HOST = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


@dataclass(frozen=True, slots=True)
class Normalizado:
    tipo: TipoCanal
    valor: str
    original: str
    valido: bool


def so_digitos(valor: str | int | None) -> str:
    return re.sub(r"\D", "", str(valor)) if valor is not None else ""


def telefone(bruto: str, ddd: str | None = None) -> Normalizado | None:
    """E.164 (`+5511…`). Celular = 11 dígitos começando em 9; fixo começa em 2–5."""
    if not bruto or not bruto.strip():
        return None
    d = so_digitos(bruto)
    if len(d) in (12, 13) and d.startswith("55"):
        d = d[2:]
    d = d.lstrip("0")
    if len(d) in (8, 9) and ddd:
        d = so_digitos(ddd).lstrip("0") + d
    ddd_ok = len(d) >= 2 and d[0] != "0" and d[1] != "0"
    celular = len(d) == 11 and d[2] == "9"
    fixo = len(d) == 10 and d[2] in "2345"
    valido = ddd_ok and (celular or fixo)
    tipo = TipoCanal.CELULAR if celular else TipoCanal.TELEFONE
    return Normalizado(tipo, f"+55{d}" if valido else d, bruto, valido)


def email(bruto: str) -> Normalizado | None:
    if not bruto or not bruto.strip():
        return None
    v = bruto.strip().lower().removeprefix("mailto:")
    return Normalizado(TipoCanal.EMAIL, v, bruto, bool(_EMAIL.match(v)))


def site(bruto: str) -> Normalizado | None:
    """`https://host/caminho`, sem barra final. O caminho mantém a caixa."""
    if not bruto or not bruto.strip():
        return None
    v = bruto.strip()
    v = re.sub(r"^https?://", "", v, flags=re.IGNORECASE)
    host, _, caminho = v.partition("/")
    host = host.lower()
    v = f"https://{host}/{caminho}".rstrip("/")
    return Normalizado(TipoCanal.SITE, v, bruto, bool(_HOST.match(host)))


def municipio_ibge(codigo: str | int) -> str | None:
    """Código de 6 dígitos (CNES) → 7 dígitos com o verificador do IBGE."""
    d = so_digitos(codigo)
    if len(d) == 7:
        return d
    if len(d) != 6:
        return None
    soma = 0
    for i, c in enumerate(d):
        p = int(c) * (1 if i % 2 == 0 else 2)
        soma += p // 10 + p % 10
    return d + str((10 - soma % 10) % 10)


def cep(bruto: str | None) -> str | None:
    d = so_digitos(bruto)
    return d if len(d) == 8 else None


def hash_valor(valor: str) -> str:
    """O que a supressão guarda no lugar do dado de quem pediu para sair."""
    return hashlib.sha256(valor.encode()).hexdigest()


def cpf_valido(d: str) -> bool:
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10) % 11 % 10 != int(d[n]):
            return False
    return True


def sem_cpf_no_nome(nome: str) -> str:
    """Tira o CPF que o empresário individual põe no fim do nome (1.2.6 §3)."""
    m = re.search(r"\s*(\d{11})\s*$", nome)
    if m and cpf_valido(m.group(1)):
        return nome[: m.start()].strip()
    return nome.strip()
