"""Funil do bot comercial (`docs/bot-comercial/06`): o LLM extrai os campos,
o código decide estágio e temperatura, para a mesma conversa dar sempre o mesmo
resultado. O limite de 30 mensagens é chute inicial e vai para `comercial_config`.
"""
from __future__ import annotations

from enum import StrEnum

MENSAGENS_DIA_QUENTE = 30
URGENCIAS_QUENTES = frozenset({"agora", "1-3m"})


class Etapa(StrEnum):
    RECEPCAO = "recepcao"
    QUALIFICACAO = "qualificacao"
    APRESENTACAO = "apresentacao"
    OBJECOES = "objecoes"
    AGENDAMENTO = "agendamento"
    PASSAGEM = "passagem"
    FOLLOWUP = "followup"
    OPTOUT = "optout"
    ENCERRADO = "encerrado"
    PAUSADO = "pausado"


class Temperatura(StrEnum):
    QUENTE = "quente"
    MORNO = "morno"
    FRIO = "frio"


def qualificacao_completa(dados: dict) -> bool:
    """Saída da qualificação (06 §2)."""
    return all(dados.get(campo) not in (None, "") for campo in ("nicho", "mensagens_dia", "dor"))


def temperatura(dados: dict, quer_agendar: bool = False) -> Temperatura:
    """06 §2: quente = decide, 30+ mensagens e urgência até 3 meses — ou pediu reunião."""
    if quer_agendar:
        return Temperatura.QUENTE
    mensagens = dados.get("mensagens_dia")
    if (
        dados.get("decisor") == "eu"
        and isinstance(mensagens, int)
        and mensagens >= MENSAGENS_DIA_QUENTE
        and dados.get("urgencia") in URGENCIAS_QUENTES
    ):
        return Temperatura.QUENTE
    if qualificacao_completa(dados):
        return Temperatura.MORNO
    return Temperatura.FRIO
