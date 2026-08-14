"""O índice do que o sistema sabe sobre o mundo do Pablo.

Uma linha por pedaço de texto: um trecho de nota, uma seção de README, um bloco
do Perfil Mestre, uma página de PDF. É a camada 1 (fatos) e a camada 3
(vocabulário do domínio) da §4 do plano — as duas que dão mais resultado por
menos esforço, e sem as quais nenhum treino conserta o que o modelo não sabe.
"""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

# Dimensão do bge-m3. Trocar de embedder é migration, não configuração: o
# índice HNSW é construído para um tamanho fixo.
DIM_EMBEDDING = 1024


class ConhecimentoChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "conhecimento_chunk"

    # 'nota' | 'repo' | 'pdf' | 'perfil' | 'vaga'
    fonte_tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    # Caminho do arquivo, ou `vaga:<uuid>` para o que vem do próprio banco.
    fonte_ref: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 do documento INTEIRO. Se bate, o arquivo nem é lido de novo.
    fonte_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Posição dentro da fonte. É o que permite reindexar um arquivo sozinho e
    # devolver o trecho vizinho como contexto.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)

    # Trilha de headings: "README > Instalação > Docker".
    titulo: Mapped[str | None] = mapped_column(Text)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(DIM_EMBEDDING))

    # Coluna gerada: a metade lexical da busca. Embedding erra nome próprio,
    # sigla e nome de biblioteca ("pgvector", "arq", "RRF") — justamente o que
    # o full-text acerta.
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('portuguese', coalesce(titulo,'') || ' ' || conteudo)",
            persisted=True,
        ),
    )

    # tags, wikilinks, frontmatter, página do PDF.
    metadados: Mapped[dict | None] = mapped_column(JSONB)

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_conhecimento_chunk_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_conhecimento_chunk_tsv", "tsv", postgresql_using="gin"),
        Index(
            "uq_conhecimento_chunk_fonte_ordem",
            "fonte_tipo",
            "fonte_ref",
            "ordem",
            unique=True,
        ),
        Index("ix_conhecimento_chunk_fonte_hash", "fonte_hash"),
        Index("ix_conhecimento_chunk_fonte_tipo", "fonte_tipo"),
    )

    def __repr__(self) -> str:
        return f"<Chunk {self.fonte_tipo}:{self.fonte_ref}#{self.ordem}>"
