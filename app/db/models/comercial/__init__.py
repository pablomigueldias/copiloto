"""Os modelos do motor comercial: a base de prospecção (D9) e o CRM (Fase 1)."""
from app.db.models.comercial.crm import Interacao, Lead, Tarefa, Transicao
from app.db.models.comercial.prospeccao import (
    Atividade,
    Canal,
    Estabelecimento,
    Fonte,
    Identificador,
    Importacao,
    Origem,
    Supressao,
)

__all__ = [
    "Atividade",
    "Canal",
    "Estabelecimento",
    "Fonte",
    "Identificador",
    "Importacao",
    "Interacao",
    "Lead",
    "Origem",
    "Supressao",
    "Tarefa",
    "Transicao",
]
