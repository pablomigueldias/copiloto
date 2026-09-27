"""Schemas do CRM comercial — /api/comercial/*."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class EmpresaLinha(BaseModel):
    id: int
    nome: str
    segmento: str | None = None
    bairro: str | None = None
    pessoa_fisica: bool
    cnes: str | None = None
    emails: list[str] = []
    telefones: list[str] = []
    lead_id: int | None = None


class PaginaEmpresas(BaseModel):
    total: int
    itens: list[EmpresaLinha]


class TrazerRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=10)
    confirmar_pessoa_fisica: bool = False


class TrazerResposta(BaseModel):
    trazidos: list[int]
    # estabelecimento → motivo de ter ficado de fora
    pulados: dict[int, str]


class LeadLinha(BaseModel):
    id: int
    nome: str
    estagio: str
    email: str | None = None
    email_confirmado: bool
    site: str | None = None
    proxima_acao: str | None = None
    pesquisado_em: datetime | None = None
    criado_em: datetime


class InteracaoResponse(BaseModel):
    id: int
    canal: str
    direcao: str
    tipo: str | None = None
    texto: str | None = None
    dados: dict | None = None
    criado_em: datetime


class TarefaResponse(BaseModel):
    id: int
    tipo: str
    vence_em: date
    feita_em: datetime | None = None


class RascunhoResponse(BaseModel):
    """Um texto do Redator: o que está na fila, o aprovado e o que já saiu."""

    acao_id: UUID
    tipo: str
    status: str
    assunto: str
    corpo: str
    motivo: str | None = None
    avisos: list[str] = []
    # O que o verificador acha do texto que eu editei na fila, antes de copiar.
    problemas: list[str] = []
    criada_em: datetime
    enviado_em: datetime | None = None


class LeadDetalhe(LeadLinha):
    email_fonte: str | None = None
    telefone: str | None = None
    estabelecimento_id: int | None = None
    interacoes: list[InteracaoResponse]
    tarefas: list[TarefaResponse]
    rascunhos: list[RascunhoResponse] = []


class PesquisarRequest(BaseModel):
    site: str | None = Field(default=None, max_length=300)


class PesquisarResposta(BaseModel):
    status: str
    email_confirmado: bool
    mensagem: str
    lead: LeadDetalhe


class EscreverRequest(BaseModel):
    tipo: Literal["email_frio", "lembrete_frio"] = "email_frio"


class EscreverResposta(BaseModel):
    acao_id: UUID
    avisos: list[str]
    lead: LeadDetalhe


class EnvieiRequest(BaseModel):
    acao_id: UUID
