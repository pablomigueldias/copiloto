"""O gateway, contra um provider falso.

De propósito sem Ollama: teste que só passa com o modelo no ar é integração
disfarçada — lento, instável e mudo sobre a lógica que se quer garantir. O
modelo de verdade é exercitado pelos scripts (`bench_modelos`, `bakeoff`).
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.ai_call import AiCall
from app.db.session import get_session
from app.llm import gateway
from app.llm.tipos import JSONInvalido, LLMCircuitoAberto, LLMIndisponivel, RespostaCrua

SCHEMA = {
    "type": "object",
    "required": ["senioridade", "requisitos"],
    "properties": {
        "senioridade": {"type": "string"},
        "requisitos": {"type": "array"},
    },
}


class ProviderFalso:
    """Devolve respostas de uma fila; guarda o que recebeu."""

    nome = "falso"

    def __init__(self, respostas: list[str | Exception]) -> None:
        self.respostas = list(respostas)
        self.prompts: list[str] = []
        self.modelos: list[str] = []
        self.concorrentes = 0
        self.pico_concorrencia = 0
        self.atraso = 0.0

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.concorrentes += 1
        self.pico_concorrencia = max(self.pico_concorrencia, self.concorrentes)
        try:
            if self.atraso:
                await asyncio.sleep(self.atraso)
            self.prompts.append(prompt)
            self.modelos.append(modelo)
            r = self.respostas.pop(0) if self.respostas else '{"ok": true}'
            if isinstance(r, Exception):
                raise r
            return RespostaCrua(texto=r, modelo=modelo, tokens_input=10, tokens_output=5)
        finally:
            self.concorrentes -= 1

    async def embedar(self, textos, *, modelo):
        return [[0.1] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def _limpar():
    gateway.resetar_breakers()
    yield
    gateway.usar_provider(gateway.OllamaProvider())
    gateway.resetar_breakers()


def usar(respostas) -> ProviderFalso:
    p = ProviderFalso(respostas)
    gateway.usar_provider(p)
    return p


# ── Roteamento ────────────────────────────────────────────────────


async def test_extrair_e_classificar_vao_para_o_modelo_de_extracao():
    p = usar(['{"senioridade": "pleno", "requisitos": []}'] * 2)
    await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    await gateway.gerar("x", tarefa="classificar", agente="t", json_schema=SCHEMA)
    assert p.modelos == [settings.ollama_model_extracao] * 2


async def test_redigir_e_resumir_vao_para_o_modelo_de_redacao():
    p = usar(["um texto qualquer", "outro texto"])
    await gateway.gerar("x", tarefa="redigir", agente="t")
    await gateway.gerar("x", tarefa="resumir", agente="t")
    assert p.modelos == [settings.ollama_model_redacao] * 2


async def test_modelo_explicito_ganha_da_rota():
    p = usar(["texto"])
    await gateway.gerar("x", tarefa="redigir", agente="t", modelo="modelo-do-bakeoff")
    assert p.modelos == ["modelo-do-bakeoff"]


# ── JSON, retry e reprompt ────────────────────────────────────────


async def test_json_sujo_e_limpo_sem_gastar_tentativa():
    usar(['```json\n{"senioridade": "junior", "requisitos": ["python"]}\n```'])
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.json == {"senioridade": "junior", "requisitos": ["python"]}
    assert r.tentativas == 1


async def test_reprompt_ate_o_modelo_acertar():
    p = usar(
        [
            "desculpe, não entendi",  # nem JSON é
            '{"senioridade": "pleno"}',  # falta chave obrigatória
            '{"senioridade": "pleno", "requisitos": ["fastapi"]}',
        ]
    )
    r = await gateway.gerar("Extraia da vaga", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.tentativas == 3
    assert r.json["requisitos"] == ["fastapi"]
    # O reprompt precisa dizer O QUE deu errado — senão o modelo repete o erro.
    assert "não veio JSON válido" in p.prompts[1]
    assert "requisitos" in p.prompts[2]
    assert "Extraia da vaga" in p.prompts[2]


async def test_chave_do_tipo_errado_e_rejeitada():
    p = usar(
        [
            '{"senioridade": ["pleno"], "requisitos": []}',
            '{"senioridade": "pleno", "requisitos": []}',
        ]
    )
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.tentativas == 2
    assert "deveria ser string" in p.prompts[1]


async def test_envelope_inventado_e_removido_sem_gastar_retry():
    # Caso real do phi4-mini: pedem {senioridade, requisitos}, ele devolve
    # tudo dentro de {"vaga": {...}}.
    usar(['{"vaga": {"senioridade": "pleno", "requisitos": ["python"]}}'])
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.tentativas == 1
    assert r.json == {"senioridade": "pleno", "requisitos": ["python"]}


async def test_objeto_de_uma_chave_legitimo_nao_e_desembrulhado():
    schema = {"type": "object", "required": ["resultado"]}
    usar(['{"resultado": {"a": 1}}'])
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=schema)
    assert r.json == {"resultado": {"a": 1}}


async def test_temperatura_sobe_a_cada_retentativa():
    # Com temperatura baixa o modelo repete a mesma resposta errada, e o retry
    # vira três vezes o mesmo custo pelo mesmo erro.
    class Espia(ProviderFalso):
        temperaturas: list[float | None] = []

        async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
            self.temperaturas.append(temperatura)
            return await super().gerar(
                prompt, modelo=modelo, json_mode=json_mode, temperatura=temperatura
            )

    p = Espia(["lixo", "lixo", '{"senioridade": "x", "requisitos": []}'])
    p.temperaturas = []
    gateway.usar_provider(p)
    await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert p.temperaturas == sorted(p.temperaturas)
    assert p.temperaturas[0] < p.temperaturas[-1]


async def test_desiste_com_erro_explicito():
    usar(["não sei", "também não", "desisto"])
    with pytest.raises(JSONInvalido):
        await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)


async def test_texto_livre_nao_passa_pelo_parser():
    usar(["Olá, tudo bem? Segue o retorno que combinamos."])
    r = await gateway.gerar("x", tarefa="redigir", agente="t")
    assert r.json is None
    assert r.texto.startswith("Olá")


async def test_resposta_vazia_conta_como_tentativa():
    # É o caso real do modelo com raciocínio: gasta o orçamento pensando e
    # devolve `response` vazio.
    usar(["", "   ", "agora sim"])
    r = await gateway.gerar("x", tarefa="redigir", agente="t")
    assert r.tentativas == 3
    assert r.texto == "agora sim"


# ── Indisponibilidade e breaker ───────────────────────────────────


async def test_servidor_fora_falha_na_hora_sem_reprompt():
    p = usar([LLMIndisponivel("conexão recusada")] * 3)
    with pytest.raises(LLMIndisponivel):
        await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert len(p.prompts) == 1  # não insiste com quem está fora do ar


async def test_breaker_abre_apos_o_limite_de_falhas():
    usar([LLMIndisponivel("fora")] * 10)
    for _ in range(settings.llm_breaker_falhas):
        with pytest.raises(LLMIndisponivel):
            await gateway.gerar("x", tarefa="redigir", agente="t")

    with pytest.raises(LLMCircuitoAberto):
        await gateway.gerar("x", tarefa="redigir", agente="t")


async def test_sucesso_zera_a_contagem_de_falhas():
    usar([LLMIndisponivel("fora"), "voltou"])
    with pytest.raises(LLMIndisponivel):
        await gateway.gerar("x", tarefa="redigir", agente="t")
    await gateway.gerar("x", tarefa="redigir", agente="t")
    assert not gateway._breakers


# ── Observabilidade e concorrência ────────────────────────────────


async def test_grava_ai_call_no_sucesso():
    usar(["texto gerado"])
    await gateway.gerar("meu prompt", tarefa="redigir", agente="candidatura", alvo_ref="vaga:1")

    async with get_session() as s:
        call = await s.scalar(select(AiCall))
    assert call.sucesso is True
    assert call.agente == "candidatura"
    assert call.tarefa == "redigir"
    assert call.provider == "falso"
    assert call.alvo_ref == "vaga:1"
    assert call.tokens_total == 15


async def test_grava_ai_call_na_falha():
    usar(["lixo", "lixo", "lixo"])
    with pytest.raises(JSONInvalido):
        await gateway.gerar("p", tarefa="extrair", agente="vaga", json_schema=SCHEMA)

    async with get_session() as s:
        call = await s.scalar(select(AiCall))
    assert call.sucesso is False
    assert "JSONInvalido" in call.error_message
    # A última saída do modelo fica gravada — é por onde se descobre o porquê.
    assert call.resposta == "lixo"


async def test_semaforo_serializa_as_inferencias():
    p = usar(["a", "b", "c"])
    p.atraso = 0.05
    await asyncio.gather(
        *(gateway.gerar("x", tarefa="redigir", agente="t") for _ in range(3))
    )
    assert p.pico_concorrencia == 1


async def test_embedar_em_lote():
    usar([])
    vetores = await gateway.embedar(["a", "b", "c"])
    assert len(vetores) == 3
    assert len(vetores[0]) == 1024
