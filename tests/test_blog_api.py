"""Endpoints da redação — /api/blog/*.

Dois testes carregam o peso aqui:

- o **409 do `pronto`**: o portão das camadas tem de valer pela API também, ou
  o botão do painel vira um jeito de burlar a régua;
- o **PATCH parcial**: salvar só o corpo não pode apagar a descrição. É o bug
  clássico de editor com autosave, e ele só aparece depois, quando o campo já
  sumiu sem ninguém ver.
"""
from __future__ import annotations

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.blog import servico

DESCRICAO = (
    "Busca vetorial nunca volta vazia. Como um corte de distância fez meu RAG "
    "recusar em 0,2 s."
)


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


@pytest.fixture
async def post():
    return await servico.criar(titulo="Um RAG que sabe dizer não sei", pilar="ia-llms")


def _csrf(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}


async def test_sem_cookie_e_401(client):
    assert (await client.get("/api/blog")).status_code == 401


async def test_listar_traz_a_contagem_por_estado(logado, post):
    r = await logado.get("/api/blog")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == 1
    assert corpo["por_estado"]["pauta"] == 1
    # A lista não carrega o corpo de 40 posts para desenhar 40 cards.
    assert "corpo" not in corpo["itens"][0]


async def test_criar_pauta(logado):
    r = await logado.post(
        "/api/blog",
        json={"titulo": "Veio do vault", "origem": [{"vault": "Machine Learning/nota.md"}]},
        headers=_csrf(logado),
    )
    assert r.status_code == 201
    assert r.json()["estado"] == "pauta"


async def test_detalhe_traz_o_diagnostico(logado, post):
    r = await logado.get(f"/api/blog/{post.id}")
    assert r.status_code == 200
    d = r.json()["diagnostico"]
    assert len(d["camadas"]) == 5
    assert {c["publico"] for c in d["camadas"]} == {
        "entusiasta",
        "cliente",
        "tecnico",
        "recrutador",
        "todos",
    }
    assert d["exportavel"] is False
    # Sinal vermelho vem com a dica: a regra mora no sistema, não na minha cabeça.
    vermelhos = [s for c in d["camadas"] for s in c["sinais"] if not s["ok"]]
    assert vermelhos and all(s["dica"] for s in vermelhos)


async def test_patch_parcial_nao_apaga_o_resto(logado, post):
    await logado.patch(
        f"/api/blog/{post.id}", json={"descricao": DESCRICAO}, headers=_csrf(logado)
    )
    r = await logado.patch(
        f"/api/blog/{post.id}", json={"corpo": "primeiro parágrafo"}, headers=_csrf(logado)
    )
    assert r.status_code == 200
    assert r.json()["descricao"] == DESCRICAO


async def test_patch_vazio_e_422(logado, post):
    r = await logado.patch(f"/api/blog/{post.id}", json={}, headers=_csrf(logado))
    assert r.status_code == 422


async def test_marcar_pronto_sem_estar_pronto_e_409(logado, post):
    r = await logado.post(
        f"/api/blog/{post.id}/estado", json={"estado": "pronto"}, headers=_csrf(logado)
    )
    assert r.status_code == 409
    assert r.json()["detail"]  # diz o que falta


async def test_previa_devolve_o_mdx(logado, post):
    r = await logado.get(f"/api/blog/{post.id}/previa")
    assert r.status_code == 200
    assert r.json()["mdx"].startswith("---\n")


async def test_versoes_em_ordem_decrescente(logado, post):
    for texto in ("um", "dois", "três"):
        await logado.patch(
            f"/api/blog/{post.id}", json={"corpo": texto}, headers=_csrf(logado)
        )
    r = await logado.get(f"/api/blog/{post.id}/versoes")
    assert [v["numero"] for v in r.json()] == [3, 2, 1]


async def test_post_inexistente_e_404(logado):
    r = await logado.get("/api/blog/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_vocabulario_traz_a_taxonomia_do_blog(logado):
    r = await logado.get("/api/blog/vocabulario")
    assert r.status_code == 200
    v = r.json()
    assert v["pilares"] == ["ia-llms", "dados-ml", "automacao-negocio"]
    assert "rag" in v["tags"]
    assert v["tags_max"] == 5


async def test_publicar_exige_pr_aberto(logado, post):
    """A regra da fila continua: o sistema prepara, eu executo.

    O que mudou foi onde o clique acontece — antes era eu no terminal, agora é
    um botão. O que **não** mudou: publicar é uma rota própria, separada da que
    abre o PR, e ela recusa quando não há o que mergear.
    """
    r = await logado.post(f"/api/blog/{post.id}/publicar", headers=_csrf(logado))
    assert r.status_code == 422
    assert "não tem PR" in r.json()["detail"]


async def test_abrir_pr_de_post_que_nao_esta_pronto_e_409(logado, post):
    r = await logado.post(f"/api/blog/{post.id}/pr", headers=_csrf(logado))
    assert r.status_code == 409
    assert "pronto" in r.json()["detail"]


async def test_situacao_do_pr_de_post_sem_pr(logado, post):
    r = await logado.get(f"/api/blog/{post.id}/pr")
    assert r.status_code == 200
    assert r.json()["existe"] is False
