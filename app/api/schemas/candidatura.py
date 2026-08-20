"""Schemas da candidatura — /api/vagas/*."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VagaRequest(BaseModel):
    descricao: str = Field(min_length=50, max_length=40_000)
    titulo: str | None = None
    empresa: str | None = None
    link: str | None = None
    fonte: str | None = None


class VagaPatch(BaseModel):
    """O que dá para corrigir na tela. Tudo opcional: PATCH, não PUT.

    `None` num campo enviado significa "limpa" — por isso o router distingue
    "não veio" de "veio vazio" com `exclude_unset`.
    """

    titulo: str | None = None
    empresa: str | None = None
    link: str | None = None
    fonte: str | None = None
    localizacao: str | None = None
    modelo: str | None = None
    senioridade: str | None = None
    contato_nome: str | None = None
    contato_email: str | None = None
    descricao: str | None = Field(default=None, max_length=40_000)
    notas: str | None = None
    status: str | None = None


class CurriculoTexto(BaseModel):
    """O currículo em texto puro — o formato do editor da gaveta e da fila.

    Texto e não JSON de propósito: é o que o `de_texto` sabe ler, é o que o ATS
    enxerga, e é o mesmo formato que a fila já usa. Um editor de JSON pediria
    que eu acertasse chave e vírgula para corrigir uma frase.
    """

    texto: str = Field(min_length=1, max_length=60_000)


class CurriculoTextoResponse(BaseModel):
    vaga_id: str
    texto: str
    # `None` quando a edição não mudou nada — a tela não avisa "salvo" à toa.
    pdf: str | None = None


class EventoRequest(BaseModel):
    evento: str
    detalhe: str | None = None


class VagaResponse(BaseModel):
    id: str
    titulo: str
    empresa: str | None = None
    status: str
    link: str | None = None
    localizacao: str | None = None
    modelo: str | None = None
    senioridade: str | None = None
    contato_nome: str | None = None
    contato_email: str | None = None
    # Curta e escrita por mim: cabe na listagem sem pesar, e a gaveta precisa
    # dela de volta depois de salvar para não reenviar o mesmo texto.
    notas: str | None = None
    match_score: int | None = None
    analise_json: dict | None = None
    match_json: dict | None = None
    curriculo_json: dict | None = None
    curriculo_gerado_em: datetime | None = None
    created_at: datetime


class VagaLinha(BaseModel):
    """A vaga como a **tabela** precisa dela — e nada além disso.

    `VagaResponse` carrega `analise_json`, `match_json` e `curriculo_json`, que
    somam 6,5 KB por vaga e não aparecem em lugar nenhum da listagem: 87% do
    tráfego era desperdício, e com 100 vagas isso vira 637 KB jogados fora a
    cada refresco (medido — ver docs/fase06.md §2.3).

    Quem precisa dos blocos é a gaveta, e ela chama `/api/vagas/{id}`.
    """

    id: str
    titulo: str
    empresa: str | None = None
    status: str
    match_score: int | None = None
    modelo: str | None = None
    localizacao: str | None = None
    senioridade: str | None = None
    # `bool` em vez dos 4 KB de `curriculo_json`: a tabela só mostra um ✓.
    tem_curriculo: bool = False
    curriculo_gerado_em: datetime | None = None
    created_at: datetime


class PaginaVagas(BaseModel):
    total: int
    itens: list[VagaLinha]


class EventoResponse(BaseModel):
    evento: str
    detalhe: str | None = None
    ocorreu_em: datetime


class VagaDetalheResponse(VagaResponse):
    descricao: str
    historico: list[EventoResponse] = []


class GeracaoResponse(BaseModel):
    vaga_id: str
    curriculo: dict
    pdf: str | None = None
    acao_id: str | None = None
    # O botão "analisar + gerar" devolve a vaga junto: a tela precisa do score
    # novo na mesma resposta, senão pisca o valor velho antes de recarregar.
    vaga: VagaResponse | None = None
    # O que a anti-alucinação derrubou e o que o ATS vai reclamar: a resposta
    # carrega os dois porque são o que decide se dá para enviar como está.
    rejeitados: list[str] = []
    avisos: list[str] = []


class MetricasResponse(BaseModel):
    funil: dict[str, int]
    por_status: dict[str, int]
    taxa_resposta: float | None = None
    dias_ate_resposta: float | None = None
    followup_vencido: int
    paradas: list[dict] = []
    gaps_frequentes: list[dict] = []
    score_medio: float | None = None
