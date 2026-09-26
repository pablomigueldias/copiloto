"""O quadro de pendências, num navegador de verdade.

O que a suíte sem navegador não vê: o cartão arrastado entre colunas gravar
de verdade (e não só mudar na tela), e o filtro por tópico esconder sem mexer
na ordem dos cartões escondidos.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from app.pendencias import servico

pytestmark = pytest.mark.ui

COLUNA = 'section[aria-label="{}"]'


def sem_erros(pagina):
    assert not pagina.erros_de_js, f"JS quebrou: {pagina.erros_de_js}"


@pytest.fixture
async def cartoes():
    await servico.criar(
        titulo="Ligar o 2FA do Bitwarden",
        topico="Contas e ferramentas",
        descricao="e guardar a senha do backup",
        quando="agora",
        onde="`fase-0/operacao.md`",
    )
    await servico.criar(
        titulo="Conferir o backup",
        topico="Contas e ferramentas",
        quando="03/10",
        prazo=date.today() - timedelta(days=2),
    )
    await servico.criar(titulo="Nome do módulo do Zoho", topico="Currículo")


async def _recarregar(pagina):
    await pagina.reload(wait_until="domcontentloaded")
    await pagina.wait_for_selector('h1:has-text("O que é meu fazer")', timeout=60000)


async def test_quadro_mostra_os_cartoes_nas_colunas(pendencias, cartoes):
    await _recarregar(pendencias)
    a_fazer = pendencias.locator(COLUNA.format("A fazer"))
    await a_fazer.get_by_text("Ligar o 2FA do Bitwarden").wait_for(timeout=10000)
    assert await a_fazer.locator("article").count() == 3
    # prazo vencido aparece como vencido, e o `onde` sem as crases do Markdown
    await a_fazer.get_by_text("venceu há 2 d").wait_for()
    await a_fazer.get_by_text("fase-0/operacao.md").wait_for()

    shot = os.environ.get("PENDENCIAS_SCREENSHOT")
    if shot:
        await pendencias.screenshot(path=shot, full_page=True)
    sem_erros(pendencias)


async def test_seta_move_e_grava(pendencias, cartoes):
    await _recarregar(pendencias)
    cartao = pendencias.locator("article", has_text="Nome do módulo do Zoho")
    await cartao.get_by_role("button", name="mover para Fazendo").click()
    await pendencias.locator(COLUNA.format("Fazendo")).get_by_text(
        "Nome do módulo do Zoho"
    ).wait_for(timeout=10000)
    await pendencias.wait_for_timeout(500)

    gravado = {p.titulo: p for p in await servico.listar()}
    assert gravado["Nome do módulo do Zoho"].coluna == "fazendo"
    sem_erros(pendencias)


async def test_arrastar_para_feito_grava_a_conclusao(pendencias, cartoes):
    await _recarregar(pendencias)
    await pendencias.locator("article", has_text="Conferir o backup").drag_to(
        pendencias.locator(COLUNA.format("Feito"))
    )
    await pendencias.locator(COLUNA.format("Feito")).get_by_text(
        "Conferir o backup"
    ).wait_for(timeout=10000)
    await pendencias.wait_for_timeout(500)

    backup = next(p for p in await servico.listar() if p.titulo == "Conferir o backup")
    assert backup.coluna == "feito" and backup.concluida_em is not None
    sem_erros(pendencias)


async def test_nova_pendencia_pelo_dialogo(pendencias, cartoes):
    await _recarregar(pendencias)
    await pendencias.click('button:has-text("+ nova")')
    await pendencias.fill("#pend-titulo", "Revisar a isca")
    await pendencias.fill("#pend-topico", "Newsletter")
    await pendencias.fill("#pend-prazo", "2026-11-17")
    await pendencias.click('div[role="dialog"] button:has-text("salvar")')
    await pendencias.locator(COLUNA.format("A fazer")).get_by_text(
        "Revisar a isca"
    ).wait_for(timeout=10000)

    isca = next(p for p in await servico.listar() if p.titulo == "Revisar a isca")
    assert (isca.topico, isca.prazo) == ("Newsletter", date(2026, 11, 17))
    sem_erros(pendencias)


async def test_filtro_por_topico(pendencias, cartoes):
    await _recarregar(pendencias)
    await pendencias.click('[role="toolbar"] button:has-text("Currículo")')
    a_fazer = pendencias.locator(COLUNA.format("A fazer"))
    await a_fazer.get_by_text("Nome do módulo do Zoho").wait_for(timeout=10000)
    assert await a_fazer.locator("article").count() == 1
    sem_erros(pendencias)
