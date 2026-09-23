"""Traz um post que já existe como `.mdx` para dentro da redação.

    python scripts/importar_mdx.py ~/Documentos/pabloortiz.dev/content/blog/x.mdx
    python scripts/importar_mdx.py --todos          # tudo que está com draft: true
    python scripts/importar_mdx.py --todos --conferir   # só mostra o diagnóstico

Serve duas vezes. A primeira é a mudança de casa: os rascunhos que hoje moram no
repo do blog passam a morar no CMS, que é onde eles podem ser medidos. A segunda
é o caminho de volta, no dia em que eu editar o `.mdx` à mão e quiser o texto
de novo aqui.

Só importa **rascunho** por padrão. Post publicado não volta para a redação: o
que está no ar é o arquivo no git, e ter duas fontes da verdade para o mesmo
texto publicado é o jeito mais rápido de publicar a versão errada.

O frontmatter é lido com um parser mínimo — o suficiente para o formato que o
`app/blog/mdx.py` escreve, e nada além. Puxar um PyYAML para ler oito chaves
seria pagar uma dependência para não escrever trinta linhas.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.blog import servico  # noqa: E402
from app.blog.taxonomia import SLUG_RE  # noqa: E402
from app.db.models.blog import BlogPost  # noqa: E402
from app.db.session import get_session  # noqa: E402


def separar(texto: str) -> tuple[dict, str]:
    """Frontmatter e corpo. Arquivo sem `---` no topo é erro, não corpo solto."""
    if not texto.startswith("---\n"):
        raise ValueError("arquivo sem frontmatter")
    fim = texto.index("\n---", 4)
    return ler_frontmatter(texto[4:fim]), texto[fim + 4 :].lstrip("\n")


def _valor(bruto: str):
    bruto = bruto.strip()
    if bruto.startswith('"'):
        return json.loads(bruto)
    if bruto.startswith("["):
        return [t.strip().strip('"') for t in bruto[1:-1].split(",") if t.strip()]
    if bruto in ("true", "false"):
        return bruto == "true"
    return bruto


def ler_frontmatter(bloco: str) -> dict:
    dados: dict = {}
    chave_lista: str | None = None
    for linha in bloco.split("\n"):
        if not linha.strip():
            continue
        # Item de lista de objetos: "  - copiloto: "docs/fase03.md"".
        if linha.lstrip().startswith("- ") and chave_lista:
            item = linha.lstrip()[2:]
            k, _, v = item.partition(":")
            dados[chave_lista].append({k.strip(): _valor(v)})
            continue
        if not linha.startswith(" "):
            chave, _, resto = linha.partition(":")
            if resto.strip() == "":
                chave_lista = chave.strip()
                dados[chave_lista] = []
            else:
                chave_lista = None
                dados[chave.strip()] = _valor(resto)
    return dados


async def existe(slug: str) -> BlogPost | None:
    from sqlalchemy import select

    async with get_session() as session:
        return await session.scalar(select(BlogPost).where(BlogPost.slug == slug))


async def importar(caminho: Path, *, conferir: bool = False) -> None:
    fm, corpo = separar(caminho.read_text(encoding="utf-8"))
    slug = caminho.stem
    if not SLUG_RE.match(slug):
        print(f"  ✗ {caminho.name}: nome de arquivo não é um slug válido")
        return

    if not fm.get("draft", False):
        print(f"  — {slug}: já publicado, não volta para a redação")
        return

    ja = await existe(slug)
    if ja and not conferir:
        post = await servico.salvar(
            ja.id,
            {
                "titulo": fm.get("titulo", ja.titulo),
                "descricao": fm.get("descricao"),
                "corpo": corpo,
                "pilar": fm.get("pilar"),
                "tags": fm.get("tags", []),
                "origem": fm.get("origem", []),
                "data_publicacao": str(fm.get("data")) if fm.get("data") else None,
            },
        )
        print(f"  ↻ {slug}: atualizado (o corpo anterior virou versão)")
    elif ja:
        post = ja
        print(f"  = {slug}: já está na redação")
    else:
        novo = await servico.criar(titulo=fm.get("titulo", slug), pilar=fm.get("pilar"))
        post = await servico.salvar(
            novo.id,
            {
                "slug": slug,
                "descricao": fm.get("descricao"),
                "corpo": corpo,
                "tags": fm.get("tags", []),
                "origem": fm.get("origem", []),
                "data_publicacao": str(fm.get("data")) if fm.get("data") else None,
            },
        )
        if conferir:
            print(f"  + {slug}: entraria na redação")
        else:
            print(f"  + {slug}: importado")

    d = servico.diagnostico(post)
    print(f"      {d['palavras']} palavras · {d['minutos']} min")
    if d["exportavel"]:
        print("      ✓ as cinco camadas fecharam e o frontmatter passa")
    for item in d["falta"] + d["frontmatter_erros"]:
        print(f"      ✗ {item}")


async def principal(args) -> int:
    if args.todos:
        pasta = Path(args.pasta).expanduser()
        if not pasta.is_dir():
            print(f"pasta não encontrada: {pasta}")
            return 1
        arquivos = sorted(pasta.glob("*.mdx"))
    else:
        arquivos = [Path(a).expanduser() for a in args.arquivo]

    if not arquivos:
        print("nada para importar")
        return 0

    for arquivo in arquivos:
        if not arquivo.is_file():
            print(f"  ✗ {arquivo}: não existe")
            continue
        try:
            await importar(arquivo, conferir=args.conferir)
        except ValueError as e:
            print(f"  ✗ {arquivo.name}: {e}")
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("arquivo", nargs="*", help="um ou mais .mdx")
    p.add_argument("--todos", action="store_true", help="varre a pasta do blog")
    p.add_argument(
        "--pasta",
        default="~/Documentos/pabloortiz.dev/content/blog",
        help="onde varrer com --todos",
    )
    p.add_argument("--conferir", action="store_true", help="não grava nada novo")
    sys.exit(asyncio.run(principal(p.parse_args())))
