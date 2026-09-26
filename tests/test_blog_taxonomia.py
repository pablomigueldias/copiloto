"""A cópia das regras do blog, conferida contra o original.

`app/blog/taxonomia.py` repete, em Python, as listas e os limites que o blog
define em `src/content/schema.ts`. Cópia é dívida; este arquivo é o juro.

Se o repo do blog não estiver na máquina, os testes de comparação pulam: dois
repos independentes não podem virar um só por causa de duas listas.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from app.blog import taxonomia

BLOG = Path(
    os.getenv("BLOG_REPO_DIR", "~/Documentos/pabloortiz.dev")
).expanduser()
SCHEMA = BLOG / "src" / "content" / "schema.ts"

precisa_do_blog = pytest.mark.skipif(
    not SCHEMA.is_file(), reason=f"repo do blog não encontrado em {SCHEMA}"
)


def _lista(nome: str, fonte: str) -> list[str]:
    """A lista `nome` declarada no schema — ou no arquivo de onde ele a reexporta.

    O blog moveu `PILARES` para `pilares.ts` em 22/09/2026 (o schema puxa Zod, e
    as páginas que só querem os pilares não podem arrastar o Zod para o Worker).
    Este teste existe justamente para pegar esse tipo de mudança, então ele
    segue o `import ... from "./x.ts"` em vez de exigir tudo num arquivo só.
    """
    bloco = re.search(rf"{nome}\s*=\s*\[(.*?)\]\s*as const", fonte, re.DOTALL)
    if not bloco:
        reexport = re.search(
            rf'import\s*\{{[^}}]*\b{nome}\b[^}}]*\}}\s*from\s*"\.\/([\w.-]+)"', fonte
        )
        assert reexport, f"não achei {nome} nem no schema.ts nem num import dele"
        vizinho = SCHEMA.parent / reexport.group(1)
        assert vizinho.is_file(), f"o schema importa {nome} de {vizinho}, que não existe"
        return _lista(nome, vizinho.read_text(encoding="utf-8"))
    return re.findall(r'"([^"]+)"', bloco.group(1))


@precisa_do_blog
def test_pilares_batem_com_o_blog():
    assert list(taxonomia.PILARES) == _lista("PILARES", SCHEMA.read_text(encoding="utf-8"))


@precisa_do_blog
def test_tags_batem_com_o_blog():
    assert list(taxonomia.TAGS) == _lista("TAGS", SCHEMA.read_text(encoding="utf-8"))


@precisa_do_blog
def test_limites_batem_com_o_blog():
    fonte = SCHEMA.read_text(encoding="utf-8")
    titulo = re.search(r"titulo:\s*z\.string\(\)\.min\((\d+)\)\.max\((\d+)\)", fonte)
    descricao = re.search(r"descricao:\s*z\.string\(\)\.min\((\d+)\)\.max\((\d+)\)", fonte)
    tags_max = re.search(r"\.max\((\d+)\)\s*\n?\s*\.default\(\[\]\)", fonte)
    assert titulo and (int(titulo[1]), int(titulo[2])) == (
        taxonomia.TITULO_MIN,
        taxonomia.TITULO_MAX,
    )
    assert descricao and (int(descricao[1]), int(descricao[2])) == (
        taxonomia.DESCRICAO_MIN,
        taxonomia.DESCRICAO_MAX,
    )
    assert tags_max and int(tags_max[1]) == taxonomia.TAGS_MAX


# ── a validação em si (não depende do repo do blog) ───────────────────

BOM = dict(
    slug="rag-que-diz-nao-sei",
    titulo="Um RAG que sabe dizer: não está nas minhas notas",
    descricao="Busca vetorial nunca volta vazia. Como um corte de distância fez meu RAG recusar em 0,2 s.",
    pilar="ia-llms",
    tags=["rag", "pgvector"],
    data="2026-09-22",
    origem=[{"copiloto": "docs/fase03.md"}],
)


def test_frontmatter_bom_nao_tem_erro():
    assert taxonomia.validar_frontmatter(**BOM) == []


def test_post_do_pilar_de_negocio_valida():
    """O pilar do dono de negócio (passo 8.1) abre com tags do assunto dele."""
    post = {
        **BOM,
        "slug": "quanto-um-lead-esfria-em-uma-hora",
        "titulo": "Quanto um paciente esfria em uma hora sem resposta",
        "pilar": "automacao-negocio",
        "tags": ["whatsapp", "atendimento"],
    }
    assert taxonomia.validar_frontmatter(**post) == []


def test_lista_todos_os_erros_de_uma_vez():
    """Um erro por vez, com um round-trip de painel a cada um, é o que faz
    ninguém usar a ferramenta."""
    erros = taxonomia.validar_frontmatter(
        **{**BOM, "slug": None, "pilar": "carreira", "descricao": "curta"}
    )
    assert len(erros) == 3


def test_slug_com_barra_e_recusado():
    erros = taxonomia.validar_frontmatter(**{**BOM, "slug": "../../etc/passwd"})
    assert any("slug inválido" in e for e in erros)


def test_origem_com_caminho_absoluto_e_recusada():
    erros = taxonomia.validar_frontmatter(
        **{**BOM, "origem": [{"vault": "/caminho/absoluto/nota.md"}]}
    )
    assert any("caminho absoluto" in e for e in erros)


def test_tag_fora_da_lista_curada_e_recusada():
    erros = taxonomia.validar_frontmatter(**{**BOM, "tags": ["rag", "kubernetes"]})
    assert any("kubernetes" in e for e in erros)
