"""A redação: máquina de estados, versionamento e exportação.

Contra Postgres de verdade, sem Ollama — o CMS desta fase não gera texto.

O teste que mais importa é o do versionamento: se ele falhar em silêncio, a
descoberta vem no dia em que eu apagar um parágrafo bom e for buscá-lo de volta.
"""
from __future__ import annotations

import pytest

from app.blog import mdx, servico
from app.blog.taxonomia import PILARES

CORPO_BOM = """\
Perguntei ao assistente quais eram as figuras de linguagem. Ele trouxe três
trechos sobre lógica difusa, nenhum sobre o assunto.

## O problema

A busca vetorial nunca volta vazia. O corte por distância fez a recusa sair em
0,2 s, contra 12 s de antes.

```python
if distancia > CORTE:
    return None
```

## O que eu faria diferente

Mediria antes. Código no [repositório](https://github.com/pablomigueldias/copiloto).

Tem um RAG que nunca diz "não sei"? [Me chama](/contato).
"""

DESCRICAO = (
    "Busca vetorial nunca volta vazia. Como um corte de distância fez meu RAG "
    "recusar em 0,2 s."
)


@pytest.fixture
async def pauta():
    return await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")


@pytest.fixture
async def pronto(pauta):
    return await servico.salvar(
        pauta.id,
        {
            "slug": "rag-que-diz-nao-sei",
            "titulo": "Um RAG que sabe dizer: não está nas minhas notas",
            "descricao": DESCRICAO,
            "corpo": CORPO_BOM,
            "tags": ["rag", "pgvector"],
            "origem": [{"copiloto": "docs/fase03.md"}],
            "data_publicacao": "2026-09-22",
        },
    )


# ── estados ───────────────────────────────────────────────────────────


async def test_nasce_como_pauta(pauta):
    assert pauta.estado == "pauta"
    assert pauta.corpo == ""


async def test_criar_com_corpo_ja_nasce_rascunho():
    post = await servico.criar(titulo="Veio do vault", corpo="um parágrafo qualquer")
    assert post.estado == "rascunho"


async def test_pauta_que_ganha_corpo_vira_rascunho(pauta):
    post = await servico.salvar(pauta.id, {"corpo": "primeira linha"})
    assert post.estado == "rascunho"


async def test_pronto_exige_as_camadas_verdes(pauta):
    """O portão do `pronto` — e a mensagem precisa dizer o que falta."""
    with pytest.raises(servico.NaoEstaPronto) as e:
        await servico.mudar_estado(pauta.id, "pronto")
    assert "Abertura" in str(e.value) or "slug" in str(e.value)


async def test_pronto_passa_quando_o_post_esta_inteiro(pronto):
    post = await servico.mudar_estado(pronto.id, "pronto")
    assert post.estado == "pronto"


async def test_arquivar_nao_tem_portao(pauta):
    """Ideia que não vingou sai da frente sem precisar estar boa."""
    post = await servico.mudar_estado(pauta.id, "arquivado")
    assert post.estado == "arquivado"


async def test_estado_inventado_e_recusado(pauta):
    with pytest.raises(servico.EstadoInvalido):
        await servico.mudar_estado(pauta.id, "publicando")


# ── versionamento ─────────────────────────────────────────────────────


async def test_mudar_o_corpo_guarda_a_versao_anterior(pauta):
    await servico.salvar(pauta.id, {"corpo": "versão um"})
    await servico.salvar(pauta.id, {"corpo": "versão dois"})

    vs = await servico.versoes(pauta.id)
    assert [v.numero for v in vs] == [2, 1]
    # A versão guarda o texto de ANTES do salvamento que a criou.
    assert vs[0].corpo == "versão um"
    assert vs[1].corpo == ""


async def test_salvar_sem_mexer_no_corpo_nao_versiona(pauta):
    await servico.salvar(pauta.id, {"corpo": "texto"})
    await servico.salvar(pauta.id, {"descricao": DESCRICAO})
    await servico.salvar(pauta.id, {"corpo": "texto"})  # mesmo texto

    assert len(await servico.versoes(pauta.id)) == 1


async def test_versao_guarda_o_tamanho(pauta):
    await servico.salvar(pauta.id, {"corpo": "uma duas três"})
    await servico.salvar(pauta.id, {"corpo": "outro"})
    assert (await servico.versoes(pauta.id))[0].palavras == 3


async def test_campo_fora_da_lista_branca_e_recusado(pauta):
    """`estado` tem portão próprio; entrar por aqui seria a porta dos fundos."""
    with pytest.raises(servico.BlogErro):
        await servico.salvar(pauta.id, {"estado": "pronto"})


# ── diagnóstico ───────────────────────────────────────────────────────


async def test_diagnostico_de_pauta_vazia_lista_o_que_falta(pauta):
    d = servico.diagnostico(pauta)
    assert not d["exportavel"]
    assert d["falta"]
    assert any("slug" in e for e in d["frontmatter_erros"])
    assert d["palavras"] == 0


async def test_diagnostico_de_post_inteiro_fica_verde(pronto):
    d = servico.diagnostico(pronto)
    assert d["camadas_ok"] and not d["frontmatter_erros"] and d["exportavel"]
    assert d["minutos"] >= 1
    assert len(d["camadas"]) == 5


# ── MDX ───────────────────────────────────────────────────────────────


async def test_previa_monta_o_frontmatter_dos_campos(pronto):
    texto = servico.previa(pronto)
    assert texto.startswith("---\n")
    assert 'titulo: "Um RAG que sabe dizer: não está nas minhas notas"' in texto
    assert "pilar: ia-llms" in texto
    assert "tags: [rag, pgvector]" in texto
    assert "data: 2026-09-22" in texto
    assert "lang: pt-BR" in texto
    assert "  - copiloto: \"docs/fase03.md\"" in texto
    # Rascunho enquanto não está `pronto`: o blog não publica o que não fechou.
    assert "draft: true" in texto


async def test_previa_de_post_pronto_sai_sem_draft(pronto):
    post = await servico.mudar_estado(pronto.id, "pronto")
    assert "draft: false" in servico.previa(post)


async def test_titulo_com_aspas_nao_quebra_o_yaml(pauta):
    post = await servico.salvar(pauta.id, {"titulo": 'O RAG que diz "não sei"'})
    assert 'titulo: "O RAG que diz \\"não sei\\""' in servico.previa(post)


async def test_exportar_escreve_o_arquivo(pronto, tmp_path):
    post = await servico.mudar_estado(pronto.id, "pronto")
    saida = await servico.exportar(post.id, diretorio=tmp_path)

    arquivo = tmp_path / "rag-que-diz-nao-sei.mdx"
    assert arquivo.is_file()
    assert saida["caminho"] == str(arquivo)
    assert "draft: false" in arquivo.read_text(encoding="utf-8")
    assert (await servico.obter(post.id)).exportado_em is not None


async def test_exportar_recusa_post_incompleto(pauta, tmp_path):
    with pytest.raises(mdx.ExportacaoErro) as e:
        await servico.exportar(pauta.id, diretorio=tmp_path)
    assert "slug" in str(e.value)


async def test_exportar_nao_sai_da_pasta_de_destino(pronto, tmp_path):
    """Slug vem de um campo de texto: `../../.ssh/config` é `Path` válido."""
    post = await servico.salvar(pronto.id, {"slug": "../fora"})
    with pytest.raises(mdx.ExportacaoErro):
        await servico.exportar(post.id, diretorio=tmp_path)
    assert not (tmp_path.parent / "fora.mdx").exists()


async def test_exportar_avisa_quando_a_pasta_nao_existe(pronto, tmp_path):
    post = await servico.mudar_estado(pronto.id, "pronto")
    with pytest.raises(mdx.ExportacaoErro) as e:
        await servico.exportar(post.id, diretorio=tmp_path / "nao-existe")
    assert "BLOG_REPO_DIR" in str(e.value)


# ── listagem ──────────────────────────────────────────────────────────


async def test_listar_por_estado_e_contagem(pronto):
    """`pronto` sai da mesma pauta (virou rascunho); a outra fica como pauta."""
    outra = await servico.criar(titulo="Ideia para depois")

    total, itens = await servico.listar(estado="pauta")
    assert total == 1 and itens[0].id == outra.id

    por_estado = await servico.contar_por_estado()
    assert por_estado == {"pauta": 1, "rascunho": 1}


async def test_listagem_traz_o_mexido_por_ultimo_no_topo(pronto):
    outra = await servico.criar(titulo="Ideia para depois")
    _, itens = await servico.listar()
    assert itens[0].id == outra.id


async def test_pilares_sao_os_do_blog():
    assert "ia-llms" in PILARES and "dados-ml" in PILARES
