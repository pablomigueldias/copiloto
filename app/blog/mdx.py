"""De linha do banco a arquivo `.mdx` — e nada além disso.

O frontmatter nasce dos campos, nunca é digitado. Se o `titulo` morasse no
banco **e** no topo do corpo, os dois divergiriam no primeiro dia em que eu
editasse só um, e a lista do painel mostraria um título que o site não usa.

Exportar escreve o arquivo no repo do blog e para. Não há `git add`, `commit`
nem `push` aqui, e a ausência é a mesma decisão da fila de aprovação: o sistema
prepara, eu executo. O que vai para o ar passa por PR e pelo CI de privacidade
do blog — um processo que só protege enquanto nada o pula.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.blog import taxonomia

# O `lang` é fixo: o blog é PT-BR, e o inglês é uma decisão de daqui a uns anos
# (§8 do plano do blog). Sai no frontmatter mesmo assim porque o schema tem o
# campo, e escrevê-lo agora é o que torna a virada um `sed` em vez de um script.
LANG = "pt-BR"


def _escapar(valor: str) -> str:
    """Aspas duplas em YAML, via JSON — que já resolve aspa, barra e acento."""
    return json.dumps(valor, ensure_ascii=False)


def frontmatter(
    *,
    titulo: str,
    descricao: str | None,
    data: date,
    pilar: str,
    tags: list[str],
    origem: list[dict] | None = None,
    rascunho: bool = False,
) -> str:
    linhas = [
        "---",
        f"titulo: {_escapar(titulo)}",
        f"descricao: {_escapar(descricao or '')}",
        f"data: {data.isoformat()}",
        f"pilar: {pilar}",
        f"tags: [{', '.join(tags)}]",
        f"draft: {'true' if rascunho else 'false'}",
        f"lang: {LANG}",
    ]
    if origem:
        linhas.append("origem:")
        for item in origem:
            for chave, caminho in item.items():
                linhas.append(f"  - {chave}: {_escapar(str(caminho))}")
    linhas.append("---")
    return "\n".join(linhas)


def montar(post, *, rascunho: bool = False) -> str:
    """O arquivo inteiro: frontmatter + corpo, com uma linha em branco entre eles."""
    fm = frontmatter(
        titulo=post.titulo,
        descricao=post.descricao,
        data=post.data_publicacao or date.today(),
        pilar=post.pilar or "",
        tags=list(post.tags or []),
        origem=list(post.origem or []),
        rascunho=rascunho,
    )
    corpo = (post.corpo or "").strip()
    return f"{fm}\n\n{corpo}\n"


class ExportacaoErro(Exception):
    """O que impediria o arquivo de existir — ou de passar no CI do blog."""


def destino(diretorio: str | Path, slug: str) -> Path:
    """`<repo do blog>/content/blog/<slug>.mdx`.

    O slug é validado antes de virar caminho. Não é paranoia decorativa: ele
    vem de um campo de texto do painel, e `../../.ssh/config` é um slug tão
    válido para `Path` quanto `rag-que-diz-nao-sei`.
    """
    if not taxonomia.SLUG_RE.match(slug):
        raise ExportacaoErro(f"slug inválido: {slug!r}")
    return Path(diretorio).expanduser() / f"{slug}.mdx"


def exportar(post, *, diretorio: str | Path, rascunho: bool = False) -> Path:
    """Escreve o `.mdx` e devolve o caminho. Não toca no git."""
    erros = taxonomia.validar_frontmatter(
        slug=post.slug,
        titulo=post.titulo,
        descricao=post.descricao,
        pilar=post.pilar,
        tags=list(post.tags or []),
        data=post.data_publicacao,
        origem=list(post.origem or []),
    )
    if erros:
        raise ExportacaoErro("; ".join(erros))

    caminho = destino(diretorio, post.slug)
    if not caminho.parent.is_dir():
        raise ExportacaoErro(
            f"{caminho.parent} não existe — aponte BLOG_REPO_DIR para o repo do blog"
        )
    caminho.write_text(montar(post, rascunho=rascunho), encoding="utf-8")
    return caminho
