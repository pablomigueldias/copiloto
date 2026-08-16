"""Schemas do conhecimento — /api/conhecimento/*."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TrechoResponse(BaseModel):
    """Um resultado de busca.

    `fonte_ref`, `titulo` e `origem` não são detalhe de depuração: a tela da F3
    cita a fonte, e `origem` diz se o trecho veio do vetor, do full-text ou dos
    dois — é como se descobre que metade da busca está carregando a outra.
    """

    id: str
    fonte_tipo: str
    fonte_ref: str
    ordem: int
    titulo: str | None = None
    conteudo: str
    metadados: dict = {}
    score: float
    origem: str
    # Distância de cosseno até a pergunta; `null` quando o trecho veio só do
    # full-text. É a medida de confiança — o `score` não é.
    distancia: float | None = None


class BuscaResponse(BaseModel):
    consulta: str
    total: int
    trechos: list[TrechoResponse]


class PerguntaRequest(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500)
    fonte_tipo: list[str] | None = None
    tag: list[str] | None = None
    limite: int = Field(default=5, ge=1, le=10)


class RespostaResponse(BaseModel):
    """A resposta e tudo que permite conferi-la.

    `respondeu=False` com `motivo` é resultado legítimo, não erro: "não tenho
    isso indexado" é a resposta certa quando o índice não cobre o assunto.
    """

    pergunta: str
    texto: str
    respondeu: bool
    motivo: str | None = None
    # O que a resposta citou — é o que a tela mostra como fonte clicável.
    fontes: list[TrechoResponse] = []
    # Tudo que a busca trouxe, citado ou não: serve para desconfiar da resposta.
    trechos: list[TrechoResponse] = []
    distancia: float | None = None
    modelo: str | None = None
    latencia_ms: int | None = None
    tokens: int | None = None


class FonteResponse(BaseModel):
    fonte_tipo: str
    fonte_ref: str
    titulo: str | None = None
    chunks: int
    # Páginas do PDF ou blocos do perfil; 1 quando a fonte é um arquivo só.
    partes: int
    atualizado_em: datetime


class InventarioResponse(BaseModel):
    total: int
    chunks_por_tipo: dict[str, int]
    itens: list[FonteResponse]


class RemocaoResponse(BaseModel):
    fonte_tipo: str
    fonte_ref: str
    chunks_removidos: int
