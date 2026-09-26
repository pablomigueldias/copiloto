"""Os modelos do motor comercial — por ora, a base de prospecção (D9)."""
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
    "Origem",
    "Supressao",
]
