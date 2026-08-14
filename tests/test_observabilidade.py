"""Observabilidade: grava sempre, e nunca derruba quem chamou."""
from app.db.observability import (
    AiCallRecord,
    registrar_ai_call,
    registrar_evento,
    stats,
)


async def test_registra_chamada_e_soma_nas_stats():
    await registrar_ai_call(
        AiCallRecord(
            agente="candidatura",
            tarefa="redigir",
            provider="ollama",
            modelo="qwen3:4b",
            prompt="p",
            resposta="r",
            tokens_input=100,
            tokens_output=50,
            latencia_ms=1200,
            alvo_ref="vaga:abc",
        )
    )
    s = await stats()
    assert s["ai_calls_total"] == 1
    assert s["tokens_total"] == 150
    assert s["latencia_media_ms"] == 1200
    # Modelo local não tem preço cadastrado → custo estimado zero.
    assert s["custo_usd_estimado"] == 0.0


async def test_registra_falha():
    await registrar_ai_call(
        AiCallRecord(provider="ollama", modelo="qwen3:8b", sucesso=False, erro="timeout")
    )
    s = await stats()
    assert s["ai_calls_falhas"] == 1


async def test_registra_evento_de_pipeline():
    await registrar_evento("ingestao", status="ok", duracao_ms=42, alvo_ref="obsidian:nota.md")
    assert (await stats())["pipeline_events_total"] == 1


async def test_nao_guarda_payload_quando_desligado(monkeypatch):
    from app.config import settings
    from app.db.models.ai_call import AiCall
    from app.db.session import get_session

    monkeypatch.setattr(settings, "observ_store_payloads", False)
    await registrar_ai_call(
        AiCallRecord(provider="ollama", modelo="qwen3:4b", prompt="segredo", resposta="segredo")
    )

    async with get_session() as session:
        from sqlalchemy import select

        call = await session.scalar(select(AiCall))
    assert call.prompt is None
    assert call.resposta is None
    # As métricas continuam: o que se perde é só o conteúdo.
    assert call.prompt_chars == len("segredo")
