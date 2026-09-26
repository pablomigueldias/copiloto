"""O quadro de pendências — serviço, API e a importação do PENDENCIAS.md.

O que mais importa: `concluida_em` seguir a coluna nos dois sentidos, e
reimportar não desfazer o que eu mexi na tela.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.api.services.auth.csrf import csrf_cookie_name
from app.pendencias import importacao, servico

HOJE = date(2026, 9, 26)

MD = """\
# Pendências

### Do Pablo — por tópico (para o kanban)

> nota que não é cartão

#### 1. E-mail e domínio
- [ ] **Nome de exibição** — no webmail · agora · `fase-0/emails.md`
- [ ] **Aquecimento** — 5 por dia · até ~17/10 · `fase-0/emails.md` §2.6

#### 2. Currículo
- [ ] **Ler M01 em voz alta** · antes da 1ª reunião · `ensaio/pdf/`
- [x] **Já feito** — algo · sem data · `x.md`

### Do Claude

- [ ] **Não é do Pablo** — fora · agora · `y.md`
"""


# ── serviço ───────────────────────────────────────────────────────────


async def test_cartao_novo_vai_para_o_fim_da_coluna():
    a = await servico.criar(titulo="A", topico="T")
    b = await servico.criar(titulo="B", topico="T")
    assert (a.ordem, b.ordem) == (0, 1)
    assert a.coluna == "a_fazer" and a.concluida_em is None


async def test_concluida_em_segue_a_coluna_nos_dois_sentidos():
    p = await servico.criar(titulo="A", topico="T")
    feito = await servico.atualizar(p.id, coluna="feito")
    assert feito.concluida_em is not None
    voltou = await servico.atualizar(p.id, coluna="fazendo")
    assert voltou.concluida_em is None


async def test_mover_sem_ordem_poe_no_fim_da_coluna_de_destino():
    await servico.criar(titulo="Já fazendo", topico="T", coluna="fazendo")
    p = await servico.criar(titulo="A", topico="T")
    movido = await servico.atualizar(p.id, coluna="fazendo")
    assert movido.ordem == 1


async def test_texto_vazio_vira_nulo_e_titulo_vazio_e_recusado():
    p = await servico.criar(titulo="A", topico="T", onde="x.md")
    assert (await servico.atualizar(p.id, onde="  ")).onde is None
    with pytest.raises(servico.PendenciaErro):
        await servico.atualizar(p.id, titulo=" ")


async def test_topicos_na_ordem_em_que_apareceram():
    await servico.criar(titulo="A", topico="Zeta")
    await servico.criar(titulo="B", topico="Alfa")
    await servico.criar(titulo="C", topico="Zeta")
    assert await servico.topicos() == ["Zeta", "Alfa"]


# ── importação ────────────────────────────────────────────────────────


def test_le_so_a_secao_do_pablo_com_topico_e_campos():
    cartoes = importacao.ler(MD, hoje=HOJE)
    assert [c.titulo for c in cartoes] == [
        "Nome de exibição",
        "Aquecimento",
        "Ler M01 em voz alta",
        "Já feito",
    ]
    nome, aquecimento, m01, feito = cartoes
    assert (nome.topico, nome.descricao, nome.quando, nome.onde) == (
        "E-mail e domínio",
        "no webmail",
        "agora",
        "`fase-0/emails.md`",
    )
    assert aquecimento.prazo == date(2026, 10, 17)
    assert (m01.descricao, m01.quando) == (None, "antes da 1ª reunião")
    assert feito.feito and not nome.feito


def test_prazo_vira_o_ano_quando_a_data_ja_passou_ha_muito():
    assert importacao.prazo_de("15/01", HOJE) == date(2027, 1, 15)
    assert importacao.prazo_de("03/10", HOJE) == date(2026, 10, 3)
    assert importacao.prazo_de("antes do 1º contrato", HOJE) is None
    assert importacao.prazo_de("31/02", HOJE) is None


async def test_reimportar_nao_duplica_nem_desfaz_o_que_mudei():
    assert await importacao.importar(MD, hoje=HOJE) == (4, 0)
    nome = next(p for p in await servico.listar() if p.titulo == "Nome de exibição")
    await servico.atualizar(nome.id, coluna="fazendo")

    assert await importacao.importar(MD, hoje=HOJE) == (0, 4)
    depois = {p.titulo: p for p in await servico.listar()}
    assert len(depois) == 4
    assert depois["Nome de exibição"].coluna == "fazendo"
    assert depois["Já feito"].coluna == "feito"


# ── API ───────────────────────────────────────────────────────────────


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


def _csrf(client) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get(csrf_cookie_name())}


async def test_api_exige_login(client):
    assert (await client.get("/api/pendencias")).status_code == 401


async def test_api_cria_move_e_apaga(logado):
    r = await logado.post(
        "/api/pendencias",
        json={"titulo": "Bitwarden", "topico": "Contas", "prazo": "2026-10-03"},
        headers=_csrf(logado),
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await logado.patch(
        f"/api/pendencias/{pid}", json={"coluna": "feito"}, headers=_csrf(logado)
    )
    assert r.status_code == 200 and r.json()["concluida_em"]

    quadro = (await logado.get("/api/pendencias")).json()
    assert quadro["topicos"] == ["Contas"]
    assert quadro["itens"][0]["prazo"] == "2026-10-03"

    # prazo: null apaga; omitir não mexe
    r = await logado.patch(f"/api/pendencias/{pid}", json={"prazo": None}, headers=_csrf(logado))
    assert r.json()["prazo"] is None

    r = await logado.delete(f"/api/pendencias/{pid}", headers=_csrf(logado))
    assert r.status_code == 204
    assert (await logado.get("/api/pendencias")).json()["itens"] == []


async def test_api_recusa_coluna_inventada(logado):
    r = await logado.post(
        "/api/pendencias",
        json={"titulo": "A", "topico": "T", "coluna": "arquivado"},
        headers=_csrf(logado),
    )
    assert r.status_code == 422
