"""As regras do blog, copiadas de propósito — e vigiadas por teste.

A fonte da verdade é `pabloortiz.dev/src/content/schema.ts`: é ele que o CI do
blog roda, e é ele que decide se um post entra. Este arquivo é uma cópia em
Python das mesmas listas e limites, para que o CMS possa recusar antes de
exportar, em vez de descobrir no PR.

Cópia é dívida, e a dívida aqui é paga por `tests/test_blog_taxonomia.py`: se o
repo do blog estiver na máquina, o teste lê o `schema.ts` e compara. Se não
estiver, o teste pula — dois repos independentes não podem virar um só por
causa de duas listas, e importar TypeScript de dentro do Python para evitar
copiar 20 strings seria a troca errada.
"""
from __future__ import annotations

import re

# "hardware" ainda não existe no blog: abre com o primeiro projeto documentado.
PILARES = ("ia-llms", "dados-ml")

# Tag nova entra aqui **e** no schema.ts antes de ser usada num post.
TAGS = (
    "rag",
    "llm",
    "llm-local",
    "agentes",
    "avaliacao",
    "observabilidade",
    "pgvector",
    "postgresql",
    "sql",
    "python",
    "fastapi",
    "machine-learning",
    "redes-neurais",
    "analise-de-dados",
    "pipeline-de-dados",
    "whisper",
    "fundamentos",
    "carreira",
)

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TITULO_MIN, TITULO_MAX = 10, 70
DESCRICAO_MIN, DESCRICAO_MAX = 50, 160
TAGS_MAX = 5

# Caminho absoluto em `origem` expõe a estrutura da minha máquina — o schema do
# blog recusa, e aqui também.
_ABSOLUTO_RE = re.compile(r"^(?:/|[A-Za-z]:\\|~)")


def caminho_relativo(caminho: str) -> bool:
    return bool(caminho) and not _ABSOLUTO_RE.match(caminho)


def validar_frontmatter(
    *,
    slug: str | None,
    titulo: str,
    descricao: str | None,
    pilar: str | None,
    tags: list[str],
    data: object | None,
    origem: list[dict] | None = None,
) -> list[str]:
    """Os problemas que o CI do blog apontaria, em português e de uma vez.

    Lista vazia quer dizer "exportável". Devolver **todos** os erros, e não o
    primeiro, é o ponto: corrigir um por vez, com um round-trip de painel a
    cada um, é o que faz ninguém usar a ferramenta.
    """
    erros: list[str] = []

    if not slug:
        erros.append("falta o slug (é o nome do arquivo e a URL do post)")
    elif not SLUG_RE.match(slug):
        erros.append(f"slug inválido: {slug!r} — use minúsculas, números e hífen")

    n = len(titulo.strip())
    if not TITULO_MIN <= n <= TITULO_MAX:
        erros.append(f"título com {n} caracteres — o blog exige de {TITULO_MIN} a {TITULO_MAX}")

    d = len((descricao or "").strip())
    if not DESCRICAO_MIN <= d <= DESCRICAO_MAX:
        erros.append(
            f"descrição com {d} caracteres — o blog exige de {DESCRICAO_MIN} a {DESCRICAO_MAX}"
        )

    if pilar not in PILARES:
        erros.append(f"pilar inválido: {pilar!r} — use um de {list(PILARES)}")

    if len(tags) > TAGS_MAX:
        erros.append(f"{len(tags)} tags — o máximo é {TAGS_MAX}")
    for t in tags:
        if t not in TAGS:
            erros.append(f"tag fora da lista curada: {t!r}")

    if data is None:
        erros.append("falta a data de publicação")

    for item in origem or []:
        for chave, caminho in item.items():
            if chave not in ("vault", "copiloto"):
                erros.append(f"origem com chave desconhecida: {chave!r}")
            elif not caminho_relativo(str(caminho)):
                erros.append(f"origem com caminho absoluto: {caminho!r}")

    return erros
