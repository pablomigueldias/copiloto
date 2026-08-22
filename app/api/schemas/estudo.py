"""Schemas do estudo — /api/estudo/*."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models.estudo.questao import FORMATOS, TRILHAS

Formato = Literal[FORMATOS]  # type: ignore[valid-type]
Trilha = Literal[TRILHAS]  # type: ignore[valid-type]


class Alternativa(BaseModel):
    letra: str = Field(pattern="^[A-E]$")
    texto: str


class AgendaResponse(BaseModel):
    proxima_em: date
    ultima_em: datetime | None = None
    intervalo_dias: int
    acertos_seguidos: int
    total_acertos: int
    total_erros: int
    estado: str


class QuestaoResponse(BaseModel):
    id: str
    formato: str
    modulo: str
    topico: str
    topico_id: str
    comando: str | None = None
    enunciado: str
    texto_base: str | None = None
    texto_base_fonte: str | None = None
    codigo: str | None = None
    linguagem: str | None = None
    alternativas: list[Alternativa] = []
    afirmacoes: list[str] = []
    explicacao: str | None = None
    origem: str | None = None
    fonte: str | None = None
    dificuldade: int
    agenda: AgendaResponse | None = None
    # Ausente na revisão, presente na listagem: mandar o gabarito junto com a
    # questão que estou respondendo é entregar a resposta ao DevTools.
    gabarito: str | None = None


class PaginaQuestoes(BaseModel):
    total: int
    itens: list[QuestaoResponse]


class FilaResponse(BaseModel):
    total: int
    itens: list[QuestaoResponse]


class ResumoResponse(BaseModel):
    hoje: int
    de_erro: int
    novas: int
    adiadas: int
    dominadas: int
    total: int
    respondidas_hoje: int


class TopicoResumo(BaseModel):
    id: str
    nome: str
    questoes: int
    hoje: int
    dominadas: int
    com_erro: int
    proxima_em: date | None = None


class ModuloResumo(BaseModel):
    id: str
    nome: str
    trilha: str
    questoes: int
    hoje: int
    dominadas: int
    com_erro: int
    proxima_em: date | None = None
    topicos: list[TopicoResumo]


class RespostaRequest(BaseModel):
    resposta: str = Field(description="'A'..'E', ou 'C'/'E' no julgue o item")
    # A tela deixa tentar de novo antes de revelar. Só a primeira reagenda —
    # ver `app/estudo/servico.responder`.
    tentativa_n: int = Field(default=1, ge=1, le=5)
    segundos: int | None = Field(default=None, ge=0)


class RespostaResponse(BaseModel):
    acertou: bool
    gabarito: str
    explicacao: str | None = None
    reagendou: bool
    proxima_em: date
    intervalo_dias: int
    estado: str


class AdiarRequest(BaseModel):
    dias: int | None = Field(default=None, ge=1, le=365)


class AgendaSimples(BaseModel):
    proxima_em: date
    intervalo_dias: int
    estado: str


class TentativaResponse(BaseModel):
    id: str
    respondida_em: datetime
    acertou: bool
    resposta: str | None = None
    tentativa_n: int
    segundos: int | None = None


class QuestaoRequest(BaseModel):
    topico_id: str
    formato: Formato
    enunciado: str
    gabarito: str = Field(pattern="^[A-E]$")
    comando: str | None = None
    texto_base: str | None = None
    texto_base_fonte: str | None = None
    codigo: str | None = None
    linguagem: str | None = None
    alternativas: list[Alternativa] = []
    afirmacoes: list[str] = []
    explicacao: str | None = None
    origem: str | None = None
    fonte: str | None = None
    dificuldade: int = Field(default=2, ge=1, le=3)


class QuestaoPatch(BaseModel):
    """Só o que eu corrijo depois. Gabarito e explicação são o caso comum."""

    enunciado: str | None = None
    comando: str | None = None
    gabarito: str | None = Field(default=None, pattern="^[A-E]$")
    explicacao: str | None = None
    dificuldade: int | None = Field(default=None, ge=1, le=3)
    fonte: str | None = None


class ModuloRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    trilha: Trilha = "concurso"
    ordem: int = Field(default=0, ge=0, le=999)


class ModuloPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    trilha: Trilha | None = None
    ordem: int | None = Field(default=None, ge=0, le=999)


class TopicoRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    ordem: int = Field(default=0, ge=0, le=999)


class TopicoPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=160)
    ordem: int | None = Field(default=None, ge=0, le=999)


class ModuloCriado(BaseModel):
    id: str
    nome: str
    trilha: str
    ordem: int


class TopicoCriado(BaseModel):
    id: str
    modulo_id: str
    nome: str
    ordem: int


class Apagado(BaseModel):
    """Quantas questões foram junto. Zero é o caso normal."""

    questoes_apagadas: int
