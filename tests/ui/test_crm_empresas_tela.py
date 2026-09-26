"""A tela Empresas do CRM (Fase 1, passo 2), num navegador de verdade."""
from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from app.db.models.comercial.crm import Lead, Tarefa
from app.db.models.comercial.prospeccao import Canal, Estabelecimento
from app.db.session import get_session

pytestmark = pytest.mark.ui


def sem_erros(pagina):
    assert not pagina.erros_de_js, f"JS quebrou: {pagina.erros_de_js}"


@pytest.fixture
async def base():
    async with get_session() as s:
        for nome, bairro in [("Clínica de Psicologia Aurora", "Pinheiros"), ("Espaço Psicologia Vila", "Vila Mariana")]:
            e = Estabelecimento(nicho="clinica", segmento="clinica_especialidade", nome_fantasia=nome,
                                pessoa_fisica=False, situacao="ativo", bairro=bairro)
            s.add(e)
            await s.flush()
            email = nome.split()[-1].lower() + "@clinica.test"
            s.add(Canal(estabelecimento_id=e.id, tipo="email", valor=email, valor_original=email, valido=True))
        await s.commit()


async def test_marcar_e_trazer_para_o_crm(comercial_empresas, base):
    p = comercial_empresas
    await p.reload(wait_until="domcontentloaded")
    await p.wait_for_selector('h1:has-text("Quem trazer para o CRM")', timeout=60000)
    await p.get_by_text("Clínica de Psicologia Aurora").wait_for(timeout=10000)
    shot = os.environ.get("EMPRESAS_SCREENSHOT")
    if shot:
        await p.screenshot(path=shot, full_page=True)

    await p.get_by_label("selecionar Clínica de Psicologia Aurora").check()
    await p.click('button:has-text("Trazer 1 para o CRM")')
    await p.get_by_text("1 clínica trazida para o CRM").wait_for(timeout=10000)
    await p.get_by_text("no CRM").first.wait_for(timeout=10000)

    async with get_session() as s:
        leads = list(await s.scalars(select(Lead)))
        tarefas = list(await s.scalars(select(Tarefa)))
    assert [lead.nome for lead in leads] == ["Clínica de Psicologia Aurora"]
    assert [t.tipo for t in tarefas] == ["pesquisar"]
    sem_erros(p)
