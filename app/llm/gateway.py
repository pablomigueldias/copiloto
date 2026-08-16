"""O ponto único de LLM do sistema.

Nenhum agente fala com o Ollama direto: todo mundo passa por `gerar()`. Foi a
ausência disso no repo antigo que produziu quatro caminhos diferentes de
chamada, dos quais só um gravava observabilidade — justamente o pago, deixando
cego o caminho que mais erra.

Cinco responsabilidades, nesta ordem:

1. roteamento por tarefa      — o modelo certo, sem o chamador saber o nome dele
2. semáforo global            — uma inferência por vez nos 6 GB da 2060
3. JSON com retry e reprompt  — devolve dict válido ou erro explícito
4. circuit breaker por modelo — Ollama caído não vira 200 timeouts em fila
5. observabilidade sempre     — sucesso e falha, com o número de tentativas
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.db.observability import AiCallRecord, registrar_ai_call
from app.llm.json_extract import extrair_json
from app.llm.providers.ollama import OllamaProvider
from app.llm.tipos import (
    JSONInvalido,
    LLMCircuitoAberto,
    LLMErro,
    LLMIndisponivel,
    LLMResult,
    Provider,
    Rota,
    Tarefa,
)
from app.utils.logger import get_logger

logger = get_logger()

# Uma inferência por vez. Duas chamadas concorrentes em 6 GB não ficam lentas:
# uma delas escorrega para a RAM e o tempo explode uma ordem de grandeza. O
# semáforo é de processo — quando o worker da F4 chegar, o limite continua
# valendo porque a GPU é uma só (daí NUM_PARALLEL=1 no servidor também).
_semaforo = asyncio.Semaphore(1)

_provider: Provider = OllamaProvider()


def usar_provider(p: Provider) -> None:
    """Troca o provider — usado pelos testes e pelo bake-off."""
    global _provider
    _provider = p


def rota(tarefa: Tarefa) -> Rota:
    """Qual modelo atende cada tarefa.

    Tabela lida do settings a cada chamada, e não congelada no import: trocar
    de modelo é editar o `.env` e reiniciar, nunca mexer em código.
    """
    if tarefa in ("classificar", "extrair"):
        # Saída estruturada, temperatura baixa: aqui criatividade é defeito.
        return Rota(modelo=settings.ollama_model_extracao, json_mode=True, temperatura=0.1)
    if tarefa == "compreender":
        # Também devolve JSON, mas a semelhança para aí: "extrair" é achar o que
        # está escrito, e isto é **ler 3.000 palavras e dizer do que elas
        # tratam**. Medido no fichamento de uma aula de 26 min: o phi4-mini
        # (2,5 GB) propôs 2 destaques e um título que repetia a mesma palavra
        # duas vezes; o llama3.1:8b propôs 5 fatos com os símbolos certos. Custa
        # 37 s contra 7 s, numa nota que já leva 3 min de reescrita.
        return Rota(modelo=settings.ollama_model_pesado, json_mode=True, temperatura=0.1)
    return Rota(modelo=settings.ollama_model_redacao, temperatura=0.7)


# ── Circuit breaker ───────────────────────────────────────────────
# Generaliza o `_bloquear_gemini_hoje()` do repo antigo. Lá o bloqueio durava o
# dia porque a causa era cota de API. Aqui a causa é Ollama derrubado ou OOM de
# VRAM — some em minutos, então o circuito também.


@dataclass(slots=True)
class _Breaker:
    falhas: int = 0
    aberto_ate: datetime | None = None


_breakers: dict[str, _Breaker] = {}


def _checar_breaker(modelo: str) -> None:
    b = _breakers.get(modelo)
    if b and b.aberto_ate and datetime.now(UTC) < b.aberto_ate:
        raise LLMCircuitoAberto(
            f"Circuito aberto para '{modelo}' até {b.aberto_ate:%H:%M:%S} "
            f"({b.falhas} falhas seguidas)"
        )


def _registrar_falha(modelo: str) -> None:
    b = _breakers.setdefault(modelo, _Breaker())
    b.falhas += 1
    if b.falhas >= settings.llm_breaker_falhas:
        b.aberto_ate = datetime.now(UTC) + timedelta(minutes=settings.llm_breaker_minutos)
        logger.warning(
            f"Circuito ABERTO para '{modelo}' por {settings.llm_breaker_minutos} min "
            f"após {b.falhas} falhas seguidas"
        )


def _registrar_sucesso(modelo: str) -> None:
    _breakers.pop(modelo, None)


def resetar_breakers() -> None:
    _breakers.clear()


# ── Validação do JSON ─────────────────────────────────────────────


def _validar_schema(dado: dict | list, schema: dict) -> str | None:
    """Checagem mínima de forma. Devolve a queixa, ou None se está bom.

    Não é JSON Schema completo de propósito: o que o retry precisa saber é
    "faltou chave" ou "veio do tipo errado". Sem isso, `{"erro": "não sei"}`
    passa como sucesso — que era exatamente o buraco do repo antigo.
    """
    obrigatorias = schema.get("required") or list((schema.get("properties") or {}).keys())
    if not isinstance(dado, dict):
        return "a resposta precisa ser um objeto JSON, não uma lista"

    faltando = [k for k in obrigatorias if k not in dado]
    if faltando:
        return f"faltam as chaves obrigatórias: {', '.join(faltando)}"

    tipos = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for chave, regra in (schema.get("properties") or {}).items():
        esperado = tipos.get(regra.get("type", ""))
        if esperado and chave in dado and not isinstance(dado[chave], esperado):
            return f"a chave '{chave}' deveria ser {regra['type']}"
    return None


def _desembrulhar(dado: dict | list, schema: dict) -> dict | list:
    """Tira o envelope que o modelo pequeno adora inventar.

    Pedido `{senioridade, requisitos}`, o phi4-mini devolve
    `{"vaga": {"senioridade": ..., "requisitos": ...}}` com teimosia — e
    reprompt não resolve, porque com temperatura baixa ele repete a mesma
    resposta. É regra, não julgamento: se o objeto tem uma única chave e lá
    dentro estão as chaves pedidas, o envelope some aqui mesmo.
    """
    if not isinstance(dado, dict) or len(dado) != 1:
        return dado
    obrigatorias = schema.get("required") or list((schema.get("properties") or {}).keys())
    (interno,) = dado.values()
    if isinstance(interno, dict) and any(k in interno for k in obrigatorias):
        return interno
    return dado


def _reprompt(prompt: str, saida: str, queixa: str, schema: dict | None) -> str:
    partes = [
        prompt,
        "\n\n---\nSua resposta anterior foi rejeitada.",
        f"Você respondeu:\n{saida[:1500]}",
        f"Problema: {queixa}",
        "Responda AGORA apenas com o JSON válido, com as chaves pedidas no nível "
        "raiz (sem envelope), sem texto antes ou depois, sem cerca de código e "
        "sem comentários.",
    ]
    if schema:
        partes.insert(-1, f"O formato exigido é:\n{json.dumps(schema, ensure_ascii=False)}")
    return "\n".join(partes)


# ── Gateway ───────────────────────────────────────────────────────


@dataclass(slots=True)
class _Tentativa:
    texto: str = ""
    queixa: str = ""
    campos: dict = field(default_factory=dict)


async def gerar(
    prompt: str,
    *,
    tarefa: Tarefa,
    agente: str,
    json_schema: dict | None = None,
    max_tentativas: int | None = None,
    alvo_ref: str | None = None,
    modelo: str | None = None,
    temperatura: float | None = None,
) -> LLMResult:
    """Gera texto (ou JSON) com o modelo da tarefa.

    Levanta `JSONInvalido` se pediram JSON e o modelo não entregou depois dos
    reprompts, e `LLMIndisponivel` se o servidor não respondeu. Nunca devolve
    resultado meio-válido: quem chama trata a exceção ou confia no retorno.
    """
    r = rota(tarefa)
    modelo_usado = modelo or r.modelo
    quer_json = json_schema is not None
    tentativas_max = max_tentativas or settings.llm_max_tentativas

    _checar_breaker(modelo_usado)

    t0 = time.perf_counter()
    ultimo = _Tentativa()
    resultado: LLMResult | None = None
    erro: Exception | None = None
    tentativa = 0
    prompt_atual = prompt

    async with _semaforo:
        while tentativa < tentativas_max:
            tentativa += 1
            base = temperatura if temperatura is not None else r.temperatura
            try:
                cru = await _provider.gerar(
                    prompt_atual,
                    modelo=modelo_usado,
                    json_mode=quer_json or r.json_mode,
                    # Sobe a cada retentativa: com temperatura 0.1 o modelo
                    # devolve exatamente a mesma resposta errada, e o retry vira
                    # três vezes o mesmo custo pelo mesmo erro.
                    temperatura=(
                        None if base is None else min(base + 0.2 * (tentativa - 1), 0.9)
                    ),
                    opcoes=r.opcoes or None,
                )
            except LLMIndisponivel as e:
                # Servidor fora não melhora com reprompt: falha na hora.
                erro = e
                break

            ultimo = _Tentativa(
                texto=cru.texto,
                campos={
                    "tokens_input": cru.tokens_input,
                    "tokens_output": cru.tokens_output,
                    "finish_reason": cru.finish_reason,
                    "thinking_chars": len(cru.thinking),
                },
            )

            if not quer_json:
                if not cru.texto.strip():
                    ultimo.queixa = "resposta vazia"
                    continue
                resultado = LLMResult(
                    texto=cru.texto,
                    modelo=modelo_usado,
                    latencia_ms=int((time.perf_counter() - t0) * 1000),
                    tentativas=tentativa,
                    **ultimo.campos,
                )
                break

            dado = extrair_json(cru.texto)
            if dado is not None:
                dado = _desembrulhar(dado, json_schema)
            queixa = "não veio JSON válido" if dado is None else _validar_schema(dado, json_schema)
            if queixa:
                ultimo.queixa = queixa
                logger.warning(
                    f"[{agente}/{tarefa}] JSON rejeitado na tentativa {tentativa}: {queixa}"
                )
                prompt_atual = _reprompt(prompt, cru.texto, queixa, json_schema)
                continue

            resultado = LLMResult(
                texto=cru.texto,
                json=dado,
                modelo=modelo_usado,
                latencia_ms=int((time.perf_counter() - t0) * 1000),
                tentativas=tentativa,
                **ultimo.campos,
            )
            break

    if resultado is None and erro is None:
        erro = JSONInvalido(
            f"{tentativas_max} tentativas sem JSON válido ({ultimo.queixa}). "
            f"Última saída: {ultimo.texto[:300]!r}"
        )

    latencia = int((time.perf_counter() - t0) * 1000)

    # Grava em todo desfecho. Uma falha de LLM que não deixa rastro é uma hora
    # de depuração depois.
    await registrar_ai_call(
        AiCallRecord(
            agente=agente,
            tarefa=tarefa,
            provider=getattr(_provider, "nome", "?"),
            modelo=modelo_usado,
            prompt=prompt,
            resposta=ultimo.texto or None,
            tokens_input=ultimo.campos.get("tokens_input"),
            tokens_output=ultimo.campos.get("tokens_output"),
            latencia_ms=latencia,
            sucesso=erro is None,
            finish_reason=ultimo.campos.get("finish_reason"),
            erro=f"{type(erro).__name__}: {erro}" if erro else None,
            alvo_ref=alvo_ref,
        )
    )

    if erro is not None:
        _registrar_falha(modelo_usado)
        raise erro

    _registrar_sucesso(modelo_usado)
    assert resultado is not None
    return resultado


async def embedar(textos: list[str], *, modelo: str | None = None) -> list[list[float]]:
    """Vetores para o RAG. Em lote — uma chamada por texto seria absurdo."""
    async with _semaforo:
        return await _provider.embedar(textos, modelo=modelo or settings.ollama_model_embedding)


__all__ = [
    "JSONInvalido",
    "LLMErro",
    "LLMIndisponivel",
    "LLMResult",
    "embedar",
    "gerar",
    "rota",
    "usar_provider",
]
