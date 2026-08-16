"""Endpoints /api/conhecimento/* — busca, inventário e remoção.

O índice guarda nota pessoal, Perfil Mestre e vaga inteira. O primeiro teste é o
que garante que nada disso responde sem sessão.
"""
from __future__ import annotations

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.conhecimento.fontes import Documento
from app.conhecimento.indexador import indexar
from app.llm import gateway

CORPO = "Anotação com corpo suficiente para o chunker tratar como seção. " * 5


class EmbedderFalso:
    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("a API de busca não gera texto")

    async def embedar(self, textos, *, modelo):
        return [[0.003 * (len(t) % 40)] * 1024 for t in textos]


@pytest.fixture
async def indexado():
    gateway.usar_provider(EmbedderFalso())
    await indexar(
        [
            Documento(
                fonte_tipo="nota",
                fonte_ref="/notas/banco.md",
                titulo="Banco",
                conteudo=f"# Banco\n\nO índice usa pgvector com HNSW. {CORPO}",
                metadados={"tags": ["infra"]},
            )
        ],
        fonte_tipo="nota",
    )
    await indexar(
        [
            Documento(
                fonte_tipo="repo",
                fonte_ref="/repo/README.md",
                titulo="Leia-me",
                conteudo=f"# Leia-me\n\nComo subir o projeto. {CORPO}",
            )
        ],
        fonte_tipo="repo",
    )
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


async def test_tudo_exige_sessao(client, indexado):
    assert (await client.get("/api/conhecimento/buscar?q=pgvector")).status_code == 401
    assert (await client.get("/api/conhecimento/fontes")).status_code == 401
    r = await client.delete("/api/conhecimento/fonte?fonte_tipo=nota&fonte_ref=/notas/banco.md")
    assert r.status_code == 401


async def test_busca_devolve_trecho_com_fonte(logado, indexado):
    r = await logado.get("/api/conhecimento/buscar", params={"q": "pgvector"})
    assert r.status_code == 200

    corpo = r.json()
    assert corpo["consulta"] == "pgvector" and corpo["total"] >= 1
    primeiro = corpo["trechos"][0]
    assert primeiro["fonte_ref"] == "/notas/banco.md"
    assert primeiro["origem"] in ("lexical", "ambas", "vetorial")
    assert primeiro["score"] > 0
    assert "pgvector" in primeiro["conteudo"]


async def test_busca_filtra_por_tipo(logado, indexado):
    r = await logado.get(
        "/api/conhecimento/buscar", params={"q": "projeto anotação", "fonte_tipo": "repo"}
    )
    assert {t["fonte_tipo"] for t in r.json()["trechos"]} <= {"repo"}


async def test_busca_recusa_tipo_invalido(logado, indexado):
    r = await logado.get(
        "/api/conhecimento/buscar", params={"q": "qualquer", "fonte_tipo": "obsidian"}
    )
    assert r.status_code == 422 and "obsidian" in r.json()["detail"]


async def test_busca_exige_consulta_com_conteudo(logado, indexado):
    assert (await logado.get("/api/conhecimento/buscar", params={"q": "a"})).status_code == 422


async def test_limite_e_respeitado(logado, indexado):
    r = await logado.get("/api/conhecimento/buscar", params={"q": "anotação", "limite": 1})
    assert len(r.json()["trechos"]) <= 1


async def test_inventario_lista_o_que_esta_indexado(logado, indexado):
    corpo = (await logado.get("/api/conhecimento/fontes")).json()
    assert corpo["total"] == 2
    assert corpo["chunks_por_tipo"].keys() == {"nota", "repo"}

    refs = {i["fonte_ref"]: i for i in corpo["itens"]}
    assert refs["/notas/banco.md"]["chunks"] >= 1
    assert refs["/notas/banco.md"]["atualizado_em"]


async def test_inventario_filtra_por_tipo(logado, indexado):
    corpo = (await logado.get("/api/conhecimento/fontes", params={"fonte_tipo": "repo"})).json()
    assert corpo["total"] == 1 and corpo["itens"][0]["fonte_tipo"] == "repo"


def _csrf(client) -> dict[str, str]:
    """Apagar é mutação: passa pelo double-submit cookie como qualquer outra."""
    return {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}


async def test_apagar_sem_csrf_e_recusado(logado, indexado):
    r = await logado.delete(
        "/api/conhecimento/fonte",
        params={"fonte_tipo": "nota", "fonte_ref": "/notas/banco.md"},
    )
    assert r.status_code == 403


async def test_apagar_fonte(logado, indexado):
    r = await logado.delete(
        "/api/conhecimento/fonte",
        params={"fonte_tipo": "nota", "fonte_ref": "/notas/banco.md"},
        headers=_csrf(logado),
    )
    assert r.status_code == 200 and r.json()["chunks_removidos"] >= 1

    corpo = (await logado.get("/api/conhecimento/fontes")).json()
    assert corpo["total"] == 1


async def test_apagar_fonte_inexistente_e_404(logado, indexado):
    r = await logado.delete(
        "/api/conhecimento/fonte",
        params={"fonte_tipo": "nota", "fonte_ref": "/nao/existe.md"},
        headers=_csrf(logado),
    )
    assert r.status_code == 404
