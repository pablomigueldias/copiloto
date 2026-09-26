"""Empresas (Fase 1, passo 2): procurar na base e trazer para o CRM."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.comercial.crm import empresas, leads
from app.comercial.prospeccao import retencao
from app.db.models.comercial.crm import Tarefa
from app.db.models.comercial.prospeccao import (
    Canal,
    Estabelecimento,
    MotivoSupressao,
    TipoSupressao,
)
from app.db.session import get_session

HOJE = date(2026, 12, 1)


async def _est(s, nome, *, email=None, segmento="clinica_especialidade", pf=False, bairro="Pinheiros"):
    e = Estabelecimento(
        nicho="clinica", segmento=segmento, nome_fantasia=nome, pessoa_fisica=pf,
        situacao="ativo", bairro=bairro,
    )
    s.add(e)
    await s.flush()
    if email:
        s.add(Canal(estabelecimento_id=e.id, tipo="email", valor=email, valor_original=email, valido=True))
    await s.commit()
    return e.id


async def test_busca_padrao_e_clinica_de_psicologia_com_email():
    async with get_session() as s:
        alvo = await _est(s, "Clínica de Psicologia Alfa", email="alfa@clinica.test")
        await _est(s, "Clínica de Psicologia Sem Email")
        await _est(s, "Consultório de Psicologia", email="solo@x.test", segmento="consultorio_isolado")
        await _est(s, "Clínica Odonto", email="odonto@x.test")
        total, linhas = await empresas.buscar(s)
        assert total == 1 and [linha.id for linha in linhas] == [alvo]
        assert linhas[0].emails == ["alfa@clinica.test"]


async def test_trazer_cria_lead_e_tarefa_de_pesquisar():
    async with get_session() as s:
        e1 = await _est(s, "Psicologia Um", email="um@x.test")
        e2 = await _est(s, "Psicologia Dois", email="dois@x.test")
        r = await empresas.trazer(s, [e1, e2], hoje=HOJE)
        assert len(r.trazidos) == 2 and r.pulados == {}
        tarefas = list(await s.scalars(select(Tarefa)))
        assert {t.tipo for t in tarefas} == {"pesquisar"} and {t.vence_em for t in tarefas} == {HOJE}
        _, linhas = await empresas.buscar(s)
        assert all(linha.lead_id for linha in linhas)
        _, fora = await empresas.buscar(s, incluir_no_crm=False)
        assert fora == []


async def test_trazer_pula_suprimido_repetido_e_pessoa_fisica():
    async with get_session() as s:
        ok = await _est(s, "Psicologia Ok", email="ok@x.test")
        sai = await _est(s, "Psicologia Sai", email="sai@x.test")
        pf = await _est(s, "Psicologia PF", email="pf@x.test", pf=True)
        await empresas.trazer(s, [ok], hoje=HOJE)
        await retencao.suprimir(s, TipoSupressao.EMAIL, "sai@x.test", MotivoSupressao.OPTOUT)
        r = await empresas.trazer(s, [ok, sai, pf], hoje=HOJE)
        assert r.trazidos == []
        assert r.pulados[ok] == "já está no CRM"
        # a supressão apagou o e-mail da base: sem destinatário, não vira lead
        assert r.pulados[sai] == "sem e-mail na base"
        assert "pessoa física" in r.pulados[pf]


async def test_pessoa_fisica_so_uma_por_vez_com_confirmacao():
    async with get_session() as s:
        pf = await _est(s, "Psicóloga Solo", email="solo@x.test", pf=True)
        outra = await _est(s, "Psicologia Dois", email="dois@x.test")
        with pytest.raises(leads.CrmErro):
            await empresas.trazer(s, [pf, outra], confirmar_pessoa_fisica=True)
        r = await empresas.trazer(s, [pf], confirmar_pessoa_fisica=True, hoje=HOJE)
        assert len(r.trazidos) == 1


async def test_no_maximo_dez_por_vez():
    async with get_session() as s:
        with pytest.raises(leads.CrmErro):
            await empresas.trazer(s, list(range(1, 12)))


# ── API ───────────────────────────────────────────────────────────────


@pytest.fixture
async def logado(client, usuario):
    u, senha = usuario
    r = await client.post("/api/auth/login", json={"email": u.email, "senha": senha})
    assert r.status_code == 200
    return client


async def test_api_busca_e_traz(logado):
    from app.api.services.auth.csrf import csrf_cookie_name

    async with get_session() as s:
        e = await _est(s, "Psicologia API", email="api@x.test")
    r = await logado.get("/api/comercial/empresas")
    assert r.status_code == 200 and r.json()["total"] == 1
    csrf = {"X-CSRF-Token": logado.cookies.get(csrf_cookie_name())}
    r = await logado.post("/api/comercial/empresas/trazer", json={"ids": [e]}, headers=csrf)
    assert r.status_code == 200 and len(r.json()["trazidos"]) == 1
    r = await logado.get("/api/comercial/empresas", params={"segmento": "hospital"})
    assert r.status_code == 422


async def test_api_exige_login(client):
    assert (await client.get("/api/comercial/empresas")).status_code == 401
