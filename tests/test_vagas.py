"""Vagas: entrada por texto colado, histórico e follow-up vencido.

O follow-up é o teste que representa a fase: é a coisa que eu nunca faço à mão
e a única que justifica o sistema existir para além de gerar PDF.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.candidatura import vagas
from app.db.models.pessoal.candidatura_evento import CandidaturaEvento
from app.db.session import get_session

JD = """Pessoa Engenheira de Dados Pleno
A Acme busca alguém para construir pipelines de dados.
Requisitos: Python, Airflow, SQL avançado. Desejável: dbt, Terraform.
Envie seu currículo para vagas@acme.dev
"""


async def nova(**kw):
    return await vagas.criar(**{"descricao": JD, **kw})


async def test_colar_a_vaga_basta():
    v = await nova()
    assert v.status == "quero_candidatar"
    # Título e e-mail saem do texto — regex, não LLM.
    assert v.titulo == "Pessoa Engenheira de Dados Pleno"
    assert v.contato_email == "vagas@acme.dev"


async def test_titulo_explicito_vence_o_chute():
    v = await nova(titulo="Engenheiro de Dados Pleno (LinkedIn)")
    assert v.titulo == "Engenheiro de Dados Pleno (LinkedIn)"


async def test_descricao_curta_e_recusada():
    with pytest.raises(vagas.VagaErro):
        await vagas.criar(descricao="vaga de dev")


async def test_criar_ja_registra_o_primeiro_evento():
    v = await nova()
    assert [e.evento for e in await vagas.historico(v.id)] == ["salva"]


async def test_evento_move_o_status():
    v = await nova()
    await vagas.registrar_evento(v.id, "enviada")
    assert (await vagas.obter(v.id)).status == "candidatei"

    await vagas.registrar_evento(v.id, "respondida", detalhe="pediram teste técnico")
    assert (await vagas.obter(v.id)).status == "respondeu"

    await vagas.registrar_evento(v.id, "entrevista")
    assert (await vagas.obter(v.id)).status == "entrevista"


async def test_evento_que_nao_move_status():
    v = await nova()
    await vagas.registrar_evento(v.id, "enviada")
    await vagas.registrar_evento(v.id, "visualizada")
    # Visualizar é informação, não progresso.
    assert (await vagas.obter(v.id)).status == "candidatei"


async def test_evento_desconhecido_e_erro():
    v = await nova()
    with pytest.raises(vagas.VagaErro, match="desconhecido"):
        await vagas.registrar_evento(v.id, "quase_contratado")


async def test_historico_em_ordem():
    v = await nova()
    for e in ("analisada", "gerada", "enviada"):
        await vagas.registrar_evento(v.id, e)
    assert [e.evento for e in await vagas.historico(v.id)] == [
        "salva", "analisada", "gerada", "enviada",
    ]


async def envelhecer(vaga_id, dias: int) -> None:
    """Empurra os eventos da vaga para o passado."""
    async with get_session() as s:
        await s.execute(
            update(CandidaturaEvento)
            .where(CandidaturaEvento.vaga_id == vaga_id)
            .values(ocorreu_em=datetime.now(UTC) - timedelta(days=dias))
        )
        await s.commit()


async def test_followup_vencido_pega_o_que_esta_parado():
    antiga = await nova()
    await vagas.registrar_evento(antiga.id, "enviada")
    await envelhecer(antiga.id, 10)

    recente = await nova(titulo="Outra")
    await vagas.registrar_evento(recente.id, "enviada")

    vencidas = await vagas.followup_vencido()
    assert [v.id for v, _ in vencidas] == [antiga.id]
    assert vencidas[0][1] >= 7


async def test_quem_respondeu_sai_do_followup():
    v = await nova()
    await vagas.registrar_evento(v.id, "enviada")
    await vagas.registrar_evento(v.id, "respondida")
    await envelhecer(v.id, 30)

    # Já respondeu: cobrar de novo seria insistência, não follow-up.
    assert await vagas.followup_vencido() == []


async def test_marcar_sem_retorno_e_idempotente():
    v = await nova()
    await vagas.registrar_evento(v.id, "enviada")
    await envelhecer(v.id, 10)

    assert await vagas.marcar_sem_retorno() == 1
    # O worker roda todo dia; marcar de novo encheria o histórico de ruído.
    assert await vagas.marcar_sem_retorno() == 0

    async with get_session() as s:
        eventos = (await s.scalars(select(CandidaturaEvento.evento))).all()
    assert eventos.count("sem_retorno") == 1


async def test_listar_ordena_por_aderencia():
    baixa = await nova(titulo="Baixa")
    alta = await nova(titulo="Alta")
    async with get_session() as s:
        from app.db.models.pessoal.vaga import Vaga

        await s.execute(update(Vaga).where(Vaga.id == alta.id).values(match_score=90))
        await s.execute(update(Vaga).where(Vaga.id == baixa.id).values(match_score=20))
        await s.commit()

    total, itens = await vagas.listar()
    assert total == 2 and itens[0].titulo == "Alta"
