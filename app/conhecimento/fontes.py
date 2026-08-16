"""De onde o conhecimento vem — um `Documento` por arquivo ou registro.

Cada fonte só sabe **ler e normalizar**. Chunkar, embedar e gravar é trabalho do
indexador. Assim uma fonte nova (e-mail, transcrição, edital) é um arquivo de 30
linhas, não uma reforma.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger()

# Pastas que nunca são conhecimento — e que, se entrarem, enchem o índice com
# dezenas de milhares de READMEs de biblioteca. O `Estudos/` desta máquina tem
# 12.264 arquivos, dos quais 16 são do Pablo.
IGNORAR = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", ".next", "dist",
    "build", ".ruff_cache", ".pytest_cache", "site-packages", ".cache",
    "target", "vendor", ".obsidian", ".trash", ".claude",
}

_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TAG = re.compile(r"(?:^|\s)#([a-zA-ZÀ-ÿ][\w/-]{1,40})")
_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


@dataclass(slots=True)
class Documento:
    """Um texto inteiro, antes de virar chunks."""

    fonte_tipo: str
    fonte_ref: str
    titulo: str
    conteudo: str
    metadados: dict = field(default_factory=dict)

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.conteudo.encode("utf-8")).hexdigest()


def _frontmatter(texto: str) -> tuple[dict, str]:
    """Lê o frontmatter YAML sem depender de PyYAML.

    Só `chave: valor` e listas simples — que é o que o Obsidian escreve. Um
    parser completo aqui seria uma dependência para ler quatro linhas.
    """
    m = _FRONTMATTER.match(texto)
    if not m:
        return {}, texto

    dados: dict = {}
    chave_lista: str | None = None
    for linha in m.group(1).splitlines():
        if not linha.strip():
            continue
        if linha.lstrip().startswith("- ") and chave_lista:
            dados.setdefault(chave_lista, []).append(linha.split("-", 1)[1].strip())
            continue
        if ":" in linha:
            chave, _, valor = linha.partition(":")
            chave, valor = chave.strip(), valor.strip()
            if not valor:
                chave_lista = chave
                dados[chave] = []
            else:
                chave_lista = None
                if valor.startswith("[") and valor.endswith("]"):
                    dados[chave] = [v.strip().strip("\"'") for v in valor[1:-1].split(",") if v.strip()]
                else:
                    dados[chave] = valor.strip("\"'")
    return dados, texto[m.end():]


def _tags_e_links(texto: str, frontmatter: dict) -> dict:
    tags = {t.lower() for t in _TAG.findall(texto)}
    do_fm = frontmatter.get("tags") or frontmatter.get("tag")
    if isinstance(do_fm, str):
        tags.update(t.strip().lower() for t in do_fm.split(",") if t.strip())
    elif isinstance(do_fm, list):
        tags.update(str(t).lower() for t in do_fm)

    meta: dict = {}
    if tags:
        meta["tags"] = sorted(tags)
    links = sorted(set(_WIKILINK.findall(texto)))
    if links:
        meta["wikilinks"] = links
    if frontmatter:
        meta["frontmatter"] = frontmatter
    return meta


def _titulo(frontmatter: dict, corpo: str, arquivo: Path) -> str:
    """Frontmatter → primeiro H1 → nome do arquivo.

    O H1 antes do nome do arquivo porque `n.md` e `04 - Classificação.md`
    dizem muito menos que o título que a pessoa escreveu dentro.
    """
    do_fm = frontmatter.get("title") or frontmatter.get("titulo")
    if do_fm:
        return str(do_fm)
    h1 = _H1.search(corpo)
    return h1.group(1).strip() if h1 else arquivo.stem


def _relevante(caminho: Path) -> bool:
    return not any(parte in IGNORAR for parte in caminho.parts)


def ler_markdown(raiz: Path, *, fonte_tipo: str = "nota") -> Iterator[Documento]:
    """Todos os `.md` de uma pasta (ou o arquivo, se `raiz` for um arquivo)."""
    raiz = raiz.expanduser()
    if not raiz.exists():
        logger.warning(f"Fonte inexistente, pulando: {raiz}")
        return

    arquivos = [raiz] if raiz.is_file() else sorted(raiz.rglob("*.md"))
    for arquivo in arquivos:
        if not _relevante(arquivo.relative_to(raiz) if raiz.is_dir() else arquivo):
            continue
        try:
            bruto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            logger.warning(f"Não consegui ler {arquivo}: {e}")
            continue
        if not bruto.strip():
            continue

        frontmatter, corpo = _frontmatter(bruto)
        meta = _tags_e_links(corpo, frontmatter)
        meta["arquivo"] = arquivo.name
        yield Documento(
            fonte_tipo=fonte_tipo,
            fonte_ref=str(arquivo),
            titulo=_titulo(frontmatter, corpo, arquivo),
            conteudo=corpo.strip(),
            metadados=meta,
        )
