"""O worker — sem Redis no ar.

Job neste projeto é função fina que chama serviço, então o que se testa aqui é
justamente isso: que o job chama o serviço certo, mede, e não enche a
observabilidade de "nada aconteceu". O `arq` em si não é testado — é biblioteca.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.pipeline_event import PipelineEvent
from app.db.session import get_session
from app.fila import servico
from app.llm import gateway
from app.worker import jobs
from app.worker.main import WorkerSettings, _minutos

NOTA = "# Nota\n\n" + "Corpo com tamanho suficiente para virar um chunk de verdade. " * 5


class EmbedderFalso:
    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("worker não gera texto nestes jobs")

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture
def embedder():
    gateway.usar_provider(EmbedderFalso())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
def vault(tmp_path, monkeypatch):
    (tmp_path / "a.md").write_text(NOTA, encoding="utf-8")
    monkeypatch.setattr(settings, "conhecimento_fontes", f"nota:{tmp_path}")
    return tmp_path


async def eventos(nome: str) -> list[PipelineEvent]:
    async with get_session() as s:
        return list((await s.scalars(select(PipelineEvent).where(PipelineEvent.evento == nome))).all())


# ── Cron ──────────────────────────────────────────────────────────


def test_minutos_do_cron():
    assert _minutos(10) == {0, 10, 20, 30, 40, 50}
    assert _minutos(60) == {0}
    # Intervalo absurdo não vira cron quebrado.
    assert _minutos(0) == set(range(60))
    assert _minutos(999) == {0}


def test_worker_registra_os_jobs():
    nomes = {f.__name__ for f in WorkerSettings.functions}
    assert nomes == {"reindexar", "embedar_exemplos", "marcar_followup"}
    # A GPU é uma só: o worker nunca roda dois jobs ao mesmo tempo.
    assert WorkerSettings.max_jobs == 1


# ── reindexar ─────────────────────────────────────────────────────


async def test_reindexar_indexa_o_que_apareceu(vault, embedder):
    r = await jobs.reindexar({})
    assert r["mudou"] == 1 and r["erros"] == 0
    assert r["resumo"]["nota"]["chunks"] >= 1
    assert r["duracao_ms"] >= 0


async def test_reindexar_sem_mudanca_nao_polui_a_observabilidade(vault, embedder):
    await jobs.reindexar({})
    antes = len(await eventos("worker.reindexar"))

    r = await jobs.reindexar({})
    assert r["mudou"] == 0
    # Um job de 10 em 10 minutos que sempre grava são 144 linhas por dia
    # dizendo "nada aconteceu".
    assert len(await eventos("worker.reindexar")) == antes


async def test_reindexar_registra_quando_algo_muda(vault, embedder):
    await jobs.reindexar({})
    (vault / "b.md").write_text(NOTA + "outra coisa", encoding="utf-8")

    await jobs.reindexar({})
    assert [e.status for e in await eventos("worker.reindexar")] == ["ok", "ok"]


async def test_reindexar_pega_arquivo_apagado(vault, embedder):
    await jobs.reindexar({})
    (vault / "a.md").unlink()

    r = await jobs.reindexar({})
    assert r["resumo"]["nota"]["removidos"] == 1


# ── embedar_exemplos ──────────────────────────────────────────────


async def test_marcar_followup_pega_candidatura_esquecida(embedder):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.candidatura import vagas
    from app.db.models.pessoal.candidatura_evento import CandidaturaEvento

    v = await vagas.criar(descricao="Vaga de dados com Python e SQL. " * 3)
    await vagas.registrar_evento(v.id, "enviada")
    async with get_session() as s:
        await s.execute(
            update(CandidaturaEvento)
            .where(CandidaturaEvento.vaga_id == v.id)
            .values(ocorreu_em=datetime.now(UTC) - timedelta(days=10))
        )
        await s.commit()

    assert await jobs.marcar_followup({}) == 1
    # Roda todo dia: marcar de novo encheria o histórico de ruído.
    assert await jobs.marcar_followup({}) == 0


async def test_embedar_exemplos_preenche_o_que_a_aprovacao_deixou(embedder):
    acao = await servico.criar(
        agente="outreach", tipo="email_frio", titulo="Acme", texto_gerado="Texto meu."
    )
    await servico.decidir(acao.id, decisao="aprovar")

    assert await jobs.embedar_exemplos({}) == 1
    assert await jobs.embedar_exemplos({}) == 0
