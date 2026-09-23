"""A redação — onde o post mora antes de o git saber que ele existe.

O blog guarda o que está **publicado**; aqui fica o que está sendo **escrito**.
A separação não é organizacional, é prática: rascunho no repo só existe se
virar commit, e commit de texto meio pronto num repo público é ou ruído no
histórico ou texto que ninguém salva. O resultado medido foi um só — o rascunho
do post do RAG parado com um comentário dentro dele listando o que faltava.

Duas tabelas:

    blog_post          o post, da ideia à publicação
    blog_post_versao   o corpo de antes, guardado quando o corpo muda

A `versao` existe porque autosave sem histórico é uma forma educada de perder
parágrafo. Guarda só o que muda de valor (título e corpo), e não uma cópia da
linha inteira: `estado` e `tags` se reconstroem, um parágrafo apagado não.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# A ordem é a do trabalho, e `pronto` é o único com portão (as camadas verdes).
# `arquivado` não é um fim: é o jeito de tirar a ideia da frente sem apagá-la,
# porque pauta descartada em janeiro costuma ser post em julho.
ESTADOS = ("pauta", "rascunho", "pronto", "publicado", "arquivado")


class BlogPost(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blog_post"

    # Nome do arquivo no blog (`content/blog/<slug>.mdx`) e URL do post. Só é
    # obrigatório para exportar: pauta nasce com título e nada mais.
    slug: Mapped[str | None] = mapped_column(String(120), unique=True)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    # O texto do card, da busca e do compartilhamento. O schema do blog exige
    # 50–160 caracteres, e é a camada `resultado` que cobra isso aqui.
    descricao: Mapped[str | None] = mapped_column(Text)

    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pauta", server_default="pauta"
    )
    # 'ia-llms' | 'dados-ml' — a lista vem do blog (`app/blog/taxonomia.py`).
    pilar: Mapped[str | None] = mapped_column(String(40))
    # Lista de strings da lista curada do blog. JSONB e não tabela de ligação:
    # são no máximo cinco por post, sem atributo próprio e sem consulta que
    # mereça um join.
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # O MDX sem frontmatter — o frontmatter é gerado dos campos ao exportar,
    # para não existir em dois lugares e divergir.
    corpo: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # O que eu não publico: referência solta, nome de cliente, raciocínio de
    # bastidor. Nunca entra no MDX — é a razão de este campo existir separado do
    # corpo, em vez de ser comentário `{/* */}` no meio do texto.
    notas: Mapped[str | None] = mapped_column(Text)

    # [{"vault": "Machine Learning/..."}, {"copiloto": "docs/fase03.md"}].
    # Caminho **relativo**: absoluto expõe a estrutura da minha máquina, e o
    # schema do blog recusa (§10 do plano do blog).
    origem: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # A data que vai no frontmatter. Fica em aberto até haver o que datar.
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    # Quando o MDX foi para o repo do blog. É o que separa `pronto` de
    # `publicado` — e o que permite saber se o arquivo lá é mais novo que aqui.
    exportado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── A publicação (app/blog/publicacao.py) ────────────────────────
    #
    # O PR aberto para este post. Guardado aqui, e não consultado no GitHub a
    # cada tela, porque a lista precisa saber "este já foi?" sem gastar uma
    # chamada de API por card — e porque o número do PR é o que liga o post ao
    # histórico do repo depois que a branch morre.
    pr_numero: Mapped[int | None] = mapped_column(Integer)
    pr_url: Mapped[str | None] = mapped_column(Text)
    # `post/<slug>`. Recriada a cada publicação a partir da `origin/main`, então
    # nunca fica atrás — que é o que a `main` protegida exige (`strict`).
    branch: Mapped[str | None] = mapped_column(String(160))
    # Quando o PR entrou na `main`. É o único carimbo que significa "está no ar"
    # (ou a caminho: o deploy da Cloudflare vem logo depois).
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<BlogPost {self.estado} {self.titulo[:40]!r}>"


class BlogPostVersao(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "blog_post_versao"

    # CASCADE: versão é histórico **do post**, não dado meu. Apagar o post leva
    # o histórico junto — o contrário de `exemplo_estilo`, que sobrevive à ação
    # que o gerou porque virou dado de treino.
    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("blog_post.id", ondelete="CASCADE"), nullable=False
    )
    # 1, 2, 3… por post. Número e não timestamp porque é o que eu digo em voz
    # alta ("volta para a versão 3"), e o `unique` impede duas versões 3.
    numero: Mapped[int] = mapped_column(Integer, nullable=False)

    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    corpo: Mapped[str] = mapped_column(Text, nullable=False)
    palavras: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_blog_post_versao_numero", "post_id", "numero", unique=True),
        # A consulta da tela: o histórico de um post, mais novo primeiro.
        Index("ix_blog_post_versao_post", "post_id", "criada_em"),
    )

    def __repr__(self) -> str:
        return f"<BlogPostVersao {self.post_id} v{self.numero}>"
