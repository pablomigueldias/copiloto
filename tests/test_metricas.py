"""O painel — contar é trabalho de banco, não de LLM.

O teste mais importante é o dos gaps frequentes: é ele que transforma trinta
candidaturas numa lista de estudo, e é a única métrica aqui que muda o que o
Pablo faz na semana seguinte.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.candidatura import metricas, vagas
from app.db.models.pessoal.candidatura_evento import CandidaturaEvento
from app.db.models.pessoal.vaga import Vaga
from app.db.session import get_session

JD = "Vaga de dados com Python, Airflow e SQL. Envie para vagas@acme.dev. " * 2


@pytest.fixture(autouse=True)
def sem_llm():
    from app.llm import gateway

    class Falso:
        nome = "falso"

        async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
            raise AssertionError("métricas não geram texto")

        async def embedar(self, textos, *, modelo):
            return [[0.01] * 1024 for _ in textos]

    gateway.usar_provider(Falso())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


async def vaga_com(eventos: list[str], *, titulo="Vaga", gaps=None, score=None):
    v = await vagas.criar(descricao=JD, titulo=titulo)
    for e in eventos:
        await vagas.registrar_evento(v.id, e)
    if gaps is not None or score is not None:
        async with get_session() as s:
            await s.execute(
                update(Vaga).where(Vaga.id == v.id).values(
                    match_json={"gaps": gaps or [], "destaques": []}, match_score=score
                )
            )
            await s.commit()
    return v


async def envelhecer(vaga_id, dias: int):
    async with get_session() as s:
        await s.execute(
            update(CandidaturaEvento)
            .where(CandidaturaEvento.vaga_id == vaga_id)
            .values(ocorreu_em=datetime.now(UTC) - timedelta(days=dias))
        )
        await s.commit()


async def test_funil_conta_quem_chegou_em_cada_etapa():
    await vaga_com(["analisada", "gerada", "enviada", "respondida"], titulo="Respondeu")
    await vaga_com(["analisada", "gerada", "enviada"], titulo="Enviou")
    await vaga_com(["analisada"], titulo="Só analisou")

    m = await metricas.calcular()
    # 'salva' nasce com a vaga; as outras etapas contam quem passou por lá.
    assert m.funil["salva"] == 3
    assert m.funil["analisada"] == 3
    assert m.funil["enviada"] == 2
    assert m.funil["respondida"] == 1


async def test_taxa_de_resposta():
    await vaga_com(["enviada", "respondida"])
    await vaga_com(["enviada"])
    await vaga_com(["enviada"])
    await vaga_com(["enviada"])

    m = await metricas.calcular()
    assert m.taxa_resposta == 25.0


async def test_taxa_de_resposta_sem_envio_e_nula():
    await vaga_com(["analisada"])
    assert (await metricas.calcular()).taxa_resposta is None


async def test_dias_ate_a_resposta_so_conta_quem_respondeu():
    v = await vaga_com(["enviada"])
    await envelhecer(v.id, 4)
    await vagas.registrar_evento(v.id, "respondida")
    # Uma que nunca respondeu não pode puxar a média para o infinito.
    parada = await vaga_com(["enviada"])
    await envelhecer(parada.id, 60)

    m = await metricas.calcular()
    assert 3.5 <= m.dias_ate_resposta <= 4.5


async def test_gaps_frequentes_viram_lista_de_estudo():
    await vaga_com(["analisada"], gaps=["Kubernetes", "Inglês"])
    await vaga_com(["analisada"], gaps=["kubernetes", "Terraform"])
    await vaga_com(["analisada"], gaps=["Kubernetes"])

    (primeiro, *resto) = (await metricas.calcular()).gaps_frequentes
    # Apareceu em 3 de 3 vagas: virou dado sobre o mercado, não opinião.
    assert primeiro == {"requisito": "kubernetes", "vezes": 3, "das_vagas": 100}
    assert {g["requisito"] for g in resto} == {"inglês", "terraform"}


async def test_paradas_lista_o_que_caiu_do_radar():
    esquecida = await vaga_com(["analisada"], titulo="Esquecida")
    await envelhecer(esquecida.id, 30)
    await vaga_com(["analisada"], titulo="Recente")

    m = await metricas.calcular()
    assert [p["titulo"] for p in m.paradas] == ["Esquecida"]
    assert m.paradas[0]["parada_ha_dias"] >= 14


async def test_vaga_encerrada_nao_conta_como_parada():
    v = await vaga_com(["enviada", "recusada"], titulo="Recusada")
    await envelhecer(v.id, 40)
    assert (await metricas.calcular()).paradas == []


async def test_score_medio_e_followup():
    a = await vaga_com(["enviada"], score=80)
    await vaga_com(["analisada"], score=40)
    await envelhecer(a.id, 10)

    m = await metricas.calcular()
    assert m.score_medio == 60.0
    assert m.followup_vencido == 1


async def test_painel_vazio_nao_explode():
    m = await metricas.calcular()
    assert m.funil["salva"] == 0 and m.taxa_resposta is None and m.gaps_frequentes == []
