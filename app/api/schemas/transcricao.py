"""Schemas da transcrição — /api/transcricao/*."""
from __future__ import annotations

from pydantic import BaseModel, Field


class IniciarRequest(BaseModel):
    # 'sistema' grava o que está tocando (vídeo, reunião); 'mic', a minha voz.
    fonte: str = Field(default="sistema", pattern="^(sistema|mic)$")


class TrechoVivo(BaseModel):
    """Um pedaço de 20 s, como a tela mostra: com o relógio e o ✕."""

    indice: int
    segundo: int
    relogio: str
    texto: str
    # Pré-marcado, nunca removido sozinho: "assine o curso completo" aparece em
    # aula sobre marketing, e apagar por conta própria perderia conteúdo real.
    anuncio: bool = False


class Sugestao(BaseModel):
    """O que o modelo local propôs — tudo editável na tela antes de salvar."""

    titulo: str
    resumo: str = ""
    destaques: list[str] = []
    pasta: str = ""
    tags: list[str] = []
    conceitos: list[str] = []
    # O que o glossário corrigiu: é assim que eu descubro o que acrescentar nele.
    corrigidos: list[str] = []
    nome_arquivo: str = ""
    palavras: int = 0
    # As notas que já falam do mesmo assunto — a evidência de que a pasta
    # sugerida faz sentido, e os wikilinks que a nota nova vai carregar.
    relacionadas: list[str] = []


class EstadoTranscricao(BaseModel):
    estado: str                      # ocioso | gravando | processando | revisar
    fonte: str = "sistema"
    segundos: int = 0
    palavras: int = 0
    trechos: list[TrechoVivo] = []
    erro: str | None = None
    sugestao: Sugestao | None = None


class SalvarRequest(BaseModel):
    titulo: str = Field(min_length=2, max_length=120)
    pasta: str = Field(default="", max_length=200)
    tags: list[str] = []
    nome_arquivo: str | None = None


class NotaSalva(BaseModel):
    caminho: str
    chunks: int = 0
