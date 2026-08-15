"""Leitura das fontes de markdown — frontmatter, tags, wikilinks, exclusões."""
from app.conhecimento.fontes import Documento, ler_markdown


def escrever(pasta, nome, texto):
    caminho = pasta / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto)
    return caminho


def test_le_arquivos_e_ignora_pastas_de_dependencia(tmp_path):
    escrever(tmp_path, "nota.md", "# Nota\n\nConteúdo.")
    escrever(tmp_path, "sub/outra.md", "# Outra\n\nConteúdo.")
    escrever(tmp_path, "node_modules/pacote/README.md", "# Lixo\n\nNão indexar.")
    escrever(tmp_path, ".git/COMMIT_EDITMSG", "nada")

    docs = list(ler_markdown(tmp_path))
    nomes = sorted(d.titulo for d in docs)
    assert nomes == ["Nota", "Outra"]


def test_frontmatter_vira_metadado_e_sai_do_corpo(tmp_path):
    escrever(
        tmp_path,
        "n.md",
        """---
titulo: Minha nota
tags: [rag, postgres]
---

# Cabeçalho

Corpo da nota.
""",
    )
    doc = next(iter(ler_markdown(tmp_path)))
    assert doc.titulo == "Minha nota"
    assert doc.metadados["tags"] == ["postgres", "rag"]
    assert "---" not in doc.conteudo
    assert doc.conteudo.startswith("# Cabeçalho")


def test_frontmatter_com_lista_em_linhas(tmp_path):
    escrever(
        tmp_path,
        "n.md",
        """---
tags:
  - Estudo
  - React
---

Conteúdo.
""",
    )
    doc = next(iter(ler_markdown(tmp_path)))
    assert doc.metadados["tags"] == ["estudo", "react"]


def test_tags_inline_e_wikilinks(tmp_path):
    escrever(tmp_path, "n.md", "Estudei #pgvector hoje. Ver [[Busca Híbrida]] e [[RAG|o rag]].")
    doc = next(iter(ler_markdown(tmp_path)))
    assert "pgvector" in doc.metadados["tags"]
    assert doc.metadados["wikilinks"] == ["Busca Híbrida", "RAG"]


def test_arquivo_vazio_e_pulado(tmp_path):
    escrever(tmp_path, "vazio.md", "   \n\n")
    escrever(tmp_path, "cheio.md", "conteúdo")
    assert len(list(ler_markdown(tmp_path))) == 1


def test_pasta_inexistente_nao_explode(tmp_path):
    assert list(ler_markdown(tmp_path / "nao-existe")) == []


def test_hash_muda_com_o_conteudo():
    a = Documento(fonte_tipo="nota", fonte_ref="x", titulo="x", conteudo="um")
    b = Documento(fonte_tipo="nota", fonte_ref="x", titulo="x", conteudo="um")
    c = Documento(fonte_tipo="nota", fonte_ref="x", titulo="x", conteudo="dois")
    assert a.hash == b.hash != c.hash
