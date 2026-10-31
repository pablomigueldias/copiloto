"""O cadastro do CRM: empresa, contato, negócio e atividade, com CRUD.

O que mais importa: o CRUD não fura as regras do lead. Supressão vale no
cadastro à mão, estágio só anda pela transição, negócio que já recebeu contato
não se apaga, e a ficha mostra o que está ligado a cada registro.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.api.services.auth.csrf import csrf_cookie_name
from app.comercial.crm import cadastro, empresas, leads
from app.comercial.prospeccao import retencao
from app.db.models.acao_pendente import AcaoPendente
from app.db.models.comercial.crm import Contato, Empresa, Interacao, Lead, Tarefa
from app.db.models.comercial.prospeccao import (
    Canal,
    Estabelecimento,
    MotivoSupressao,
    TipoSupressao,
)
from app.db.session import get_session

HOJE = date(2026, 12, 1)


async def _empresa(s, **kw) -> int:
    return await cadastro.criar(s, "empresa", {"nome": "Clínica Aurora", **kw})


# ── serviço ───────────────────────────────────────────────────────────


async def test_negocio_nasce_da_empresa_com_o_contato_e_o_canal_dele():
    async with get_session() as s:
        emp = await _empresa(s, site="https://aurora.test")
        ana = await cadastro.criar(
            s, "contato", {"nome": "Ana", "cargo": "sócia", "decisor": True,
                           "email": "Ana@Aurora.test", "empresa_id": emp},
        )
        neg = await cadastro.criar(s, "negocio", {"contato_id": ana, "valor_estimado": "1.500,00"})
        lead = await s.get(Lead, neg)
        assert (lead.nome, lead.empresa_id, lead.contato_id) == ("Clínica Aurora", emp, ana)
        assert (lead.email, lead.origem, lead.estagio) == ("ana@aurora.test", "indicacao", "prospect")
        assert float(lead.valor_estimado) == 1500.0


async def test_contato_suprimido_nao_nasce_nem_entra_por_edicao():
    async with get_session() as s:
        await retencao.suprimir(s, TipoSupressao.EMAIL, "sair@x.test", MotivoSupressao.OPTOUT)
        with pytest.raises(leads.Suprimido):
            await cadastro.criar(s, "contato", {"nome": "Bia", "email": "sair@x.test"})
        bia = await cadastro.criar(s, "contato", {"nome": "Bia"})
        with pytest.raises(leads.Suprimido):
            await cadastro.editar(s, "contato", bia, {"email": "SAIR@x.test"})
        assert (await s.get(Contato, bia, populate_existing=True)).email is None


async def test_contato_de_outra_empresa_nao_entra_no_negocio():
    async with get_session() as s:
        a, b = await _empresa(s), await _empresa(s, nome="Outra")
        de_b = await cadastro.criar(s, "contato", {"nome": "Caio", "empresa_id": b})
        with pytest.raises(leads.CrmErro, match="outra empresa"):
            await cadastro.criar(s, "negocio", {"empresa_id": a, "contato_id": de_b})


async def test_edicao_generica_nao_mexe_no_estagio():
    async with get_session() as s:
        neg = await cadastro.criar(s, "negocio", {"nome": "Indicação da Ana"})
        with pytest.raises(leads.CrmErro, match="não se edita"):
            await cadastro.editar(s, "negocio", neg, {"estagio": "ganho"})
        with pytest.raises(leads.TransicaoInvalida):
            await cadastro.mover(s, neg, "proposta", None)
        await cadastro.mover(s, neg, "contatado", "liguei")
        assert (await s.get(Lead, neg, populate_existing=True)).estagio == "contatado"


async def test_negocio_ja_contatado_nao_se_apaga():
    async with get_session() as s:
        neg = await cadastro.criar(s, "negocio", {"nome": "X"})
        await cadastro.mover(s, neg, "contatado", "e-mail 1")
        with pytest.raises(cadastro.NaoPode, match="perdido"):
            await cadastro.excluir(s, "negocio", neg)


async def test_negocio_novo_se_apaga_e_leva_o_rascunho_pendente():
    async with get_session() as s:
        neg = await cadastro.criar(s, "negocio", {"nome": "X"})
        s.add(AcaoPendente(agente="comercial.redator", tipo="email_frio", titulo="t", payload={},
                           alvo_ref=f"comercial_lead:{neg}", status="pendente"))
        await s.commit()
        await cadastro.excluir(s, "negocio", neg)
        assert await s.get(Lead, neg) is None
        assert list(await s.scalars(select(AcaoPendente))) == []


async def test_empresa_com_negocio_nao_se_apaga_e_sem_negocio_leva_os_contatos():
    async with get_session() as s:
        emp = await _empresa(s)
        await cadastro.criar(s, "contato", {"nome": "Ana", "empresa_id": emp})
        neg = await cadastro.criar(s, "negocio", {"empresa_id": emp})
        with pytest.raises(cadastro.NaoPode, match="1 negócio"):
            await cadastro.excluir(s, "empresa", emp)
        await cadastro.excluir(s, "negocio", neg)
        await cadastro.excluir(s, "empresa", emp)
        assert list(await s.scalars(select(Contato))) == []


async def test_atividade_manual_marca_e_desmarca_feita():
    async with get_session() as s:
        neg = await cadastro.criar(s, "negocio", {"nome": "X"})
        t = await cadastro.criar(s, "atividade", {"lead_id": neg, "tipo": "ligar", "descricao": "falar com a Ana"},
                                 hoje=HOJE)
        await cadastro.editar(s, "atividade", t, {"feita": True})
        assert (await s.get(Tarefa, t, populate_existing=True)).feita_em is not None
        await cadastro.editar(s, "atividade", t, {"feita": False})
        assert (await s.get(Tarefa, t, populate_existing=True)).feita_em is None
        with pytest.raises(leads.CrmErro):
            await cadastro.criar(s, "atividade", {"tipo": "ligar"})


async def test_ficha_da_empresa_mostra_contatos_negocios_atividades_e_a_linha_do_tempo():
    async with get_session() as s:
        emp = await _empresa(s)
        ana = await cadastro.criar(s, "contato", {"nome": "Ana", "empresa_id": emp})
        neg = await cadastro.criar(s, "negocio", {"empresa_id": emp, "contato_id": ana})
        await cadastro.criar(s, "atividade", {"lead_id": neg, "tipo": "ligar"})
        await cadastro.registrar(s, neg, texto="liguei, pediu proposta", canal="whatsapp", direcao="entrada")

        r = await cadastro.registro(s, "empresa", emp)
        grupos = {g["titulo"]: [i["nome"] for i in g["itens"]] for g in r["grupos"]}
        assert grupos == {"Contatos": ["Ana"], "Negócios": ["Clínica Aurora"], "Atividades": ["ligar"]}
        eventos = [(e["rotulo"], e["texto"]) for e in r["linha_do_tempo"]]
        assert ("manual", "liguei, pediu proposta") in eventos
        assert ("novo → prospect", "criado (indicacao)") in eventos

        r = await cadastro.registro(s, "negocio", neg)
        estagio = next(c for c in r["campos"] if c["campo"] == "estagio")
        assert [o["valor"] for o in estagio["opcoes"]] == ["contatado", "nao_agora", "perdido"]


async def test_trazer_da_base_cria_a_empresa_e_reaproveita_na_volta():
    async with get_session() as s:
        e = Estabelecimento(nicho="clinica", segmento="clinica_especialidade", nome_fantasia="Aurora",
                            pessoa_fisica=False, situacao="ativo", bairro="Pinheiros", uf="SP")
        s.add(e)
        await s.flush()
        s.add(Canal(estabelecimento_id=e.id, tipo="email", valor="a@aurora.test",
                    valor_original="a@aurora.test", valido=True))
        await s.commit()
        r = await empresas.trazer(s, [e.id], hoje=HOJE)
        lead = await s.get(Lead, r.trazidos[0])
        emp = await s.get(Empresa, lead.empresa_id)
        assert (emp.nome, emp.bairro, emp.estabelecimento_id) == ("Aurora", "Pinheiros", e.id)

        await leads.mover(s, lead.id, leads.Estagio.PERDIDO, motivo="teste")
        r = await empresas.trazer(s, [e.id], hoje=HOJE)
        assert (await s.get(Lead, r.trazidos[0])).empresa_id == emp.id
        assert len(list(await s.scalars(select(Empresa)))) == 1


async def test_painel_soma_o_que_esta_aberto():
    async with get_session() as s:
        a = await cadastro.criar(s, "negocio", {"nome": "A", "valor_estimado": 1000})
        b = await cadastro.criar(s, "negocio", {"nome": "B", "valor_estimado": 500})
        await cadastro.mover(s, b, "perdido", "caro")
        await cadastro.criar(s, "atividade", {"lead_id": a, "vence_em": "2020-01-01"})
        p = await cadastro.painel(s)
        assert (p["negocios_abertos"], p["valor_aberto"], p["perdidos"]) == (1, 1000.0, 1)
        assert p["tarefas_atrasadas"] == 1
        assert p["motivos_perda"] == [{"motivo": "caro", "total": 1}]


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
    assert (await client.get("/api/comercial/crm/empresas")).status_code == 401


async def test_api_crud_e_ficha(logado):
    h = _csrf(logado)
    r = await logado.post("/api/comercial/crm/empresa", json={"campos": {"nome": "Aurora"}}, headers=h)
    assert r.status_code == 201
    emp = r.json()["id"]

    r = await logado.patch(f"/api/comercial/crm/empresa/{emp}", json={"campos": {"status": "cliente"}}, headers=h)
    assert r.status_code == 200
    assert next(c for c in r.json()["campos"] if c["campo"] == "status")["exibicao"] == "cliente"

    r = await logado.patch(f"/api/comercial/crm/empresa/{emp}", json={"campos": {"status": "xpto"}}, headers=h)
    assert r.status_code == 422

    neg = (await logado.post("/api/comercial/crm/negocio", json={"campos": {"empresa_id": emp}}, headers=h)).json()["id"]
    r = await logado.post(f"/api/comercial/crm/negocio/{neg}/mover", json={"para": "proposta"}, headers=h)
    assert r.status_code == 409
    r = await logado.post(f"/api/comercial/crm/negocio/{neg}/mover", json={"para": "contatado"}, headers=h)
    assert r.status_code == 200

    assert (await logado.delete(f"/api/comercial/crm/negocio/{neg}", headers=h)).status_code == 409
    r = await logado.post(f"/api/comercial/crm/negocio/{neg}/registrar", json={"texto": "nota"}, headers=h)
    assert r.status_code == 200

    lista = (await logado.get("/api/comercial/crm/empresas")).json()
    assert lista["total"] == 1 and lista["itens"][0]["n_negocios"] == 1
    negocios = (await logado.get("/api/comercial/crm/negocios")).json()
    assert negocios[0]["empresa_nome"] == "Aurora" and "respondeu" in negocios[0]["pode_ir"]
    assert (await logado.get("/api/comercial/crm/painel")).json()["negocios_abertos"] == 1
    assert (await logado.get("/api/comercial/crm/empresa/999")).status_code == 404

    async with get_session() as s:
        assert [i.texto for i in await s.scalars(select(Interacao))] == ["nota"]
