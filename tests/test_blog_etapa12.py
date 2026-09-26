"""Etapa 12 do blog: vault → pauta, rascunho no Gemini, LinkedIn e o painel.

**Nenhum teste aqui fala com o Gemini.** O provider é trocado por um falso que
registra o prompt — porque o que precisa ser verdade não é "o modelo escreveu
bem", é *o que saiu da máquina* e *o que o sistema fez com a resposta*.

Os testes que mais importam:

- a **lista branca do vault**: nota de `Curriculos/` ou `Planos/` nunca vira
  pauta, com ou sem a marca;
- o **prompt não leva o campo `notas`** nem caminho da máquina;
- o **teto do mês** recusa antes de chamar;
- o **`{{FALTA}}` bloqueia o `pronto`**.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from app.blog import distribuicao, fluxo, geracao, painel, servico, vault
from app.config import settings
from app.conhecimento.fontes import ler_posts_blog
from app.db.observability import AiCallRecord, registrar_ai_call
from app.llm import gateway
from app.llm.tipos import RespostaCrua
from tests.test_blog import CORPO_BOM, DESCRICAO

# ── vault de mentira ───────────────────────────────────────────────


def _nota(raiz, relativo: str, *, blog: str | None = "ideia", corpo: str = "Texto da nota.") -> None:
    arquivo = raiz / relativo
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---", "titulo: Redes neurais e generalização", "pilar: dados-ml", "tags: [ml, redes]"]
    if blog is not None:
        fm.append(f"blog: {blog}")
    fm.append("---")
    arquivo.write_text("\n".join(fm) + "\n\n" + corpo + "\n", encoding="utf-8")


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    raiz = tmp_path / "vault"
    _nota(raiz, "Pessoal/Machine Learning/Redes/Generalizacao.md")
    _nota(raiz, "Pessoal/Machine Learning/Sem marca.md", blog=None)
    _nota(raiz, "Pessoal/Curriculos/Curriculo 2026.md")  # marcada, mas vetada
    _nota(raiz, "Pessoal/Planos/Metas.md")
    _nota(raiz, "Pessoal/Portugues/Crase.md")  # fora da lista branca
    monkeypatch.setattr(type(settings), "vault_dir", property(lambda self: raiz))
    return raiz


@pytest.fixture
def blog_repo(tmp_path, monkeypatch):
    conteudo = tmp_path / "blog" / "content" / "blog"
    conteudo.mkdir(parents=True)
    (conteudo / "rag-que-diz-nao-sei.mdx").write_text(
        '---\ntitulo: "Um RAG que sabe dizer não"\ndata: 2026-09-22\npilar: ia-llms\n'
        "tags: [rag, pgvector]\ndraft: false\n---\n\n" + CORPO_BOM,
        encoding="utf-8",
    )
    (conteudo / "rascunho.mdx").write_text(
        '---\ntitulo: "Rascunho"\ndata: 2026-09-23\ndraft: true\n---\n\nnão publicado',
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "blog_repo_dir", str(tmp_path / "blog"))
    return conteudo


# ── o provider falso ───────────────────────────────────────────────


class Gemini:
    """Responde em sequência e guarda cada prompt. `nome` não é local: custa."""

    nome = "gemini"

    def __init__(self, *respostas: str) -> None:
        self.respostas = list(respostas)
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        texto = self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]
        return RespostaCrua(texto=texto, modelo=modelo, tokens_input=4000, tokens_output=1500)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture
def chave(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key_blog", "chave-de-teste")
    monkeypatch.setattr(settings, "blog_gemini_teto_usd_mes", 1.0)


@pytest.fixture(autouse=True)
def restaura():
    yield
    gateway.usar_provider(None)


BOA = "DESCRICAO: " + DESCRICAO + "\n---\n" + CORPO_BOM


# ── 1. vault ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("caminho", "ok"),
    [
        ("Pessoal/Machine Learning/Redes/Generalizacao.md", True),
        ("Pessoal/_Sistema-Estudos/README.md", True),
        ("Pessoal/Laboratório de Dados/registros/2026-09-24 - generalizacao.md", True),
        ("Pessoal/Curriculos/Curriculo 2026.md", False),
        ("Pessoal/Machine Learning/Planos/x.md", False),  # vetada dentro da liberada
        ("Pessoal/_Sistema-Estudos/_audio/aula.md", False),
        ("Pessoal/Portugues/Crase.md", False),
        ("Pessoal/Machine Learning/../Curriculos/x.md", False),
        ("/mnt/dados/Second-Brain/Pessoal/Machine Learning/x.md", False),
        ("Pessoal/Machine Learning/imagem.png", False),
    ],
)
def test_lista_branca(caminho, ok):
    assert vault.liberada(caminho) is ok


async def test_candidatas_so_com_marca_e_da_lista_branca(cofre):
    achadas = await vault.candidatas()
    assert [c.caminho for c in achadas] == ["Pessoal/Machine Learning/Redes/Generalizacao.md"]
    c = achadas[0]
    assert c.titulo == "Redes neurais e generalização"
    assert c.pilar == "dados-ml"
    assert c.post_id is None


async def test_importar_cria_pauta_com_origem_e_marca_a_nota(cofre):
    rel = "Pessoal/Machine Learning/Redes/Generalizacao.md"
    post = await vault.importar(rel)

    assert post.estado == "pauta"
    assert post.origem == [{"vault": rel}]
    assert post.pilar == "dados-ml"
    # A matéria-prima não é copiada: o campo privado continua vazio.
    assert not post.notas
    assert "blog: rascunho" in (cofre / rel).read_text(encoding="utf-8")
    # Some da lista de candidatas (a marca mudou).
    assert await vault.candidatas() == []


async def test_importar_duas_vezes_devolve_a_mesma_pauta(cofre):
    rel = "Pessoal/Machine Learning/Redes/Generalizacao.md"
    primeira = await vault.importar(rel)
    segunda = await vault.importar(rel)
    assert primeira.id == segunda.id


async def test_nota_vetada_nao_vira_pauta_mesmo_marcada(cofre):
    with pytest.raises(vault.VaultErro):
        await vault.importar("Pessoal/Curriculos/Curriculo 2026.md")


async def test_nota_sem_marca_nao_vira_pauta(cofre):
    with pytest.raises(vault.VaultErro, match="blog: ideia"):
        await vault.importar("Pessoal/Machine Learning/Sem marca.md")


def test_marcar_muda_so_a_linha_do_blog(cofre):
    rel = "Pessoal/Machine Learning/Redes/Generalizacao.md"
    antes = (cofre / rel).read_text(encoding="utf-8")
    assert vault.marcar(rel, "publicado")
    depois = (cofre / rel).read_text(encoding="utf-8")
    assert depois == antes.replace("blog: ideia", "blog: publicado")


# ── 2. posts publicados no índice ─────────────────────────────────


def test_leitor_do_blog_pula_rascunho_e_usa_a_url(blog_repo):
    docs = list(ler_posts_blog(blog_repo))
    assert [d.metadados["slug"] for d in docs] == ["rag-que-diz-nao-sei"]
    assert docs[0].fonte_ref == "https://pabloortiz.dev/blog/rag-que-diz-nao-sei"
    assert docs[0].fonte_tipo == "blog"


def test_blog_esta_nas_fontes_padrao():
    from app.config import Settings

    padrao = Settings.model_fields["conhecimento_fontes"].default
    assert "blog:~/Documentos/pabloortiz.dev/content/blog" in padrao


# ── 3. o que sai da máquina ───────────────────────────────────────


def test_higienizar_tira_caminho_ip_email_e_token():
    sujo = (
        "rodei em /home/pablo/Documentos/copiloto e /mnt/dados/x no 192.168.0.12:5434, "
        "chave AIzaSyA1234567890abcdefghijklmn, banco postgres://u:s@h/db, "
        "escreva para pablo@exemplo.com ou contato@pabloortiz.dev"
    )
    limpo = geracao.higienizar(sujo)
    for vazado in ("/home/pablo", "/mnt/dados", "192.168", "AIza", "postgres://", "pablo@exemplo"):
        assert vazado not in limpo
    assert "contato@pabloortiz.dev" in limpo


@pytest.mark.parametrize(
    ("rel", "ok"),
    [
        ("docs/fase03.md", True),
        ("README.md", True),
        (".env", False),
        ("data/perfil_mestre.json", False),
        ("docs/../.env.md", False),
        ("docs/sub/x.md", False),
    ],
)
def test_do_copiloto_so_docs_e_readme(rel, ok):
    assert geracao._copiloto_liberado(rel) is ok


async def test_prompt_nao_leva_notas_privadas_nem_caminho(cofre, blog_repo, chave):
    rel = "Pessoal/Machine Learning/Redes/Generalizacao.md"
    _nota(cofre, rel, corpo="Rodei no /home/pablo/lab. Medi 94% de acurácia.")
    post = await vault.importar(rel)
    await servico.salvar(post.id, {"notas": "o cliente ACME pagou R$ 9.000"})

    falso = Gemini(BOA)
    gateway.usar_provider(falso)
    await geracao.gerar_rascunho(post.id)

    prompt = falso.prompts[0]
    assert "ACME" not in prompt
    assert "/home/pablo" not in prompt
    assert "94% de acurácia" in prompt  # a matéria-prima foi
    assert "Um RAG que sabe dizer não" in prompt  # o post publicado, para link e estilo
    assert "Rascunho" not in prompt.split("## A pauta")[0]  # draft não é exemplo


# ── 4. a geração ──────────────────────────────────────────────────


async def test_sem_chave_recusa_sem_chamar(cofre, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key_blog", "")
    post = await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    falso = Gemini(BOA)
    gateway.usar_provider(falso)
    with pytest.raises(geracao.GeracaoErro, match="GEMINI_API_KEY_BLOG"):
        await geracao.gerar_rascunho(post.id)
    assert falso.prompts == []


async def test_teto_do_mes_recusa_antes_de_chamar(cofre, chave):
    await registrar_ai_call(
        AiCallRecord(
            agente="blog.rascunho", tarefa="redigir", provider="gemini",
            modelo="gemini-2.5-pro", prompt="x", resposta="y",
            tokens_input=100_000, tokens_output=100_000, latencia_ms=1, sucesso=True,
        )
    )
    assert await geracao.gasto_do_mes() >= 1.0

    post = await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    falso = Gemini(BOA)
    gateway.usar_provider(falso)
    with pytest.raises(geracao.GeracaoErro, match="teto"):
        await geracao.gerar_rascunho(post.id)
    assert falso.prompts == []


async def test_gasto_de_outro_agente_nao_conta_no_teto(chave):
    await registrar_ai_call(
        AiCallRecord(
            agente="candidatura.curriculo", tarefa="redigir", provider="gemini",
            modelo="gemini-2.5-pro", prompt="x", resposta="y",
            tokens_input=100_000, tokens_output=100_000, latencia_ms=1, sucesso=True,
        )
    )
    assert await geracao.gasto_do_mes() == 0


async def test_rascunho_bom_passa_numa_rodada_e_vai_para_o_corpo(cofre, blog_repo, chave):
    post = await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    falso = Gemini(BOA)
    gateway.usar_provider(falso)

    r = await geracao.gerar_rascunho(post.id)

    assert r["rodadas"] == 1
    assert r["pendentes"] == []
    depois = await servico.obter(post.id)
    assert depois.estado == "rascunho"  # pauta que ganhou corpo
    assert depois.corpo.startswith("Perguntei ao assistente")
    assert depois.descricao == DESCRICAO


async def test_rascunho_ruim_volta_ao_modelo_com_o_que_falta(cofre, blog_repo, chave):
    ruim = "DESCRICAO: curta\n---\nNeste post vou falar de redes neurais. É muito bom."
    post = await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    falso = Gemini(ruim, BOA)
    gateway.usar_provider(falso)

    r = await geracao.gerar_rascunho(post.id)

    assert r["rodadas"] == 2
    revisao = falso.prompts[1]
    assert "reprovou" in revisao
    assert "Neste post" in revisao  # o texto voltou
    assert "abertura" in revisao.lower()  # e a lista do que falta


async def test_rodadas_tem_limite(cofre, blog_repo, chave):
    ruim = "DESCRICAO: curta\n---\nNeste post vou falar de redes neurais."
    post = await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    falso = Gemini(ruim)
    gateway.usar_provider(falso)

    r = await geracao.gerar_rascunho(post.id)

    assert r["rodadas"] == geracao.RODADAS
    assert len(falso.prompts) == geracao.RODADAS
    assert r["pendentes"]  # o que sobrou vermelho vai para mim


async def test_gerar_guarda_a_versao_anterior(cofre, blog_repo, chave):
    post = await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    await servico.salvar(post.id, {"corpo": "o que eu tinha escrito à mão"})
    gateway.usar_provider(Gemini(BOA))

    await geracao.gerar_rascunho(post.id)

    versoes = await servico.versoes(post.id)
    assert versoes[0].corpo == "o que eu tinha escrito à mão"


async def test_gerar_recusa_post_publicado(chave):
    post = await servico.criar(titulo="Já no ar", origem=[{"copiloto": "README.md"}])
    await servico.mudar_estado(post.id, "publicado")
    with pytest.raises(geracao.GeracaoErro, match="publicado"):
        await geracao.gerar_rascunho(post.id)


def test_gateway_manda_o_blog_para_a_chave_do_blog(monkeypatch):
    outros = [("redigir", "conhecimento.transcricao.bloco1"), ("compreender", "x")]
    antes = [gateway.rota(t, a) for t, a in outros]

    monkeypatch.setattr(settings, "gemini_api_key_blog", "chave-de-teste")
    r = gateway.rota("redigir", "blog.rascunho")
    assert r.provider == "gemini_blog"
    assert r.modelo == settings.blog_gemini_modelo
    # O resto do Copiloto não muda de rota por causa da chave do blog.
    assert [gateway.rota(t, a) for t, a in outros] == antes


def test_sem_chave_do_blog_o_blog_nao_usa_a_outra(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key_blog", "")
    monkeypatch.setattr(settings, "gemini_api_key", "chave-do-copiloto")
    assert gateway.rota("redigir", "blog.rascunho").provider == "ollama"


# ── 5. {{FALTA}} ──────────────────────────────────────────────────


async def test_falta_aberto_bloqueia_o_pronto():
    post = await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")
    corpo = CORPO_BOM.replace("0,2 s, contra 12 s", "{{FALTA: quanto tempo levava antes?}} 0,2 s, contra 12 s")
    post = await servico.salvar(
        post.id,
        {
            "slug": "rag-que-diz-nao-sei",
            "titulo": "Um RAG que sabe dizer: não está nas minhas notas",
            "descricao": DESCRICAO,
            "corpo": corpo,
            "tags": ["rag", "pgvector"],
            "origem": [{"copiloto": "docs/fase03.md"}],
            "data_publicacao": "2026-09-22",
        },
    )
    d = servico.diagnostico(post)
    assert d["faltas"] == ["quanto tempo levava antes?"]
    assert not d["exportavel"]
    with pytest.raises(servico.NaoEstaPronto, match="FALTA"):
        await servico.mudar_estado(post.id, "pronto")


# ── 6. LinkedIn ───────────────────────────────────────────────────


LINKEDIN_BOM = (
    "Perguntei ao meu assistente sobre figuras de linguagem e ele respondeu com lógica difusa.\n\n"
    "Um corte de distância fez a recusa sair em 0,2 s, contra 12 s de antes.\n\n"
    "Aprendi que medir o vazio vale mais que ajustar o prompt.\n\n"
    "https://pabloortiz.dev/blog/rag-que-diz-nao-sei"
)


@pytest.fixture
async def no_ar():
    post = await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")
    await servico.salvar(post.id, {"slug": "rag-que-diz-nao-sei", "corpo": CORPO_BOM})
    return await servico.mudar_estado(post.id, "publicado")


def test_linkedin_na_quarta_seguinte():
    assert distribuicao.proxima_data(date(2026, 9, 22)) == date(2026, 9, 23)  # terça → quarta
    assert distribuicao.proxima_data(date(2026, 9, 23)) == date(2026, 9, 30)  # quarta → a outra


def test_regua_do_linkedin():
    assert distribuicao.checar(LINKEDIN_BOM, slug="rag-que-diz-nao-sei") == []
    ruim = "Solução robusta! 🚀 #a #b #c #d\n```py\nx\n```"
    problemas = " ".join(distribuicao.checar(ruim, slug="rag-que-diz-nao-sei"))
    for esperado in ("link", "código", "hashtags", "emoji", "proibida"):
        assert esperado in problemas


async def test_gerar_linkedin_grava_texto_e_data(no_ar, chave):
    gateway.usar_provider(Gemini(LINKEDIN_BOM))
    r = await distribuicao.gerar_linkedin(no_ar.id)

    assert r["pendentes"] == []
    post = await servico.obter(no_ar.id)
    assert post.linkedin_texto == LINKEDIN_BOM
    assert post.linkedin_em is not None


async def test_linkedin_nao_sai_de_rascunho(chave):
    post = await servico.criar(titulo="x")
    with pytest.raises(geracao.GeracaoErro):
        await distribuicao.gerar_linkedin(post.id)


# ── 7. o painel ───────────────────────────────────────────────────


def test_proxima_terca():
    assert painel.proxima_terca(date(2026, 9, 23)) == date(2026, 9, 29)  # quarta
    assert painel.proxima_terca(date(2026, 9, 29)) == date(2026, 9, 29)  # a própria terça


async def test_fila_vazia_pede_pauta_e_data(monkeypatch, tmp_path):
    monkeypatch.setattr(type(settings), "vault_dir", property(lambda self: tmp_path))
    r = await painel.resumo(hoje=date(2026, 9, 23))
    tipos = [p["tipo"] for p in r["proximos"]]
    assert tipos == ["pauta", "calendario"]
    assert r["m4"] == {"publicados": 0, "minimo": 5, "completo": 10}
    assert len(r["calendario"]) == painel.SEMANAS_NO_CALENDARIO


async def test_pr_aberto_vem_antes_de_tudo(monkeypatch, tmp_path):
    monkeypatch.setattr(type(settings), "vault_dir", property(lambda self: tmp_path))
    await servico.criar(titulo="Uma pauta qualquer")
    pronto = await servico.criar(titulo="Quase no ar")
    from app.db.models.blog import BlogPost
    from app.db.session import get_session

    # Direto no banco: o `pronto` tem portão, e o que se testa aqui é a ordem.
    async with get_session() as s:
        alvo = await s.get(BlogPost, pronto.id)
        alvo.estado = "pronto"
        alvo.pr_numero = 41
        await s.commit()

    r = await painel.resumo(hoje=date(2026, 9, 23))
    assert r["proximos"][0]["tipo"] == "publicar"
    assert r["proximos"][0]["post_id"] == str(pronto.id)


async def test_pauta_com_fonte_e_chave_sugere_gerar(cofre, chave):
    await vault.importar("Pessoal/Machine Learning/Redes/Generalizacao.md")
    r = await painel.resumo(hoje=date(2026, 9, 23))
    assert "gerar" in [p["tipo"] for p in r["proximos"]]


async def test_post_da_semana_tira_o_aviso_do_calendario(monkeypatch, tmp_path):
    monkeypatch.setattr(type(settings), "vault_dir", property(lambda self: tmp_path))
    p = await servico.criar(titulo="Busca híbrida")
    await servico.salvar(p.id, {"data_publicacao": "2026-09-29"})
    r = await painel.resumo(hoje=date(2026, 9, 23))
    assert "calendario" not in [x["tipo"] for x in r["proximos"]]
    assert r["calendario"][0]["posts"][0]["titulo"] == "Busca híbrida"


async def test_linkedin_so_e_cobrado_ate_marcar_postado(monkeypatch, tmp_path, no_ar):
    monkeypatch.setattr(type(settings), "vault_dir", property(lambda self: tmp_path))
    ontem = date.today() - timedelta(days=1)
    await servico.salvar(no_ar.id, {"linkedin_texto": LINKEDIN_BOM, "linkedin_em": ontem.isoformat()})

    r = await painel.resumo()
    assert "linkedin" in [p["tipo"] for p in r["proximos"]]

    await distribuicao.marcar_postado(no_ar.id)
    r = await painel.resumo()
    assert "linkedin" not in [p["tipo"] for p in r["proximos"]]


async def test_publicar_marca_a_nota_do_vault(cofre, monkeypatch):
    rel = "Pessoal/Machine Learning/Redes/Generalizacao.md"
    post = await vault.importar(rel)

    async def mergear(_post):
        return {"pr_numero": 1, "url": "https://pabloortiz.dev/blog/x"}

    monkeypatch.setattr(fluxo.publicacao, "mergear", mergear)
    await fluxo.concluir(post.id)
    assert "blog: publicado" in (cofre / rel).read_text(encoding="utf-8")


def test_datas_de_parado_usam_utc():
    agora = datetime.now(UTC)
    assert painel._dias(agora - timedelta(days=8), agora.date()) == 8


# ── 8. editar depois de publicado ─────────────────────────────────


@pytest.fixture
async def publicado():
    """Um post completo, no ar desde 2026-09-22, com a assinatura do que está no ar."""
    post = await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")
    await servico.salvar(
        post.id,
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
    await servico.mudar_estado(post.id, "pronto")
    from app.db.models.blog import BlogPost
    from app.db.session import get_session

    async with get_session() as s:
        alvo = await s.get(BlogPost, post.id)
        alvo.estado = "publicado"
        alvo.publicado_em = datetime(2026, 9, 22, 15, 0, tzinfo=UTC)
        alvo.pr_numero = 34
        await s.commit()
    return await servico.obter(post.id)


async def test_post_no_ar_nao_troca_slug_nem_data(publicado):
    with pytest.raises(servico.BlogErro, match="slug"):
        await servico.salvar(publicado.id, {"slug": "outro-endereco"})
    with pytest.raises(servico.BlogErro, match="data_publicacao"):
        await servico.salvar(publicado.id, {"data_publicacao": "2026-10-01"})
    # Mandar o mesmo valor (o autosave manda o form inteiro às vezes) não é troca.
    await servico.salvar(publicado.id, {"slug": "rag-que-diz-nao-sei"})


async def test_editar_post_no_ar_marca_alteracao_nao_publicada(publicado):
    assert not servico.alteracoes_nao_publicadas(publicado)
    depois = await servico.salvar(
        publicado.id, {"corpo": CORPO_BOM.replace("0,2 s", "0,18 s")}
    )
    assert depois.publicado_hash  # guardado antes da primeira edição
    assert servico.alteracoes_nao_publicadas(depois)
    assert servico.diagnostico(depois)["alteracoes_nao_publicadas"]


async def test_atualizacao_sem_mudanca_nao_abre_pr(publicado, monkeypatch):
    await servico.salvar(publicado.id, {"notas": "só uma nota privada"})

    async def proibido(post):
        raise AssertionError("não era para abrir PR")

    monkeypatch.setattr(fluxo.publicacao, "abrir_pr", proibido)
    with pytest.raises(servico.NaoEstaPronto, match="nada mudou"):
        await fluxo.abrir_pr(publicado.id)


async def test_atualizacao_abre_pr_com_data_de_correcao_e_sem_rascunho(publicado, monkeypatch):
    await servico.salvar(publicado.id, {"corpo": CORPO_BOM.replace("0,2 s", "0,18 s")})
    visto: dict = {}

    async def abrir(post):
        visto["mdx"] = servico.previa(post, rascunho=servico.rascunho_no_arquivo(post))
        return {"pr_numero": 40, "pr_url": "https://github.com/x/y/pull/40", "branch": "post/rag"}

    monkeypatch.setattr(fluxo.publicacao, "abrir_pr", abrir)
    await fluxo.abrir_pr(publicado.id)

    assert f"atualizado: {date.today().isoformat()}" in visto["mdx"]
    assert "data: 2026-09-22" in visto["mdx"]
    assert "draft: false" in visto["mdx"]  # o post não some do site
    post = await servico.obter(publicado.id)
    assert post.estado == "publicado"
    assert post.branch  # PR aberto


async def test_merge_da_atualizacao_mantem_a_data_e_zera_a_pendencia(publicado, monkeypatch):
    await servico.salvar(publicado.id, {"corpo": CORPO_BOM.replace("0,2 s", "0,18 s")})

    async def mergear(post):
        return {"pr_numero": 40, "url": "https://pabloortiz.dev/blog/rag-que-diz-nao-sei"}

    monkeypatch.setattr(fluxo.publicacao, "mergear", mergear)
    await fluxo.concluir(publicado.id)

    post = await servico.obter(publicado.id)
    assert post.publicado_em == datetime(2026, 9, 22, 15, 0, tzinfo=UTC)
    assert not servico.alteracoes_nao_publicadas(post)


async def test_painel_cobra_a_atualizacao_guardada(publicado, monkeypatch, tmp_path):
    monkeypatch.setattr(type(settings), "vault_dir", property(lambda self: tmp_path))
    await servico.salvar(publicado.id, {"corpo": CORPO_BOM.replace("0,2 s", "0,18 s")})
    r = await painel.resumo(hoje=date(2026, 9, 23))
    assert any("não publicada" in p["titulo"] for p in r["proximos"])


def test_commit_de_atualizacao_diz_que_atualiza(publicado):
    from app.blog import publicacao

    assunto, _ = publicacao._mensagem(publicado)
    assert assunto.startswith("post: atualiza ")


def test_pilar_de_negocio_leva_o_guia_do_dono_de_negocio():
    """Passo 8.2: a voz do dono de negócio vai por cima da voz de post, e só no pilar dele."""
    from app.blog import geracao

    tecnico = geracao._spec("ia-llms")
    negocio = geracao._spec("automacao-negocio")
    assert "Sem jargão" not in tecnico
    assert negocio.startswith(tecnico) and "Sem jargão" in negocio
