"""Redator (Fase 1, passo 4): o e-mail 1 e o lembrete, pela fila.

A IA é falsa. O que precisa ser verdade: a IA só escreve a abertura, e com
fonte; o verificador barra frase proibida, jargão, preço e texto sem opt-out
antes da fila; nada sai sem aprovação; e depois do lembrete, nada.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import select

from app.comercial.crm import calendario, leads, redator
from app.comercial.prospeccao import retencao
from app.db.models.acao_pendente import AcaoPendente
from app.db.models.comercial.crm import Interacao, Lead, OrigemLead, Tarefa
from app.db.models.comercial.prospeccao import MotivoSupressao, TipoSupressao
from app.db.session import get_session
from app.fila import servico as fila
from app.llm import gateway
from app.llm.tipos import LLMIndisponivel, RespostaCrua

HOJE = date(2026, 12, 1)
SITE = "https://clinicaaurora.com.br"
FICHA = {
    "site": SITE,
    "paginas": [SITE, f"{SITE}/contato", f"{SITE}/equipe"],
    "emails": [{"valor": "contato@clinicaaurora.com.br", "fonte": f"{SITE}/contato"}],
    "whatsapp": {"valor": "5511912345678", "fonte": SITE},
    "agendamento_online": {"valor": "agende", "fonte": SITE},
    "psicologos_crp": {"valor": 2, "fonte": f"{SITE}/equipe"},
    "o_que_faz": {"valor": "psicoterapia para adultos e casais", "fonte": SITE},
    "gancho": {"valor": "o site manda marcar pelo WhatsApp", "fonte": SITE},
}
BOA = {"abertura": "Vi que vocês atendem adultos e casais e que a marcação é pelo WhatsApp.", "fonte": f"{SITE}/"}


class IA:
    nome = "falso"

    def __init__(self, *respostas: dict) -> None:
        self.respostas = [json.dumps(r) for r in respostas]
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        texto = self.respostas[min(len(self.prompts), len(self.respostas)) - 1]
        return RespostaCrua(texto=texto, modelo=modelo)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


class IAFora(IA):
    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise LLMIndisponivel("fora do ar")


@pytest.fixture(autouse=True)
def restaura():
    yield
    gateway.usar_provider(None)


async def _lead(s, *, confirmado=True, ficha=FICHA) -> Lead:
    lead = await leads.criar(
        s, origem=OrigemLead.PROSPECCAO, nome="CLINICA AURORA DE PSICOLOGIA LTDA",
        email="contato@clinicaaurora.com.br",
    )
    if confirmado:
        lead.email_fonte = f"{SITE}/contato"
    if ficha:
        s.add(Interacao(lead_id=lead.id, canal="nota", direcao="interna", tipo="ficha", texto="ficha", dados=ficha))
    s.add(Tarefa(lead_id=lead.id, tipo="escrever_email", vence_em=HOJE))
    await s.commit()
    return lead


async def _acao(acao_id) -> AcaoPendente:
    return await fila.obter(acao_id)


# ── o texto e a régua ────────────────────────────────────────────────


def test_nome_da_clinica_e_saudacao():
    assert redator.nome_da_clinica("CLINICA AURORA DE PSICOLOGIA LTDA") == "Clinica Aurora de Psicologia"
    assert redator.nome_da_clinica("Espaço Viver - ME") == "Espaço Viver"

    class L:
        contato_nome = None
        nome = "INSTITUTO VIVER S/S"

    assert redator.saudacao(L()) == "Oi, pessoal do Instituto Viver."
    L.contato_nome = "Marina Souza"
    assert redator.saudacao(L()) == "Oi, Marina."


def test_origem_do_contato_sem_link():
    assert redator.origem(f"{SITE}/contato") == "Achei este e-mail na página de contato do site de vocês."
    assert redator.origem(SITE) == "Achei este e-mail na página inicial do site de vocês."
    assert "clinicaaurora" not in redator.origem(f"{SITE}/equipe")


def test_o_modelo_passa_e_o_verificador_barra_o_resto():
    class L:
        nome, contato_nome, email_fonte = "Clínica Aurora", None, f"{SITE}/contato"

    bom = redator.montar_email(L(), BOA["abertura"])
    assert redator.verificar(bom) == []
    assert redator.verificar(redator.montar_lembrete(L(), redator.ASSUNTO, HOJE)) == []

    def com(trecho, tirar=None):
        texto = bom.replace(tirar, "") if tirar else bom
        return " | ".join(redator.verificar(texto.replace("Eu monto", f"{trecho} Eu monto")))

    assert "abertura de robô" in com("Espero que esteja bem.")
    assert "jargão" in com("Nosso chatbot qualifica o lead.")
    assert "jargão" in com("A IA responde.")
    assert "preço" in com("Custa R$ 300 por mês.")
    assert "promessa" in com("Garanto 30% mais consultas.")
    assert "links" in com("Veja https://exemplo.com.br.")
    assert "opt-out" in com("", tirar=redator.OPT_OUT)
    assert "de onde tirei" in com("", tirar="Achei este e-mail na página de contato do site de vocês.")


def test_abertura_reprovada():
    assert redator.verificar_abertura(BOA["abertura"]) == []
    assert redator.verificar_abertura("Sou o Pablo e vi o site de vocês.")
    assert redator.verificar_abertura("Vocês respondem o WhatsApp à noite?")
    assert redator.verificar_abertura("Vi que vocês usam um chatbot no site.")
    assert redator.verificar_abertura("Espero que estejam bem.")
    assert redator.verificar_abertura("Parabéns pelo trabalho com casais.")


def test_dia_util():
    assert calendario.pascoa(2027) == date(2027, 3, 28)
    assert not calendario.dia_util(date(2026, 11, 20))  # Consciência Negra
    assert not calendario.dia_util(date(2027, 2, 9))  # terça de Carnaval
    # quarta 18/11 + 5 dias úteis, pulando o feriado de sexta 20/11
    assert calendario.somar_dias_uteis(date(2026, 11, 18), 5) == date(2026, 11, 26)


# ── o fluxo ──────────────────────────────────────────────────────────


async def test_escreve_com_a_abertura_da_ia_e_poe_na_fila():
    ia = IA(BOA)
    gateway.usar_provider(ia)
    async with get_session() as s:
        lead = await _lead(s)
        r = await redator.escrever(s, lead.id, hoje=HOJE)
        tarefas = {(t.tipo, t.feita_em is not None) for t in await s.scalars(select(Tarefa))}
        lead = await s.get(Lead, lead.id, populate_existing=True)
    acao = await _acao(r.acao_id)
    assert acao.status == "pendente" and acao.agente == "redator_comercial" and acao.tipo == "email_frio"
    assert BOA["abertura"] in acao.texto_gerado
    assert acao.texto_gerado.startswith(f"Assunto: {redator.ASSUNTO}")
    assert acao.payload["para"] == "contato@clinicaaurora.com.br" and acao.payload["abertura_fonte"] == SITE
    assert r.avisos == []
    assert tarefas == {("escrever_email", True), ("enviar_email", False)}
    assert "aprovar o e-mail 1" in lead.proxima_acao
    # a IA só viu fatos com a página de onde vieram
    assert f"[{SITE}/equipe]" in ia.prompts[0]


async def test_abertura_ruim_duas_vezes_cai_para_os_fatos():
    ruim = {"abertura": "Espero que estejam bem! Parabéns pelo trabalho.", "fonte": SITE}
    inventada = {"abertura": BOA["abertura"], "fonte": "https://outro-site.com"}
    ia = IA(ruim, inventada)
    gateway.usar_provider(ia)
    async with get_session() as s:
        lead = await _lead(s)
        r = await redator.escrever(s, lead.id, hoje=HOJE)
    acao = await _acao(r.acao_id)
    assert len(ia.prompts) == 2 and "reprovada" in ia.prompts[1]
    assert "chamar no WhatsApp ou marcar online" in acao.texto_gerado
    assert "Parabéns" not in acao.texto_gerado
    assert any("duas vezes" in a for a in r.avisos) and acao.payload["abertura_fonte"] is None


async def test_ia_fora_do_ar_nao_para_o_redator():
    gateway.usar_provider(IAFora())
    async with get_session() as s:
        lead = await _lead(s)
        r = await redator.escrever(s, lead.id, hoje=HOJE)
    assert "chamar no WhatsApp" in (await _acao(r.acao_id)).texto_gerado
    assert any("indisponível" in a for a in r.avisos)


async def test_nao_escreve_sem_email_confirmado_suprimido_ou_repetido():
    gateway.usar_provider(IA(BOA))
    async with get_session() as s:
        sem = await _lead(s, confirmado=False)
        with pytest.raises(redator.NaoPode, match="confirmado"):
            await redator.escrever(s, sem.id, hoje=HOJE)

        lead = await _lead(s)
        await redator.escrever(s, lead.id, hoje=HOJE)
        with pytest.raises(redator.NaoPode, match="na fila"):
            await redator.escrever(s, lead.id, hoje=HOJE)
        with pytest.raises(redator.NaoPode, match="depois do e-mail 1"):
            await redator.escrever(s, lead.id, tipo=redator.LEMBRETE, hoje=HOJE)

        await retencao.suprimir(s, TipoSupressao.EMAIL, "contato@clinicaaurora.com.br", MotivoSupressao.OPTOUT)
        with pytest.raises(redator.NaoPode, match="supressão"):
            await redator.escrever(s, lead.id, hoje=HOJE)


async def test_rejeitado_pode_ser_escrito_de_novo():
    gateway.usar_provider(IA(BOA))
    async with get_session() as s:
        lead = await _lead(s)
        r = await redator.escrever(s, lead.id, hoje=HOJE)
        await fila.decidir(r.acao_id, decisao="rejeitar", motivo="abertura fraca")
        with pytest.raises(redator.NaoPode, match="aprovado"):
            await redator.enviei(s, lead.id, r.acao_id, hoje=HOJE)
        await redator.escrever(s, lead.id, hoje=HOJE)
        lista = await redator.rascunhos(s, lead.id)
    assert [x.status for x in lista] == ["rejeitada", "pendente"] and lista[0].motivo == "abertura fraca"


async def test_do_email_1_ao_lembrete_e_depois_nada():
    gateway.usar_provider(IA(BOA))
    async with get_session() as s:
        lead = await _lead(s)
        r = await redator.escrever(s, lead.id, hoje=HOJE)
        acao = await _acao(r.acao_id)
        editado = acao.texto_gerado.replace("Assunto: " + redator.ASSUNTO, "Assunto: o WhatsApp da clínica")
        await fila.decidir(r.acao_id, decisao="aprovar", texto_final=editado)

        lead = await redator.enviei(s, lead.id, r.acao_id, hoje=HOJE)
        assert lead.estagio == "contatado"
        pode_em = calendario.somar_dias_uteis(HOJE, 5)
        assert lead.proxima_em == pode_em
        enviado = await s.scalar(select(Interacao).where(Interacao.tipo == "email_frio"))
        assert enviado.dados["assunto"] == "o WhatsApp da clínica" and not enviado.texto.startswith("Assunto")
        with pytest.raises(redator.NaoPode, match="já foi marcado"):
            await redator.enviei(s, lead.id, r.acao_id, hoje=HOJE)
        with pytest.raises(redator.NaoPode, match="já foi enviado"):
            await redator.escrever(s, lead.id, hoje=HOJE)

        # o lembrete conta 5 dias úteis a partir do dia em que o e-mail 1 saiu
        saiu = enviado.criado_em.date()
        antes = calendario.somar_dias_uteis(saiu, 4)
        with pytest.raises(redator.NaoPode, match="só sai em"):
            await redator.escrever(s, lead.id, tipo=redator.LEMBRETE, hoje=antes)
        lembrete = await redator.escrever(
            s, lead.id, tipo=redator.LEMBRETE, hoje=calendario.somar_dias_uteis(saiu, 5)
        )
        texto = (await _acao(lembrete.acao_id)).texto_gerado
        assert texto.startswith("Assunto: Re: o WhatsApp da clínica")
        assert "último e-mail" in texto and redator.OPT_OUT in texto
        await fila.decidir(lembrete.acao_id, decisao="aprovar")
        lead = await redator.enviei(s, lead.id, lembrete.acao_id, hoje=HOJE)
        assert lead.estagio == "contatado" and "depois dele, nada" in lead.proxima_acao

        with pytest.raises(redator.NaoPode, match="depois dele, nada"):
            await redator.escrever(s, lead.id, tipo=redator.LEMBRETE, hoje=date(2027, 3, 1))
        lista = await redator.rascunhos(s, lead.id)
        tarefas_abertas = list(await s.scalars(select(Tarefa).where(Tarefa.feita_em.is_(None))))
    assert [(x.tipo, x.enviado_em is not None) for x in lista] == [("email_frio", True), ("lembrete_frio", True)]
    assert tarefas_abertas == []


# ── API ───────────────────────────────────────────────────────────────


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


async def test_api_escrever_e_enviei(logado):
    from app.api.services.auth.csrf import csrf_cookie_name

    gateway.usar_provider(IA(BOA))
    async with get_session() as s:
        sem = await _lead(s, confirmado=False)
        lead = await _lead(s)
    csrf = {"X-CSRF-Token": logado.cookies.get(csrf_cookie_name())}

    r = await logado.post(f"/api/comercial/leads/{sem.id}/escrever", json={}, headers=csrf)
    assert r.status_code == 409 and "confirmado" in r.json()["detail"]
    assert (await logado.post("/api/comercial/leads/999999/escrever", json={}, headers=csrf)).status_code == 404

    r = await logado.post(f"/api/comercial/leads/{lead.id}/escrever", json={}, headers=csrf)
    assert r.status_code == 200
    corpo = r.json()
    (rascunho,) = corpo["lead"]["rascunhos"]
    assert rascunho["status"] == "pendente" and rascunho["assunto"] == redator.ASSUNTO
    assert BOA["abertura"] in rascunho["corpo"]

    r = await logado.post(f"/api/comercial/leads/{lead.id}/enviei", json={"acao_id": corpo["acao_id"]}, headers=csrf)
    assert r.status_code == 409  # ainda na fila

    await fila.decidir(corpo["acao_id"], decisao="aprovar", texto_final=f"Assunto: x\n\n{rascunho['corpo'].replace(redator.OPT_OUT, '')}")
    det = (await logado.get(f"/api/comercial/leads/{lead.id}")).json()
    assert any("opt-out" in p for p in det["rascunhos"][0]["problemas"])  # editei e tirei o opt-out: a tela avisa
    r = await logado.post(f"/api/comercial/leads/{lead.id}/enviei", json={"acao_id": corpo["acao_id"]}, headers=csrf)
    assert r.status_code == 200 and r.json()["estagio"] == "contatado"
    assert r.json()["rascunhos"][0]["enviado_em"]
