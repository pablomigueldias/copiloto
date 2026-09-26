"""O lead do CRM (Fase 1, passo 1): supressão, transições e a volta em 90 dias.

O que mais importa: quem pediu para sair não volta a ser lead por caminho
nenhum, e o estágio só anda pelas transições permitidas.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.comercial.crm import leads
from app.comercial.prospeccao import retencao
from app.db.models.comercial.crm import Estagio, Lead, OrigemLead, Transicao
from app.db.models.comercial.prospeccao import MotivoSupressao, TipoSupressao
from app.db.session import get_session

HOJE = date(2026, 12, 1)


async def _lead(session, **kw):
    dados = {"origem": OrigemLead.PROSPECCAO, "nome": "Clínica Teste", "email": "contato@clinica.test"}
    return await leads.criar(session, **{**dados, **kw})


async def test_lead_nasce_prospect_com_a_transicao_registrada():
    async with get_session() as s:
        lead = await _lead(s, email="  Contato@Clinica.TEST ")
        assert lead.estagio == "prospect"
        assert lead.email == "contato@clinica.test"
        trans = list(await s.scalars(select(Transicao).where(Transicao.lead_id == lead.id)))
        assert [(t.de, t.para) for t in trans] == [(None, "prospect")]


async def test_email_suprimido_nao_vira_lead():
    async with get_session() as s:
        await retencao.suprimir(s, TipoSupressao.EMAIL, "sair@clinica.test", MotivoSupressao.OPTOUT)
        with pytest.raises(leads.Suprimido):
            await _lead(s, email="SAIR@clinica.test")


async def test_telefone_suprimido_nao_vira_lead():
    async with get_session() as s:
        await retencao.suprimir(s, TipoSupressao.TELEFONE, "(11) 91234-5678", MotivoSupressao.OPTOUT)
        with pytest.raises(leads.Suprimido):
            await _lead(s, email=None, telefone="11912345678")


async def test_so_anda_pelas_transicoes_permitidas():
    async with get_session() as s:
        lead = await _lead(s)
        with pytest.raises(leads.TransicaoInvalida):
            await leads.mover(s, lead.id, Estagio.PROPOSTA)
        lead = await leads.mover(s, lead.id, Estagio.CONTATADO, motivo="e-mail 1")
        lead = await leads.mover(s, lead.id, Estagio.RESPONDEU)
        assert lead.estagio == "respondeu"


async def test_perdido_exige_motivo_e_e_final():
    async with get_session() as s:
        lead = await _lead(s)
        with pytest.raises(leads.TransicaoInvalida):
            await leads.mover(s, lead.id, Estagio.PERDIDO)
        lead = await leads.mover(s, lead.id, Estagio.PERDIDO, motivo="já tem agendacare")
        assert lead.motivo_perda == "já tem agendacare"
        with pytest.raises(leads.TransicaoInvalida):
            await leads.mover(s, lead.id, Estagio.PROSPECT)


async def test_estabelecimento_nao_tem_dois_leads_abertos():
    async with get_session() as s:
        from app.db.models.comercial.prospeccao import Estabelecimento

        est = Estabelecimento(nicho="clinica", pessoa_fisica=False, situacao="ativo", nome_fantasia="X")
        s.add(est)
        await s.commit()
        await _lead(s, estabelecimento_id=est.id)
        with pytest.raises(leads.JaNoCrm):
            await _lead(s, estabelecimento_id=est.id, email="outro@x.test")


async def test_base_apagar_o_estabelecimento_nao_apaga_o_lead():
    """Retenção ou supressão na base não pode sumir com a conversa (SET NULL)."""
    async with get_session() as s:
        from app.db.models.comercial.prospeccao import Estabelecimento

        est = Estabelecimento(nicho="clinica", pessoa_fisica=False, situacao="ativo", nome_fantasia="Y")
        s.add(est)
        await s.commit()
        lead = await _lead(s, estabelecimento_id=est.id)
        await retencao.apagar_estabelecimentos(s, [est.id])
        await s.commit()
        lead = await s.get(Lead, lead.id, populate_existing=True)
        assert lead is not None and lead.estabelecimento_id is None


async def test_nao_agora_volta_em_90_dias_e_suprimido_vira_perdido():
    async with get_session() as s:
        volta = await _lead(s, email="volta@clinica.test")
        sai = await _lead(s, email="sai@clinica.test")
        for lead in (volta, sai):
            await leads.mover(s, lead.id, Estagio.NAO_AGORA, motivo="sem orçamento", hoje=HOJE)
        await retencao.suprimir(s, TipoSupressao.EMAIL, "sai@clinica.test", MotivoSupressao.OPTOUT)

        assert await leads.voltar_os_de_90_dias(s, hoje=date(2027, 2, 28)) == 0
        assert await leads.voltar_os_de_90_dias(s, hoje=date(2027, 3, 1)) == 2
        assert (await s.get(Lead, volta.id, populate_existing=True)).estagio == "prospect"
        saiu = await s.get(Lead, sai.id, populate_existing=True)
        assert saiu.estagio == "perdido" and "sair" in saiu.motivo_perda
