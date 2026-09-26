"""Pesquisador (Fase 1, passo 3): a ficha da clínica, com fonte.

O site da clínica é falso (httpx.MockTransport) e a IA também. O que precisa ser
verdade: cada fato aponta para a página de onde veio, a IA não põe nada sem
fonte, e o e-mail só vira destinatário se a clínica o publica.
"""
from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.comercial.crm import leads, pesquisador, varredura
from app.comercial.prospeccao import retencao
from app.db.models.comercial.crm import Interacao, Lead, OrigemLead, Tarefa
from app.db.models.comercial.prospeccao import MotivoSupressao, TipoSupressao
from app.db.session import get_session
from app.llm import gateway
from app.llm.tipos import RespostaCrua

HOJE = date(2026, 12, 1)

HOME = """<html><body>
<h1>Clínica Aurora de Psicologia</h1>
<p>Psicoterapia para adultos e casais, presencial e online. Agende pelo WhatsApp.</p>
<a href="/contato">Fale conosco</a> <a href="/equipe">Nossa equipe</a>
<a href="/blog/artigo">Blog</a> <a href="https://outro-site.com/contato">parceiro</a>
<a href="https://wa.me/5511912345678">WhatsApp</a>
<img src="logo@2x.png">
</body></html>"""
CONTATO = """<html><body>E-mail: <a href="mailto:contato@clinicaaurora.com.br">contato@clinicaaurora.com.br</a>
Site feito por dev@agencia.com</body></html>"""
EQUIPE = """<html><body>Ana, CRP 06/123456. Bruno — CRP 06/654321. Ana de novo: CRP 06/123456.</body></html>"""


def _site(robots: str = "", fora: bool = False) -> httpx.AsyncClient:
    def resposta(req: httpx.Request) -> httpx.Response:
        if fora:
            return httpx.Response(503)
        html = {"/": HOME, "/contato": CONTATO, "/equipe": EQUIPE}.get(req.url.path)
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    return httpx.AsyncClient(transport=httpx.MockTransport(resposta))


class IA:
    nome = "falso"

    def __init__(self, resposta: dict | str) -> None:
        self.resposta = resposta if isinstance(resposta, str) else json.dumps(resposta)
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        return RespostaCrua(texto=self.resposta, modelo=modelo)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


class SemNavegador(varredura.Navegador):
    """Nos testes de unidade, nada de Chromium: o que o httpx leu é o que vale."""

    async def html(self, url):
        return None


@pytest.fixture(autouse=True)
def sem_chromium(monkeypatch):
    monkeypatch.setattr(varredura, "Navegador", SemNavegador)
    monkeypatch.setattr(varredura, "INTERVALO_S", 0)


@pytest.fixture(autouse=True)
def restaura():
    yield
    gateway.usar_provider(None)


async def _lead(s, email="contato@clinicaaurora.com.br"):
    return await leads.criar(s, origem=OrigemLead.PROSPECCAO, nome="Clínica Aurora", email=email)


def test_site_provavel_so_para_dominio_proprio():
    assert pesquisador.site_provavel("contato@clinicaaurora.com.br") == "https://clinicaaurora.com.br"
    assert pesquisador.site_provavel("fulana@gmail.com") is None
    assert pesquisador.site_provavel(None) is None


async def test_extrai_fatos_com_a_pagina_de_onde_vieram():
    async with _site() as c:
        v = await varredura.varrer(
            "clinicaaurora.com.br", lambda p: False, cliente=c, navegador=SemNavegador(), intervalo_s=0
        )
    urls = [u for u, _ in v.paginas]
    assert urls[0] == "https://clinicaaurora.com.br"
    assert set(urls[1:]) == {"https://clinicaaurora.com.br/contato", "https://clinicaaurora.com.br/equipe"}
    ficha = pesquisador.extrair("clinicaaurora.com.br", v.paginas)
    emails = {f.valor: f.fonte for f in ficha.emails}
    assert emails["contato@clinicaaurora.com.br"].endswith("/contato")
    assert "logo@2x.png" not in emails
    assert ficha.whatsapp.valor == "5511912345678"
    assert ficha.agendamento_online.valor == "agende"
    assert ficha.psicologos_crp.valor == 2  # CRP repetido conta uma vez


async def test_robots_txt_e_respeitado():
    async with _site(robots="User-agent: *\nDisallow: /equipe") as c:
        v = await varredura.varrer(
            "clinicaaurora.com.br", lambda p: False, cliente=c, navegador=SemNavegador(), intervalo_s=0
        )
    assert not any(u.endswith("/equipe") for u, _ in v.paginas)


async def test_ia_sem_fonte_lida_nao_entra():
    gateway.usar_provider(IA({"o_que_faz": "terapia", "gancho": "x", "fonte": "https://inventado.com"}))
    async with get_session() as s, _site() as c:
        lead = await _lead(s)
        r = await pesquisador.pesquisar(s, lead.id, cliente=c, hoje=HOJE)
    assert r.ficha.o_que_faz is None and r.ficha.gancho is None


async def test_email_da_base_publicado_no_site_vira_destinatario():
    gateway.usar_provider(IA({
        "o_que_faz": "psicoterapia para adultos e casais",
        "gancho": "o site manda agendar pelo WhatsApp",
        "fonte": "https://clinicaaurora.com.br/",
    }))
    async with get_session() as s, _site() as c:
        lead = await _lead(s)
        s.add(Tarefa(lead_id=lead.id, tipo="pesquisar", vence_em=HOJE))
        await s.commit()
        r = await pesquisador.pesquisar(s, lead.id, cliente=c, hoje=HOJE)
        assert r.status == "ok" and r.email_confirmado
        # a IA citou a home com barra no fim; a fonte é a URL como foi lida
        assert r.ficha.gancho.fonte == "https://clinicaaurora.com.br"
        lead = await s.get(Lead, lead.id, populate_existing=True)
        assert lead.email_fonte.endswith("/contato") and lead.pesquisado_em
        tarefas = {(t.tipo, t.feita_em is not None) for t in await s.scalars(select(Tarefa))}
        assert tarefas == {("pesquisar", True), ("escrever_email", False)}
        ficha = await s.scalar(select(Interacao).where(Interacao.tipo == "ficha"))
        assert ficha.dados["emails"][0]["fonte"].endswith("/contato")
        assert "confirmado no site" in ficha.texto


async def test_email_da_base_que_o_site_nao_mostra_troca_pelo_do_site():
    gateway.usar_provider(IA({"o_que_faz": "", "gancho": "", "fonte": ""}))
    async with get_session() as s, _site() as c:
        lead = await _lead(s, email="antigo@clinicaaurora.com.br")
        r = await pesquisador.pesquisar(s, lead.id, cliente=c, hoje=HOJE)
        lead = await s.get(Lead, lead.id, populate_existing=True)
    # o da própria clínica, e não o da agência que fez o site
    assert r.email_confirmado and lead.email == "contato@clinicaaurora.com.br"


async def test_email_suprimido_no_site_nao_volta():
    gateway.usar_provider(IA({"o_que_faz": "", "gancho": "", "fonte": ""}))
    async with get_session() as s, _site() as c:
        lead = await _lead(s, email="antigo@clinicaaurora.com.br")
        await retencao.suprimir(s, TipoSupressao.EMAIL, "contato@clinicaaurora.com.br", MotivoSupressao.OPTOUT)
        await pesquisador.pesquisar(s, lead.id, cliente=c, hoje=HOJE)
        lead = await s.get(Lead, lead.id, populate_existing=True)
    # o único outro e-mail é o da agência: não é da clínica, mas não está
    # suprimido. Ele fica em segundo lugar e só entra porque não há outro.
    assert lead.email == "dev@agencia.com"


async def test_sem_site_e_site_fora():
    async with get_session() as s:
        lead = await _lead(s, email="fulana@gmail.com")
        r = await pesquisador.pesquisar(s, lead.id, hoje=HOJE)
        assert r.status == "sem_site"
        async with _site(fora=True) as c:
            r = await pesquisador.pesquisar(s, lead.id, site="clinicaaurora.com.br", cliente=c, hoje=HOJE)
        assert r.status == "site_fora"
        lead = await s.get(Lead, lead.id, populate_existing=True)
        assert lead.email_fonte is None


class IAFora(IA):
    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        from app.llm.tipos import LLMIndisponivel

        raise LLMIndisponivel("fora do ar")


async def test_ia_fora_do_ar_nao_derruba_a_ficha():
    gateway.usar_provider(IAFora("{}"))
    async with get_session() as s, _site() as c:
        lead = await _lead(s)
        r = await pesquisador.pesquisar(s, lead.id, cliente=c, hoje=HOJE)
    assert r.status == "ok" and r.email_confirmado
    assert r.ficha.psicologos_crp.valor == 2 and r.ficha.o_que_faz is None


# ── API ───────────────────────────────────────────────────────────────


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


async def test_api_lista_detalha_e_pesquisa_sem_site(logado):
    from app.api.services.auth.csrf import csrf_cookie_name

    async with get_session() as s:
        lead = await _lead(s, email="fulana@gmail.com")
    lista = (await logado.get("/api/comercial/leads")).json()
    assert [l_["nome"] for l_ in lista] == ["Clínica Aurora"] and lista[0]["email_confirmado"] is False
    det = (await logado.get(f"/api/comercial/leads/{lead.id}")).json()
    assert det["interacoes"] == [] and det["estagio"] == "prospect"
    csrf = {"X-CSRF-Token": logado.cookies.get(csrf_cookie_name())}
    r = await logado.post(f"/api/comercial/leads/{lead.id}/pesquisar", json={}, headers=csrf)
    assert r.status_code == 200 and r.json()["status"] == "sem_site"
    assert "sem site" in r.json()["lead"]["proxima_acao"]
    assert (await logado.get("/api/comercial/leads/999999")).status_code == 404


async def test_site_do_contador_nao_confirma_o_email():
    """A H18 de verdade: o e-mail da base leva ao site do contador, que o publica."""
    contador = """<html><body><h1>Eretz Contabilidade</h1>Abertura de empresas, imposto de renda.
    <a href="mailto:contato@eretz.test">contato@eretz.test</a> Agende uma conversa.</body></html>"""

    def resposta(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/":
            return httpx.Response(200, text=contador, headers={"content-type": "text/html"})
        return httpx.Response(404)

    ia = IA({"o_que_faz": "x", "gancho": "y", "fonte": "https://eretz.test/"})
    gateway.usar_provider(ia)
    async with get_session() as s, httpx.AsyncClient(transport=httpx.MockTransport(resposta)) as c:
        lead = await _lead(s, email="contato@eretz.test")
        r = await pesquisador.pesquisar(s, lead.id, cliente=c, hoje=HOJE)
        lead = await s.get(Lead, lead.id, populate_existing=True)
    assert r.status == "nao_e_da_clinica" and not r.email_confirmado
    assert lead.email_fonte is None and lead.site is None
    assert "não parece ser da clínica" in lead.proxima_acao
    assert ia.prompts == []  # nem gasta IA com site que não é da clínica
