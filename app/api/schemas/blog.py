"""Schemas da redação — /api/blog/*."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.blog import taxonomia


class OrigemItem(BaseModel):
    vault: str | None = None
    copiloto: str | None = None


class PostLinha(BaseModel):
    """O que a lista mostra. Sem `corpo`: a lista de 40 posts não precisa
    carregar 40 textos inteiros para desenhar 40 cards."""

    id: str
    slug: str | None = None
    titulo: str
    descricao: str | None = None
    estado: str
    pilar: str | None = None
    tags: list[str] = []
    palavras: int = 0
    camadas_ok: bool = False
    data_publicacao: date | None = None
    exportado_em: datetime | None = None
    # O PR do post, quando já foi aberto. A lista usa para dizer "esperando o
    # CI" sem gastar uma chamada ao GitHub por card.
    pr_numero: int | None = None
    pr_url: str | None = None
    publicado_em: datetime | None = None
    linkedin_em: date | None = None
    linkedin_postado_em: datetime | None = None
    # Post no ar editado aqui e ainda não republicado.
    alteracoes_nao_publicadas: bool = False
    atualizado: date | None = None
    # Há PR aberto (primeira publicação ou atualização) esperando o merge.
    pr_aberto: bool = False
    updated_at: datetime


class Sinal(BaseModel):
    ok: bool
    texto: str
    dica: str | None = None


class CamadaResponse(BaseModel):
    id: str
    rotulo: str
    publico: str
    pergunta: str
    ok: bool
    sinais: list[Sinal]


class Diagnostico(BaseModel):
    camadas: list[CamadaResponse]
    camadas_ok: bool
    falta: list[str]
    frontmatter_erros: list[str]
    exportavel: bool
    palavras: int
    minutos: int
    # Os `{{FALTA: …}}` abertos. Bloqueiam o `pronto`.
    faltas: list[str] = []
    alteracoes_nao_publicadas: bool = False


class PostDetalhe(PostLinha):
    corpo: str = ""
    notas: str | None = None
    origem: list[dict] = []
    linkedin_texto: str | None = None
    diagnostico: Diagnostico
    created_at: datetime


class PaginaPosts(BaseModel):
    total: int
    por_estado: dict[str, int]
    itens: list[PostLinha]


class NovoPost(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    pilar: str | None = None
    corpo: str = ""
    notas: str | None = None
    origem: list[dict] = []


class EdicaoPost(BaseModel):
    """PATCH: só o que veio é gravado.

    `exclude_unset` no router é o que separa "não mandei a descrição" de
    "apaguei a descrição" — sem isso, salvar o corpo zeraria todo o resto.
    """

    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=120)
    descricao: str | None = None
    pilar: str | None = None
    tags: list[str] | None = None
    corpo: str | None = Field(default=None, max_length=200_000)
    notas: str | None = Field(default=None, max_length=50_000)
    origem: list[dict] | None = None
    data_publicacao: date | None = None
    linkedin_texto: str | None = Field(default=None, max_length=5_000)
    linkedin_em: date | None = None


class EstadoRequest(BaseModel):
    estado: Literal["pauta", "rascunho", "pronto", "publicado", "arquivado"]


class VersaoResponse(BaseModel):
    numero: int
    titulo: str
    palavras: int
    criada_em: datetime


class PreviaResponse(BaseModel):
    mdx: str


class ExportacaoResponse(BaseModel):
    caminho: str
    bytes: int


class PreviaSiteResponse(BaseModel):
    """A prévia renderizada: o post no `next dev` do blog, com o visual real."""

    url: str
    caminho: str
    servidor_de_pe: bool
    # Preenchido quando o `next dev` do blog não está no ar: o arquivo foi
    # escrito e a URL existe, mas não há quem a sirva ainda.
    aviso: str | None = None


class CheckResponse(BaseModel):
    nome: str
    # SUCCESS | FAILURE | PENDENTE | … — o que o GitHub devolveu, em maiúsculas.
    resultado: str
    url: str | None = None


class PrResponse(BaseModel):
    """A situação do PR do post. `existe: false` é o caso do post ainda não
    publicado — e é diferente de "existe e está pendente"."""

    existe: bool
    estado: str | None = None
    url: str | None = None
    checks: list[CheckResponse] = []
    checks_verdes: bool = False
    merge_status: str | None = None
    mergeavel: bool = False


class PrAbertoResponse(BaseModel):
    pr_numero: int
    pr_url: str
    branch: str


class PublicadoResponse(BaseModel):
    pr_numero: int
    url: str


class Vocabulario(BaseModel):
    """A taxonomia do blog, para o painel montar os seletores sem repetir a lista."""

    pilares: list[str] = list(taxonomia.PILARES)
    tags: list[str] = list(taxonomia.TAGS)
    tags_max: int = taxonomia.TAGS_MAX
    titulo: tuple[int, int] = (taxonomia.TITULO_MIN, taxonomia.TITULO_MAX)
    descricao: tuple[int, int] = (taxonomia.DESCRICAO_MIN, taxonomia.DESCRICAO_MAX)


# ── Etapa 12: vault, geração, distribuição e o painel ──────────────


class CandidataVault(BaseModel):
    """Uma nota do vault marcada `blog: ideia`, numa pasta liberada."""

    caminho: str
    titulo: str
    pilar: str | None = None
    tags: list[str] = []
    palavras: int
    trecho: str
    post_id: str | None = None


class ImportarNota(BaseModel):
    caminho: str = Field(min_length=1, max_length=500)


class SituacaoGeracao(BaseModel):
    disponivel: bool
    motivo: str | None = None
    gasto_usd: float
    teto_usd: float
    modelo: str


class RascunhoGerado(BaseModel):
    rodadas: int
    pendentes: list[str]
    faltas: list[str]
    palavras: int
    gasto_usd: float


class LinkedinGerado(BaseModel):
    texto: str
    pendentes: list[str]
    gasto_usd: float


class TrechoFonte(BaseModel):
    rotulo: str
    texto: str


class Parecido(BaseModel):
    """Um post já publicado que fala de algo perto desta pauta."""

    titulo: str
    url: str
    trecho: str


class Passo(BaseModel):
    tipo: str
    titulo: str
    detalhe: str
    post_id: str | None = None
    acao: str | None = None


class PostCalendario(BaseModel):
    id: str
    titulo: str
    estado: str
    data: date | None = None


class SemanaCalendario(BaseModel):
    terca: date
    posts: list[PostCalendario]


class PilarResumo(BaseModel):
    pilar: str
    publicados: int
    na_fila: int
    dias_sem_post: int | None = None


class Parado(BaseModel):
    id: str
    titulo: str
    dias: int | None = None


class PainelBlog(BaseModel):
    hoje: date
    funil: dict[str, int]
    m4: dict[str, int]
    cadencia: dict
    pilares: list[PilarResumo]
    calendario: list[SemanaCalendario]
    parados: list[Parado]
    divulgacao_ativa: bool
    gerar: SituacaoGeracao
    candidatas_vault: int
    proximos: list[Passo]
