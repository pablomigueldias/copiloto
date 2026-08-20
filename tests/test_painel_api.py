"""O endpoint que a tela consome.

Duas garantias: **um request traz tudo** (senão a tela mostra números de
momentos diferentes) e **um bloco quebrado não derruba a página** — o painel é
justamente o que se olha quando alguma coisa está errada.
"""
from __future__ import annotations

import pytest

from app.candidatura import vagas
from app.fila import servico as fila
from app.llm import gateway


class SemOllama:
    """Ollama fora do ar: `disponivel()` do provider real vai falhar sozinho."""

    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("o painel não gera texto")

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def sem_llm():
    gateway.usar_provider(SemOllama())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


async def test_exige_sessao(client):
    assert (await client.get("/api/painel")).status_code == 401


async def test_traz_todos_os_blocos_num_request(logado):
    corpo = (await logado.get("/api/painel")).json()
    assert set(corpo) >= {
        "usuario", "saude", "conhecimento", "fila", "candidaturas", "modelo",
        "acoes_decididas_hoje",
    }


async def test_reflete_o_que_existe(logado):
    await fila.criar(agente="candidatura", tipo="curriculo", titulo="Currículo para a Acme",
                     texto_gerado="Texto gerado.")
    vaga = await vagas.criar(descricao="Vaga de dados com Python e SQL. " * 3)
    await vagas.registrar_evento(vaga.id, "enviada")

    corpo = (await logado.get("/api/painel")).json()
    assert corpo["fila"]["pendentes"] == 1
    assert corpo["fila"]["itens"][0]["titulo"] == "Currículo para a Acme"
    assert corpo["candidaturas"]["funil"]["enviada"] == 1


async def test_painel_vazio_nao_explode(logado):
    corpo = (await logado.get("/api/painel")).json()
    assert corpo["fila"]["pendentes"] == 0
    assert corpo["conhecimento"]["fontes"] == 0
    assert corpo["modelo"]["chamadas_24h"] == 0


async def test_bloco_quebrado_nao_derruba_a_tela(logado, monkeypatch):
    from app.api.routers import painel

    async def explode():
        raise RuntimeError("banco de conhecimento fora")

    monkeypatch.setattr(painel, "_conhecimento", explode)

    r = await logado.get("/api/painel")
    assert r.status_code == 200
    corpo = r.json()
    assert "erro" in corpo["conhecimento"]
    # O resto continua de pé — é para isso que o painel serve.
    assert "funil" in corpo["candidaturas"]


async def test_saude_diz_se_o_ollama_responde(logado):
    corpo = (await logado.get("/api/painel")).json()
    # Sem Ollama no ar na suíte, o campo existe e é falso — não some.
    assert corpo["saude"]["ollama"] in (True, False)


async def test_a_pagina_e_servida(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "Copiloto" in r.text
    assert (await client.get("/js/main.js")).status_code == 200
    assert (await client.get("/painel.css")).status_code == 200


async def test_todo_asset_do_painel_e_revalidado(client):
    """O defeito que fazia um botão novo "não funcionar".

    Primeiro tentei `?v=<mtime>` nas URLs do HTML. Funciona para um arquivo e
    não para módulos ES: `main.js` ganhava URL nova, mas os `import` dentro
    dele são strings estáticas sem versão, e o navegador servia os submódulos
    do cache. O sintoma foi `[object Object]` na tela — front velho lendo
    backend novo. Ver docs/fase06.md.

    **Este teste tem que valer para cada arquivo servido**, não só para o de
    entrada: é exatamente a diferença que deixou o buraco passar.
    """
    for caminho in ("/", "/painel.css", "/js/main.js", "/js/vagas.js", "/js/transcricao.js"):
        r = await client.get(caminho)
        assert r.status_code == 200, caminho
        assert "no-cache" in r.headers.get("cache-control", ""), caminho

    # E revalidar tem que ser barato, senão a tentação de cachear volta.
    etag = (await client.get("/js/main.js")).headers["etag"]
    r = await client.get("/js/main.js", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert not r.content


# ── `?blocos=` — desde que as candidaturas ganharam página (20/08) ─


async def test_blocos_traz_so_o_que_foi_pedido(logado):
    corpo = (await logado.get("/api/painel?blocos=saude,candidaturas")).json()

    assert "saude" in corpo and "candidaturas" in corpo
    # Cada bloco é consulta ao banco: trazer os cinco a cada 15 s para a página
    # jogar três fora é trabalho que ninguém vê.
    assert "fila" not in corpo
    assert "conhecimento" not in corpo and "modelo" not in corpo
    # O usuário vem sempre: é o rodapé das duas páginas.
    assert corpo["usuario"]["email"]


async def test_sem_o_parametro_vem_tudo(logado):
    """O contrato antigo continua valendo para quem chama de fora da tela."""
    corpo = (await logado.get("/api/painel")).json()
    assert {"saude", "conhecimento", "fila", "candidaturas", "modelo"} <= set(corpo)


async def test_bloco_desconhecido_e_422_e_diz_quais_existem(logado):
    r = await logado.get("/api/painel?blocos=saude,inventado")
    assert r.status_code == 422
    detalhe = r.json()["detail"]
    # Errar o nome do bloco é erro de quem escreve a tela: a mensagem tem que
    # dizer o que existe, senão a correção vira leitura de código.
    assert "inventado" in detalhe and "candidaturas" in detalhe


async def test_bloco_vazio_e_tratado_como_ausente(logado):
    # `?blocos=` com valor vazio é o que sai de um template mal montado.
    corpo = (await logado.get("/api/painel?blocos=")).json()
    assert "modelo" in corpo
