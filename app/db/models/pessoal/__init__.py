from app.db.models.pessoal.candidatura_email import CandidaturaEmail
from app.db.models.pessoal.candidatura_evento import EVENTOS, CandidaturaEvento
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.models.pessoal.vaga import STATUS_VAGA, Vaga

__all__ = [
    "EVENTOS",
    "STATUS_VAGA",
    "CandidaturaEmail",
    "CandidaturaEvento",
    "PerfilMestre",
    "Vaga",
]
