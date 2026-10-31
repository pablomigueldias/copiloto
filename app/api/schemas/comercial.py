"""Schemas do CRM comercial — /api/comercial/*."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
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


# ── o cadastro do CRM: empresa, contato, negócio, atividade ──

TipoRegistro = Literal["empresa", "contato", "negocio", "atividade"]


class Opcao(BaseModel):
    valor: str
    rotulo: str


class CampoRegistro(BaseModel):
    # Nulo quando o campo só se lê aqui (o e-mail do envio, a data de criação).
    campo: str | None = None
    rotulo: str
    tipo: str
    valor: Any = None
    exibicao: str
    opcoes: list[Opcao] = []


class LinkRegistro(BaseModel):
    tipo: TipoRegistro
    id: int
    nome: str
    sub: str | None = None


class GrupoRegistro(BaseModel):
    titulo: str
    tipo: TipoRegistro
    itens: list[LinkRegistro]


class EventoLinha(BaseModel):
    quando: datetime
    tipo: Literal["interacao", "transicao"]
    canal: str | None = None
    direcao: str | None = None
    rotulo: str | None = None
    texto: str | None = None
    lead_id: int
    negocio_nome: str | None = None


class Registro(BaseModel):
    tipo: TipoRegistro
    id: int
    titulo: str
    campos: list[CampoRegistro]
    grupos: list[GrupoRegistro]
    notas: str | None = None
    linha_do_tempo: list[EventoLinha] = []
    valores: dict[str, Any] = {}


class EmpresaCrm(BaseModel):
    id: int
    nome: str
    status: str
    segmento: str | None = None
    site: str | None = None
    email: str | None = None
    telefone: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    uf: str | None = None
    estabelecimento_id: int | None = None
    n_contatos: int
    n_negocios: int


class ContatoCrm(BaseModel):
    id: int
    nome: str
    cargo: str | None = None
    decisor: bool
    email: str | None = None
    telefone: str | None = None
    linkedin: str | None = None
    empresa_id: int | None = None
    empresa_nome: str | None = None


class NegocioCrm(BaseModel):
    id: int
    nome: str
    estagio: str
    origem: str
    valor_estimado: float | None = None
    empresa_id: int | None = None
    empresa_nome: str | None = None
    contato_id: int | None = None
    contato_nome: str | None = None
    email: str | None = None
    email_confirmado: bool
    proxima_acao: str | None = None
    proxima_em: date | None = None
    motivo_perda: str | None = None
    tarefas_abertas: int
    pode_ir: list[str]
    criado_em: datetime
    atualizado_em: datetime


class AtividadeCrm(BaseModel):
    id: int
    tipo: str
    descricao: str | None = None
    vence_em: date
    feita_em: datetime | None = None
    atrasada: bool
    lead_id: int
    negocio_nome: str
    negocio_estagio: str
    empresa_id: int | None = None
    empresa_nome: str | None = None


class PaginaEmpresasCrm(BaseModel):
    total: int
    itens: list[EmpresaCrm]


class PaginaContatosCrm(BaseModel):
    total: int
    itens: list[ContatoCrm]


class EstagioPainel(BaseModel):
    estagio: str
    rotulo: str
    total: int
    valor: float


class MotivoPerda(BaseModel):
    motivo: str
    total: int


class PainelCrm(BaseModel):
    negocios_abertos: int
    valor_aberto: float
    ganhos: int
    valor_ganho: float
    perdidos: int
    por_estagio: list[EstagioPainel]
    tarefas_abertas: int
    tarefas_atrasadas: int
    tarefas_hoje: int
    empresas: int
    clientes: int
    contatos: int
    motivos_perda: list[MotivoPerda]
    proximas: list[AtividadeCrm]


class CamposRequest(BaseModel):
    campos: dict[str, Any] = Field(default_factory=dict)


class Criado(BaseModel):
    id: int


class MoverRequest(BaseModel):
    para: str
    motivo: str | None = Field(default=None, max_length=2000)


class RegistrarRequest(BaseModel):
    texto: str = Field(min_length=1, max_length=10_000)
    canal: str = "nota"
    direcao: str | None = None
