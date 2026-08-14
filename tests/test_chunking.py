"""Chunking — lógica pura, sem banco e sem modelo.

Vale testar com afinco: nenhuma busca encontra o que o chunking picou errado, e
o erro não aparece como exceção, aparece como resposta ruim seis meses depois.
"""
from app.conhecimento.chunking import chunkar


def test_texto_vazio():
    assert chunkar("") == []
    assert chunkar("   \n\n ") == []


def test_quebra_por_heading_com_trilha():
    texto = f"""# Projeto

{"Introdução do projeto. " * 15}

## Instalação

{"Passos de instalação detalhados. " * 15}

### Docker

{"Como subir com docker compose. " * 15}
"""
    chunks = chunkar(texto)
    titulos = [c.titulo for c in chunks]
    assert "Projeto" in titulos[0]
    assert "Projeto > Instalação" in titulos[1]
    # A trilha guarda os pais: sem isso "Docker" sozinho não diz de que projeto.
    assert "Projeto > Instalação > Docker" in titulos[2]


def test_ordem_e_sequencial():
    texto = "\n\n".join(f"## Seção {i}\n\n{'conteúdo longo. ' * 20}" for i in range(4))
    chunks = chunkar(texto)
    assert [c.ordem for c in chunks] == list(range(len(chunks)))


def test_secoes_curtas_sao_juntadas():
    texto = """## A

Curto.

## B

Também curto.

## C

Igualmente.
"""
    chunks = chunkar(texto)
    # Três chunks de cinco palavras seriam três linhas de ruído no índice.
    assert len(chunks) == 1
    assert "Curto." in chunks[0].conteudo and "Igualmente." in chunks[0].conteudo


def test_secao_longa_e_quebrada_com_sobreposicao():
    paragrafos = "\n\n".join(f"Parágrafo número {i}. {'texto ' * 60}" for i in range(8))
    chunks = chunkar(f"## Longa\n\n{paragrafos}")
    assert len(chunks) > 1
    assert all(len(c.conteudo) < 2000 for c in chunks)
    # A emenda entre chunks é coberta: o fim de um reaparece no começo do outro.
    fim_do_primeiro = chunks[0].conteudo.split("\n\n")[-1][:40]
    assert fim_do_primeiro in chunks[1].conteudo


def test_heading_dentro_de_bloco_de_codigo_nao_quebra():
    texto = f"""## Comandos

{"Explicação do comando. " * 12}

```bash
# instala tudo
pip install -e .
# roda
pytest
```

{"Mais explicação depois do bloco. " * 12}
"""
    chunks = chunkar(texto)
    assert all(c.titulo == "Comandos" for c in chunks)
    inteiro = "\n".join(c.conteudo for c in chunks)
    assert "# instala tudo" in inteiro


def test_texto_sem_heading_vira_um_chunk():
    chunks = chunkar("Uma nota solta, sem título nenhum. " * 10)
    assert len(chunks) == 1
    assert chunks[0].titulo is None


def test_titulo_base_prefixa_a_trilha():
    chunks = chunkar("## Seção\n\n" + "conteúdo. " * 40, titulo_base="nota.md")
    assert chunks[0].titulo == "nota.md > Seção"


def test_metadados_sao_copiados_em_cada_chunk():
    chunks = chunkar(
        "## A\n\n" + "x " * 200 + "\n\n## B\n\n" + "y " * 200,
        metadados={"tags": ["rag"]},
    )
    assert len(chunks) >= 2
    assert all(c.metadados == {"tags": ["rag"]} for c in chunks)
    # Cópia, não referência compartilhada.
    chunks[0].metadados["tags"] = []
    assert chunks[1].metadados["tags"] == ["rag"]
