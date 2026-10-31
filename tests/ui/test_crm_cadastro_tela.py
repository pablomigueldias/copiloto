"""O CRM no desenho do prospector, num navegador de verdade.

Empresa, contato e negócio criados de dentro da ficha, a navegação entre eles
pela ficha lateral, a tabela editável no lugar e o kanban que só deixa o
negócio andar pela regra.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from app.comercial.crm import cadastro
from app.db.models.comercial.crm import Contato, Empresa, Interacao, Lead
from app.db.session import get_session

pytestmark = pytest.mark.ui


def sem_erros(pagina):
    assert not pagina.erros_de_js, f"JS quebrou: {pagina.erros_de_js}"


async def _aba(p, rotulo: str):
    await p.click(f'nav[aria-label="CRM comercial"] a:has-text("{rotulo}")')
    await p.wait_for_selector(f"text=Comercial · {rotulo}", timeout=60000)


async def test_empresa_contato_e_negocio_pela_ficha(comercial):
    p = comercial
    await _aba(p, "Empresas")
    await p.click('button:has-text("+ nova empresa")')
    painel = p.locator('aside[aria-label="Nova empresa"]')
    await painel.locator("label:has-text('Nome') input").fill("Clínica Aurora")
    await painel.locator('button:has-text("criar")').click()

    ficha = p.locator("aside[role=dialog]").last
    await ficha.locator('h2:text-is("Clínica Aurora")').wait_for(timeout=10000)

    # "+ contato" de dentro da empresa já vem com a empresa marcada.
    await ficha.locator('button:has-text("+ contato")').click()
    form = p.locator('aside[aria-label="Novo contato"]')
    await form.locator("label:has-text('Nome') input").first.fill("Ana Souza")
    await form.locator("label:has-text('Cargo') input").fill("sócia")
    await form.locator("label:has-text('Decide a compra') input").check()
    await form.locator('button:has-text("criar")').click()
    await ficha.get_by_text("Ana Souza").wait_for(timeout=10000)

    await ficha.locator('button:has-text("+ negócio")').click()
    form = p.locator('aside[aria-label="Novo negócio"]')
    await form.locator("label:has-text('Valor estimado') input").fill("1800")
    await form.locator('button:has-text("criar")').click()
    await ficha.get_by_text("prospect · R$\u00a01.800,00").wait_for(timeout=10000)

    # Do negócio para a ficha dele, e de volta.
    await ficha.get_by_text("prospect · R$\u00a01.800,00").click()
    await ficha.locator('text=← voltar').wait_for(timeout=10000)
    await ficha.get_by_placeholder("anotar…").fill("liguei, pediu proposta por e-mail")
    await ficha.locator('button:has-text("registrar")').click()
    await ficha.get_by_text("liguei, pediu proposta por e-mail").wait_for(timeout=10000)

    # Estágio pela ficha: só as transições permitidas aparecem.
    await ficha.locator("button:has-text('prospect')").first.click()
    opcoes = await ficha.locator("select").first.locator("option").all_inner_texts()
    assert opcoes == ["prospect", "contatado", "não agora", "perdido"]
    await ficha.locator("select").first.select_option("contatado")
    await ficha.locator("button:has-text('contatado')").first.wait_for(timeout=10000)

    shot = os.environ.get("CRM_FICHA_SCREENSHOT")
    if shot:
        await p.screenshot(path=shot, full_page=False)

    await ficha.locator('text=← voltar').click()
    await ficha.locator('h2:text-is("Clínica Aurora")').wait_for(timeout=10000)

    async with get_session() as s:
        (emp,) = await s.scalars(select(Empresa))
        (ana,) = await s.scalars(select(Contato))
        (lead,) = await s.scalars(select(Lead))
        notas = [i.texto for i in await s.scalars(select(Interacao))]
    assert (ana.empresa_id, ana.decisor, ana.cargo) == (emp.id, True, "sócia")
    assert (lead.empresa_id, lead.contato_id, lead.estagio) == (emp.id, ana.id, "contatado")
    assert float(lead.valor_estimado) == 1800
    assert notas == ["liguei, pediu proposta por e-mail"]
    sem_erros(p)


async def test_tabela_edita_no_lugar(comercial):
    async with get_session() as s:
        await cadastro.criar(s, "empresa", {"nome": "Espaço Vila", "bairro": "Vila Mariana"})
    p = comercial
    await _aba(p, "Empresas")
    await p.get_by_text("Espaço Vila").wait_for(timeout=10000)
    await p.locator("td button:has-text('prospect')").click()
    await p.locator("td select").select_option("cliente")
    await p.locator("td button:has-text('cliente')").wait_for(timeout=10000)
    await p.locator("td button:has-text('Vila Mariana')").click()
    await p.locator("td input").fill("Pinheiros")
    await p.locator("td input").press("Enter")
    await p.locator("td button:has-text('Pinheiros')").wait_for(timeout=10000)

    async with get_session() as s:
        (emp,) = await s.scalars(select(Empresa))
    assert (emp.status, emp.bairro) == ("cliente", "Pinheiros")
    sem_erros(p)


async def test_kanban_so_anda_pela_regra(comercial):
    async with get_session() as s:
        emp = await cadastro.criar(s, "empresa", {"nome": "Clínica Aurora"})
        neg = await cadastro.criar(s, "negocio", {"empresa_id": emp, "valor_estimado": 900})
    p = comercial
    # Numa tela de notebook (1366) as seis colunas cabem sem rolar de lado.
    await p.set_viewport_size({"width": 1366, "height": 900})
    await _aba(p, "Negócios")
    cartao = p.locator("article:has-text('Clínica Aurora')")
    await cartao.wait_for(timeout=10000)

    # Pega pelo título: o centro do cartão é a célula do valor, que é botão.
    pega = {"x": 20, "y": 14}
    await cartao.drag_to(p.locator('section[aria-label="proposta"]'), source_position=pega)
    await p.get_by_text("não é permitido").wait_for(timeout=10000)
    await cartao.drag_to(p.locator('section[aria-label="contatado"]'), source_position=pega)
    await p.locator('section[aria-label="contatado"] article:has-text("Clínica Aurora")').wait_for(timeout=10000)
    # O cartão muda de coluna antes da resposta (otimista); o aviso vem depois dela.
    await p.get_by_text("Clínica Aurora: contatado").wait_for(timeout=10000)

    shot = os.environ.get("CRM_KANBAN_SCREENSHOT")
    if shot:
        await p.screenshot(path=shot, full_page=True)

    async with get_session() as s:
        lead = await s.get(Lead, neg)
    assert lead.estagio == "contatado"
    sem_erros(p)


async def test_visao_geral_mostra_o_funil(comercial):
    async with get_session() as s:
        a = await cadastro.criar(s, "negocio", {"nome": "A", "valor_estimado": 1000})
        await cadastro.criar(s, "atividade", {"lead_id": a, "tipo": "ligar", "descricao": "retornar a Ana"})
    p = comercial
    await p.reload(wait_until="domcontentloaded")
    await p.get_by_text("retornar a Ana").wait_for(timeout=60000)
    await p.get_by_text("negócios abertos").wait_for()
    shot = os.environ.get("CRM_PAINEL_SCREENSHOT")
    if shot:
        await p.screenshot(path=shot, full_page=True)
    sem_erros(p)


async def test_pesquisador_e_redator_na_ficha_do_negocio(comercial):
    """O fluxo da prospecção inteiro sem sair do kanban: pesquisar, escrever, enviei."""
    from app.comercial.crm import leads as leads_mod
    from app.db.models.acao_pendente import AcaoPendente
    from app.db.models.comercial.crm import OrigemLead
    from app.fila import servico as fila

    async with get_session() as s:
        lead = await leads_mod.criar(
            s, origem=OrigemLead.PROSPECCAO, nome="CLINICA AURORA LTDA", email="contato@clinicaaurora.test"
        )
        lead.email_fonte = "https://clinicaaurora.test/contato"
        # Ficha sem fato para a abertura: o Redator não chama a IA (a API roda noutro processo).
        s.add(Interacao(
            lead_id=lead.id, canal="nota", direcao="interna", tipo="ficha", texto="Ficha de teste",
            dados={"site": "https://clinicaaurora.test", "paginas": ["https://clinicaaurora.test"], "emails": [],
                   "whatsapp": None, "agendamento_online": None, "psicologos_crp": None,
                   "o_que_faz": None, "gancho": None},
        ))
        await s.commit()
    p = comercial
    await p.set_viewport_size({"width": 1366, "height": 900})
    await _aba(p, "Negócios")
    await p.locator("article:has-text('CLINICA AURORA LTDA')").click()
    ficha = p.locator("aside[role=dialog]").last
    await ficha.get_by_text("Prospecção · Pesquisador e e-mail").wait_for(timeout=10000)
    await ficha.get_by_text("1 página(s) lida(s) de https://clinicaaurora.test").wait_for(timeout=10000)
    await ficha.get_by_text("confirmado no site").wait_for()

    await ficha.locator('button:has-text("Escrever o e-mail 1")').click()
    await ficha.get_by_text("fila de aprovação →").wait_for(timeout=10000)
    async with get_session() as s:
        (acao,) = await s.scalars(select(AcaoPendente).where(AcaoPendente.alvo_ref == f"comercial_lead:{lead.id}"))
    await fila.decidir(acao.id, decisao="aprovar")

    await p.reload(wait_until="domcontentloaded")
    await p.locator("article:has-text('CLINICA AURORA LTDA')").click(timeout=60000)
    ficha = p.locator("aside[role=dialog]").last
    await ficha.get_by_text("Aprovado. Copie para o webmail").wait_for(timeout=10000)
    shot = os.environ.get("CRM_PROSPECCAO_SCREENSHOT")
    if shot:
        await p.screenshot(path=shot, full_page=False)
    await ficha.locator('button:has-text("Enviei")').click()
    await ficha.get_by_text("o lembrete pode sair a partir de").wait_for(timeout=10000)
    # O estágio da ficha acompanha: o "Enviei" moveu para contatado.
    await ficha.locator("button:has-text('contatado')").first.wait_for(timeout=10000)

    async with get_session() as s:
        assert (await s.get(Lead, lead.id, populate_existing=True)).estagio == "contatado"
    sem_erros(p)
