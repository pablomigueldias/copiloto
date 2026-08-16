"""A sessão de gravação e as rotas `/api/transcricao/*`.

Sem áudio e sem Whisper: o que se testa aqui é a **máquina de estados** e o
contrato da API. Gravar de verdade exige um dispositivo de som, e um teste que
depende de placa de áudio não roda em lugar nenhum além desta máquina.

O caminho completo (ffmpeg → Whisper → LLM → nota no vault) foi verificado à
mão com áudio real; ver docs/fase06.md.
"""
from __future__ import annotations

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.conhecimento import gravacao
from app.conhecimento import transcricao as tr


def _csrf(cliente) -> dict:
    return {"X-CSRF-Token": cliente.cookies.get(csrf_cookie_name())}


@pytest.fixture(autouse=True)
async def sessao_limpa():
    """Estado de módulo: um teste não pode herdar a sessão do anterior."""
    await gravacao.descartar()
    yield
    await gravacao.descartar()


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    return client


# ── estado ────────────────────────────────────────────────────────


async def test_comeca_ocioso(logado):
    corpo = (await logado.get("/api/transcricao/estado")).json()
    assert corpo["estado"] == "ocioso"
    assert corpo["trechos"] == []
    assert corpo["sugestao"] is None


async def test_estado_exige_sessao(client):
    assert (await client.get("/api/transcricao/estado")).status_code == 401


async def test_parar_sem_gravar_e_409(logado):
    r = await logado.post("/api/transcricao/parar", headers=_csrf(logado))
    assert r.status_code == 409


async def test_salvar_sem_transcricao_e_409(logado):
    r = await logado.post(
        "/api/transcricao/salvar",
        json={"titulo": "Qualquer coisa", "pasta": "Estudos", "tags": []},
        headers=_csrf(logado),
    )
    assert r.status_code == 409


async def test_fonte_invalida_e_422(logado):
    r = await logado.post(
        "/api/transcricao/iniciar", json={"fonte": "telepatia"}, headers=_csrf(logado)
    )
    assert r.status_code == 422


# ── destinos: o cardápio do formulário ────────────────────────────


async def test_destinos_lista_pastas_e_tags(logado, tmp_path, monkeypatch):
    (tmp_path / "Estudos" / "Python").mkdir(parents=True)
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "nota.md").write_text("---\ntags: [rag, python]\n---\n# Oi", encoding="utf-8")
    monkeypatch.setattr(gravacao, "vault", lambda: tmp_path)

    corpo = (await logado.get("/api/transcricao/destinos")).json()
    assert "Estudos/Python" in corpo["pastas"]
    assert not any(p.startswith(".") for p in corpo["pastas"])
    assert "rag" in corpo["tags"]


# ── o fim do caminho, sem áudio ───────────────────────────────────


@pytest.fixture
async def pronta_para_revisar(tmp_path, monkeypatch):
    """Coloca a sessão em `revisar` na mão, pulando ffmpeg e Whisper."""
    monkeypatch.setattr(gravacao, "vault", lambda: tmp_path)
    gravacao._sessao.estado = "revisar"
    gravacao._sessao.fonte = "sistema"
    gravacao._sessao.trechos = [
        gravacao.Trecho(indice=0, segundo=0, texto="o fast api usa paidantic pra validar")
    ]
    gravacao._sessao.nota = tr.Nota(
        fichamento=tr.Fichamento(
            titulo="FastAPI na prática", pasta="Estudos", tags=["fastapi"]
        ),
        corpo="## Conteúdo\n\nO FastAPI usa Pydantic.",
        corrigidos=["fast api → FastAPI"],
    )
    return tmp_path


async def test_estado_devolve_a_sugestao_do_modelo(logado, pronta_para_revisar):
    corpo = (await logado.get("/api/transcricao/estado")).json()
    assert corpo["estado"] == "revisar"
    s = corpo["sugestao"]
    assert s["titulo"] == "FastAPI na prática"
    assert s["nome_arquivo"] == "fastapi-na-pratica.md"
    # O que o glossário corrigiu volta para a tela: é assim que eu descubro o
    # que acrescentar em data/glossario.json.
    assert s["corrigidos"] == ["fast api → FastAPI"]


async def test_salvar_escreve_no_vault_com_o_que_eu_confirmei(logado, pronta_para_revisar):
    r = await logado.post(
        "/api/transcricao/salvar",
        json={
            "titulo": "RAG do zero",
            "pasta": "Estudos/IA",
            "tags": ["rag", "Busca Semântica"],
            "nome_arquivo": "rag-do-zero.md",
        },
        headers=_csrf(logado),
    )
    assert r.status_code == 200

    destino = pronta_para_revisar / "Estudos/IA/rag-do-zero.md"
    assert destino.exists()
    texto = destino.read_text(encoding="utf-8")
    # O título e as tags são os meus, não os do modelo.
    assert 'titulo: "RAG do zero"' in texto
    assert "tags: [rag, busca-semantica]" in texto
    assert "tipo: transcricao" in texto

    # E a sessão volta ao início, pronta para a próxima gravação.
    assert (await logado.get("/api/transcricao/estado")).json()["estado"] == "ocioso"


async def test_descartar_zera_a_sessao(logado, pronta_para_revisar):
    r = await logado.post("/api/transcricao/descartar", headers=_csrf(logado))
    assert r.status_code == 204
    assert (await logado.get("/api/transcricao/estado")).json()["estado"] == "ocioso"
    assert not list(pronta_para_revisar.rglob("*.md"))


async def test_nao_grava_duas_sessoes_ao_mesmo_tempo(logado, pronta_para_revisar):
    """A GPU é uma só e não existe caso real de gravar duas reuniões juntas."""
    r = await logado.post(
        "/api/transcricao/iniciar", json={"fonte": "sistema"}, headers=_csrf(logado)
    )
    assert r.status_code == 409
    assert "revisar" in r.json()["detail"]


# ── cortar o anúncio (fase06 §6.8) ────────────────────────────────


@pytest.fixture
async def gravando_com_anuncio():
    """Uma gravação em andamento, com um anúncio no meio."""
    gravacao._sessao.estado = "gravando"
    gravacao._sessao.trechos = [
        gravacao.Trecho(0, 0, "Hoje vamos falar de índices em PostgreSQL."),
        gravacao.Trecho(1, 20, "Mas antes, este vídeo é patrocinado pela Acme. Use o código X."),
        gravacao.Trecho(2, 40, "Voltando: um índice B-tree ordena as chaves."),
    ]


async def test_anuncio_e_marcado_e_nao_apagado(logado, gravando_com_anuncio):
    """Marcar e não apagar: 'assine o curso completo' aparece em aula sobre
    marketing, e remover sozinho perderia conteúdo real."""
    trechos = (await logado.get("/api/transcricao/estado")).json()["trechos"]
    assert [t["anuncio"] for t in trechos] == [False, True, False]
    assert len(trechos) == 3


async def test_cortar_trecho_tira_ele_da_transcricao(logado, gravando_com_anuncio):
    r = await logado.delete("/api/transcricao/trecho/1", headers=_csrf(logado))
    assert r.status_code == 200

    trechos = r.json()["trechos"]
    assert [t["indice"] for t in trechos] == [0, 2]
    assert not any("patrocinado" in t["texto"] for t in trechos)


async def test_corta_pelo_indice_e_nao_pela_posicao(logado, gravando_com_anuncio):
    """A lista cresce enquanto eu leio: clicar no ✕ do trecho 1 tem que apagar
    o trecho 1, não o que estiver na segunda posição quando o clique chegar."""
    await logado.delete("/api/transcricao/trecho/0", headers=_csrf(logado))
    r = await logado.delete("/api/transcricao/trecho/2", headers=_csrf(logado))
    assert [t["indice"] for t in r.json()["trechos"]] == [1]


async def test_cortar_trecho_inexistente_e_409(logado, gravando_com_anuncio):
    r = await logado.delete("/api/transcricao/trecho/99", headers=_csrf(logado))
    assert r.status_code == 409


async def test_trecho_traz_o_relogio_do_video(logado, gravando_com_anuncio):
    trechos = (await logado.get("/api/transcricao/estado")).json()["trechos"]
    assert [t["relogio"] for t in trechos] == ["00:00", "00:20", "00:40"]


async def test_duracao_para_de_contar_quando_a_captura_para(logado, monkeypatch):
    """26 min de aula viravam `duracao_min: 30`: o cronometro seguia correndo
    durante o `processando`, e o tempo do LLM entrava na duracao do video."""
    import time

    gravacao._sessao.estado = "gravando"
    gravacao._sessao.comecou_em = time.monotonic() - 600      # 10 min gravados
    gravacao._sessao.parou_em = time.monotonic() - 120        # parou ha 2 min
    gravacao._sessao.estado = "processando"

    segundos = (await logado.get("/api/transcricao/estado")).json()["segundos"]
    assert 470 < segundos < 490, f"esperava ~480 s (8 min de captura), veio {segundos}"
