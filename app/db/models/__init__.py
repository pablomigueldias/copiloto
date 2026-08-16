"""Registro dos modelos.

Importar este módulo popula ``Base.metadata`` — é o que o Alembic (e o teste
``test_db_schema``) usa para saber quais tabelas devem existir. Todo modelo
novo precisa aparecer aqui, senão some do autogenerate.
"""
from app.db.models.acao_pendente import AcaoPendente
from app.db.models.agente_evento import AgenteEvento
from app.db.models.ai_call import AiCall
from app.db.models.auth import Sessao, TentativaLogin, Usuario
from app.db.models.conhecimento import ConhecimentoChunk
from app.db.models.exemplo_estilo import ExemploEstilo
from app.db.models.pessoal import (
    CandidaturaEmail,
    CandidaturaEvento,
    PerfilMestre,
    Vaga,
)
from app.db.models.pipeline_event import PipelineEvent

__all__ = [
    "AcaoPendente",
    "AgenteEvento",
    "AiCall",
    "CandidaturaEmail",
    "CandidaturaEvento",
    "ConhecimentoChunk",
    "ExemploEstilo",
    "PerfilMestre",
    "PipelineEvent",
    "Sessao",
    "TentativaLogin",
    "Usuario",
    "Vaga",
]
