"""A prévia renderizada — escrever o rascunho e mandar o blog regerar o índice.

O `npm run conteudo` é substituído em todos os testes: a suíte não pode
depender de o repo do blog estar clonado nem de haver node na máquina. O que se
testa é o contrato em volta dele — que a prévia **sempre** escreve rascunho, e
que a saída do gerador chega inteira quando ele reprova, porque é ela que diz o
que o linter de privacidade do blog achou.
"""
from __future__ import annotations

import pytest

from app.blog import previa, servico
from tests.test_blog import CORPO_BOM, DESCRICAO  # o post que fecha as camadas

# A de verdade, guardada antes de o `dev_fora` trocá-la em todo teste.
SUBIR_BLOG = previa.subir_blog


@pytest.fixture
def repo_falso(tmp_path):
    (tmp_path / "content" / "blog").mkdir(parents=True)
    return tmp_path


@pytest.fixture
async def post(repo_falso):
    novo = await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")
    return await servico.salvar(
        novo.id,
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


@pytest.fixture(autouse=True)
def gerador_ok(monkeypatch):
    """Por padrão o gerador do blog passa. Cada teste que precisa, troca."""
    chamadas: list = []

    async def falso(repo):
        chamadas.append(repo)
        return 0, "índice gerado: 2 posts"

    monkeypatch.setattr(previa, "gerar_indice", falso)
    return chamadas


@pytest.fixture(autouse=True)
def dev_fora(monkeypatch):
    """Sem `next dev` na suíte, e sem subir um de verdade: `subir_blog` falha."""
    monkeypatch.setattr(previa, "_servidor_de_pe", lambda url: False)
    subidas: list = []

    async def nao_sobe(repo, url):
        subidas.append((repo, url))
        return False

    monkeypatch.setattr(previa, "subir_blog", nao_sobe)
    return subidas


async def test_blog_parado_e_subido_pela_previa(post, repo_falso, dev_fora):
    """O passo que eu esquecia: a prévia tenta subir o blog antes de devolver a URL."""
    r = await previa.montar(post, repo=repo_falso, url_dev="http://localhost:3000")
    assert dev_fora == [(repo_falso, "http://localhost:3000")]
    assert "logs/blog-dev.log" in r["aviso"]


async def test_subir_blog_nao_sobe_segundo_servidor(monkeypatch, tmp_path):
    """Com o blog de pé, nenhum processo novo: dois `next dev` brigam pelo `.next`."""
    monkeypatch.setattr(previa, "_servidor_de_pe", lambda url: True)

    async def proibido(*a, **k):
        raise AssertionError("não era para subir outro next dev")

    monkeypatch.setattr(previa.asyncio, "create_subprocess_exec", proibido)
    assert await SUBIR_BLOG(tmp_path, "http://localhost:3000") is True


async def test_subir_blog_usa_a_porta_da_url(monkeypatch, tmp_path):
    estados = iter([False, False, True])
    monkeypatch.setattr(previa, "_servidor_de_pe", lambda url: next(estados))
    monkeypatch.setattr(previa, "LOGS_DIR", tmp_path)
    chamadas: list = []

    async def falso(*args, **kwargs):
        chamadas.append((args, kwargs))

    monkeypatch.setattr(previa.asyncio, "create_subprocess_exec", falso)
    assert await SUBIR_BLOG(tmp_path, "http://localhost:3005") is True
    args, kwargs = chamadas[0]
    assert args == ("npm", "run", "dev", "--", "-p", "3005")
    assert kwargs["start_new_session"] is True


async def test_post_no_ar_nao_vira_rascunho_na_previa(post, repo_falso):
    """`draft: true` num post publicado, no working tree do blog, é um commit
    por engano de distância de tirar o post do ar."""
    no_ar = await servico.mudar_estado(post.id, "publicado")
    await previa.montar(no_ar, repo=repo_falso)
    arquivo = repo_falso / "content" / "blog" / "rag-que-diz-nao-sei.mdx"
    assert "draft: false" in arquivo.read_text(encoding="utf-8")


async def test_escreve_o_arquivo_e_devolve_a_url(post, repo_falso, gerador_ok):
    r = await previa.montar(post, repo=repo_falso, url_dev="http://localhost:3000")

    assert r["url"] == "http://localhost:3000/blog/rag-que-diz-nao-sei"
    assert (repo_falso / "content" / "blog" / "rag-que-diz-nao-sei.mdx").is_file()
    assert gerador_ok == [repo_falso]


async def test_a_previa_sempre_sai_como_rascunho(post, repo_falso):
    """Mesmo com o post `pronto`: prever não é decidir que está publicável."""
    pronto = await servico.mudar_estado(post.id, "pronto")
    await previa.montar(pronto, repo=repo_falso)

    arquivo = repo_falso / "content" / "blog" / "rag-que-diz-nao-sei.mdx"
    assert "draft: true" in arquivo.read_text(encoding="utf-8")


async def test_previa_nao_marca_o_post_como_exportado(post, repo_falso):
    await previa.montar(post, repo=repo_falso)
    assert (await servico.obter(post.id)).exportado_em is None


async def test_gerador_reprovando_traz_a_saida_inteira(post, repo_falso, monkeypatch):
    """É por aqui que o linter de privacidade do blog fala comigo."""
    recusa = "content/blog/x.mdx: IP interno encontrado na linha 12"

    async def falso(repo):
        return 1, recusa

    monkeypatch.setattr(previa, "gerar_indice", falso)

    with pytest.raises(previa.PreviaErro) as e:
        await previa.montar(post, repo=repo_falso)
    assert recusa in str(e.value)


async def test_repo_do_blog_ausente_avisa_qual_variavel_ajustar(post, tmp_path):
    with pytest.raises(previa.PreviaErro) as e:
        await previa.montar(post, repo=tmp_path / "nao-existe")
    assert "BLOG_REPO_DIR" in str(e.value)


async def test_post_sem_frontmatter_nao_chega_a_rodar_o_gerador(repo_falso, gerador_ok):
    """Sem slug não há arquivo — e sem arquivo não faz sentido regerar índice."""
    from app.blog import mdx

    pauta = await servico.criar(titulo="Ideia solta")
    with pytest.raises(mdx.ExportacaoErro):
        await previa.montar(pauta, repo=repo_falso)
    assert gerador_ok == []


async def test_sem_aviso_quando_o_servidor_responde(post, repo_falso, monkeypatch):
    async def de_pe(repo, url):
        return True

    monkeypatch.setattr(previa, "subir_blog", de_pe)
    r = await previa.montar(post, repo=repo_falso)
    assert r["servidor_de_pe"] is True and r["aviso"] is None
