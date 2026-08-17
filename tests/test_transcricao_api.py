"""A sessão de gravação e as rotas `/api/transcricao/*`.

Sem áudio e sem Whisper: o que se testa aqui é a **máquina de estados** e o
contrato da API. Gravar de verdade exige um dispositivo de som, e um teste que
depende de placa de áudio não roda em lugar nenhum além desta máquina.

O caminho completo (ffmpeg → Whisper → LLM → nota no vault) foi verificado à
mão com áudio real; ver docs/fase06.md.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.conhecimento import gravacao
from app.conhecimento import transcricao as tr
from app.llm import gateway
from app.llm.tipos import RespostaCrua


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


# ── a reescrita durante a aula (fase-transcricao §P1) ─────────────


class LLMContado:
    """Provider falso que **conta as chamadas** e diagrama o trecho que recebeu.

    A contagem é o teste do §P1. O resultado da nota não mudou; o que mudou é
    quantas chamadas sobram para depois do `parar` — era 6 blocos + fichamento
    (3 min 30 de tela muda), tem que virar 1 bloco + fichamento.
    """

    nome = "falso"

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.chamadas.append("json" if json_mode else "texto")
        if json_mode:
            return RespostaCrua(
                texto='{"titulo": "Aula de teste", "resumo": "r", "tags": ["logica"]}',
                modelo=modelo,
            )
        # Devolver o trecho pontuado é o que um modelo que diagrama faz — e é o
        # que passa pelo guarda de tamanho de `reescrever_um`.
        trecho = prompt.split("TRECHO:")[-1].split("TEXTO REESCRITO:")[0].strip()
        return RespostaCrua(texto=trecho.replace("palavra", "Palavra."), modelo=modelo)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture
async def ao_vivo(monkeypatch, tmp_path):
    """Uma gravação em andamento com a reescrita ao vivo ligada, e sem áudio.

    Pula o `ffmpeg` e o Whisper de propósito: o que se testa aqui é **quando** o
    LLM é chamado, e isso não depende de placa de som.
    """
    provider = LLMContado()
    gateway.usar_provider(provider)
    monkeypatch.setattr(gravacao, "vault", lambda: tmp_path)
    # Glossário vazio: esta seção mede o momento da reescrita, não a correção.
    monkeypatch.setattr(tr, "carregar_glossario", lambda *a, **k: {})

    s = gravacao._sessao
    s.__init__()
    s.estado = "gravando"
    s.etapa = "transcrevendo"
    s.comecou_em = time.monotonic()
    s.fila = asyncio.Queue()
    s.tarefa_llm = asyncio.create_task(gravacao._reescrever_ao_vivo(s))

    yield s, provider

    gateway.usar_provider(gateway.OllamaProvider())


def _falar(sessao, quantos: int, *, palavras: int = 100) -> None:
    """`quantos` pedaços de 20 s chegando do Whisper, como no laço real."""
    base = len(sessao.trechos)
    for i in range(base, base + quantos):
        sessao.trechos.append(
            gravacao.Trecho(indice=i, segundo=i * 20, texto=" ".join(["palavra"] * palavras))
        )


async def _ate(condicao, prazo: float = 20.0) -> None:
    """Espera a tarefa de reescrita avançar — ela roda fora deste `await`."""
    limite = time.monotonic() + prazo
    while time.monotonic() < limite:
        if condicao():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("a reescrita ao vivo não avançou no prazo")


async def test_bloco_fechado_e_reescrito_com_o_video_rodando(ao_vivo):
    """O passo que vale a fase: a GPU trabalha no minuto 5, não depois do parar."""
    s, provider = ao_vivo
    _falar(s, 6)                                  # 600 palavras = um bloco cheio
    await gravacao._fechar_bloco_se_cheio(s)
    await _ate(lambda: len(s.blocos) == 1)

    assert s.estado == "gravando", "a captura tem que continuar durante a reescrita"
    assert provider.chamadas == ["texto"]
    assert s.blocos[0][0] == 0                    # o bloco começa aos 00:00
    # Os pedaços que entraram no bloco ficam marcados — é o que trava o ✕.
    assert all(t.processado for t in s.trechos)


async def test_meio_bloco_espera_o_resto_da_aula(ao_vivo):
    """Bloco pela metade não vai para o LLM: 300 palavras viram um subtítulo solto."""
    s, provider = ao_vivo
    _falar(s, 3)
    await gravacao._fechar_bloco_se_cheio(s)
    await asyncio.sleep(0.2)

    assert s.blocos == []
    assert provider.chamadas == []
    assert not any(t.processado for t in s.trechos)


async def test_depois_do_parar_sobra_um_bloco_e_o_fichamento(ao_vivo):
    """A medida da fase: 6 reescritas + fichamento depois do parar viram 2 chamadas."""
    s, provider = ao_vivo
    for _ in range(3):                            # três blocos durante a aula
        _falar(s, 6)
        await gravacao._fechar_bloco_se_cheio(s)
    await _ate(lambda: len(s.blocos) == 3)
    _falar(s, 2)                                  # e um resto que não fechou

    durante_a_aula = len(provider.chamadas)
    s.estado = "processando"
    s.etapa = "reescrevendo"
    await gravacao._organizar(s)

    assert durante_a_aula == 3
    assert provider.chamadas[durante_a_aula:] == ["texto", "json"]
    assert s.erro is None, f"o caminho caiu no fallback: {s.erro}"
    assert s.estado == "revisar"
    assert s.etapa is None
    assert len(s.blocos) == 4
    # E a nota continua carimbada com o instante de cada bloco.
    assert "`⏱ 02:00`" in s.nota.corpo
    assert s.nota.fichamento.titulo == "Aula de teste"


async def test_nao_corta_trecho_que_ja_virou_bloco(logado, ao_vivo):
    """Desabilitar, e não reprocessar: o ✕ é para o anúncio, que eu vejo em 20 s.

    Cortar depois da reescrita obrigaria a pagar o bloco de novo — e o bloco
    reescrito ficaria contendo um trecho que já não existe.
    """
    s, _ = ao_vivo
    _falar(s, 6)
    await gravacao._fechar_bloco_se_cheio(s)
    await _ate(lambda: len(s.blocos) == 1)

    r = await logado.delete("/api/transcricao/trecho/0", headers=_csrf(logado))
    assert r.status_code == 409
    assert "já foi organizado" in r.json()["detail"]

    # E a tela sabe disso antes de eu clicar.
    trechos = (await logado.get("/api/transcricao/estado")).json()["trechos"]
    assert all(t["processado"] for t in trechos)


async def test_trecho_ainda_pendente_continua_cortavel(logado, ao_vivo):
    """O ✕ não pode endurecer para o trecho que ainda está na fila de acumular."""
    s, _ = ao_vivo
    _falar(s, 6)
    await gravacao._fechar_bloco_se_cheio(s)
    await _ate(lambda: len(s.blocos) == 1)
    _falar(s, 1)                                  # o pedaço 6, ainda solto

    r = await logado.delete("/api/transcricao/trecho/6", headers=_csrf(logado))
    assert r.status_code == 200
    assert [t["indice"] for t in r.json()["trechos"]] == [0, 1, 2, 3, 4, 5]


async def test_reescrita_nao_sobrevive_ao_fim_da_sessao(ao_vivo):
    """A tarefa da reescrita espera na fila para sempre — e o reset é na mesma
    instância de `Sessao`, então uma tarefa esquecida acordaria depois e
    escreveria bloco na **gravação seguinte**.

    O caminho que expõe isso é o `parar` que não achou texto: o `_organizar`, que
    é quem põe a sentinela na fila, nunca roda.
    """
    s, _ = ao_vivo
    tarefa = s.tarefa_llm

    await gravacao.descartar()
    await asyncio.sleep(0)

    assert tarefa.cancelled() or tarefa.done()
    assert s.estado == "ocioso"


# ── o progresso na tela (fase-transcricao §U1) ────────────────────


async def test_estado_diz_em_que_bloco_esta(logado, ao_vivo):
    """Três minutos de "organizando…" é onde eu penso que travou."""
    s, _ = ao_vivo
    _falar(s, 6)
    await gravacao._fechar_bloco_se_cheio(s)
    await _ate(lambda: len(s.blocos) == 1)
    _falar(s, 2)                                  # o bloco 2 começou a acumular

    corpo = (await logado.get("/api/transcricao/estado")).json()
    assert corpo["etapa"] == "transcrevendo"
    assert (corpo["bloco"], corpo["blocos"]) == (1, 2)


async def test_ocioso_nao_finge_progresso(logado):
    corpo = (await logado.get("/api/transcricao/estado")).json()
    assert corpo["etapa"] is None
    assert (corpo["bloco"], corpo["blocos"]) == (0, 0)


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
