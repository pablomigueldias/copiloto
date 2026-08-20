"""Observabilidade: grava sempre, e nunca derruba quem chamou."""
from datetime import date

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
    # Local custa zero de verdade — e isso é diferente de "não sei quanto foi".
    assert s["custo_usd_estimado"] == 0.0
    assert s["ai_calls_sem_preco"] == 0


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


# ── Custo: zero, um número, ou não sei (§6.2 da Fase C) ───────────


def test_local_custa_zero_e_externo_desconhecido_custa_none():
    from app.db.observability import _estimar_custo

    assert _estimar_custo("ollama", "gemma4:e4b", 1000, 500) == 0.0
    # Modelo de fora que não está na tabela: NÃO é zero, é desconhecido.
    assert _estimar_custo("gemini", "modelo-que-nao-existe", 1000, 500) is None


def test_preco_do_pro_bate_com_a_tabela_do_google():
    from app.db.observability import _estimar_custo

    # 100k de entrada a $1,25/1M + 100k de saída a $10,00/1M — dentro da faixa
    # barata, que é onde vive uma chamada de currículo (22.664 tokens no total).
    assert _estimar_custo("gemini", "gemini-2.5-pro", 100_000, 100_000) == 1.125


def test_prompt_longo_paga_a_faixa_cara():
    from app.db.observability import PRECOS_USD_1M

    pro = PRECOS_USD_1M["gemini-2.5-pro"]
    dia = date(2026, 8, 20)
    # 200k é o limite: em cima dele ainda é a faixa barata.
    assert pro.custo(200_000, 0, dia=dia) == round(0.2 * 1.25, 6)
    # Um token acima, a entrada dobra.
    assert pro.custo(200_001, 0, dia=dia) > 0.2 * 2.50


def test_promocao_do_flash_expira_sozinha():
    from app.db.observability import PRECOS_USD_1M

    flash = PRECOS_USD_1M["gemini-3.7-flash"]
    # O preço promocional vale até 31/12/2026; em 2027 é o dobro, sem ninguém
    # tocar em código.
    assert flash.custo(1_000_000, 0, dia=date(2026, 12, 31)) == 0.75
    assert flash.custo(1_000_000, 0, dia=date(2027, 1, 1)) == 1.50


async def test_chamada_externa_sem_preco_nao_vira_zero():
    await registrar_ai_call(
        AiCallRecord(
            provider="gemini", modelo="gemini-do-futuro",
            tokens_input=1000, tokens_output=500,
        )
    )
    s = await stats()
    # Nenhuma chamada precificada: o painel diz "não sei", não "custou nada".
    assert s["custo_usd_estimado"] is None
    assert s["ai_calls_sem_preco"] == 1


async def test_soma_o_que_tem_preco_e_conta_o_que_falta():
    for rec in (
        AiCallRecord(provider="gemini", modelo="gemini-2.5-pro",
                     tokens_input=100_000, tokens_output=100_000),
        AiCallRecord(provider="gemini", modelo="gemini-do-futuro",
                     tokens_input=10, tokens_output=10),
    ):
        await registrar_ai_call(rec)

    s = await stats()
    assert s["custo_usd_estimado"] == 1.125
    assert s["ai_calls_sem_preco"] == 1
