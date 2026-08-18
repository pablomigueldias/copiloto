"""O ponto único de LLM do sistema.

Nenhum agente fala com o Ollama direto: todo mundo passa por `gerar()`. Foi a
ausência disso no repo antigo que produziu quatro caminhos diferentes de
chamada, dos quais só um gravava observabilidade — justamente o pago, deixando
cego o caminho que mais erra.

Seis responsabilidades, nesta ordem:

1. roteamento por tarefa      — o modelo certo, sem o chamador saber o nome dele
2. semáforo global            — uma inferência LOCAL por vez nos 6 GB da 2060
3. JSON com retry e reprompt  — devolve dict válido ou erro explícito
4. circuit breaker por modelo — Ollama caído não vira 200 timeouts em fila
5. queda para o local         — API fora do ar não faz perder a nota da aula
6. observabilidade sempre     — sucesso e falha, um registro por destino

## Sobre a §5, que é nova

O escape para API externa que o `tipos.py` previa desde a Fase 1 chegou, e
chegou pequeno: **uma tarefa**. `compreender` — o fichamento da transcrição — é
onde o modelo local não chegou, e a medida é de aula real (17/08/2026): mesmo
corpo, mesmo prompt, o llama3.1:8b enunciou "a negação de P ou Q é P e Q", uma
Lei de Morgan sem as negações. O resto continua na máquina, e sem chave no
`.env` **tudo** continua na máquina.

O chamador não sabe de nada disso. `gerar(tarefa="compreender")` é a mesma
linha de antes; o que mudou é para onde o gateway a leva, e para onde ele a
leva de volta quando a API responde 503.
"""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
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

# Uma inferência **local** por vez. Duas chamadas concorrentes em 6 GB não ficam
# lentas: uma delas escorrega para a RAM e o tempo explode uma ordem de
# grandeza. O semáforo é de processo — quando o worker da F4 chegar, o limite
# continua valendo porque a GPU é uma só (daí NUM_PARALLEL=1 no servidor também).
#
# Chamada de API **não** entra aqui: ela não disputa VRAM, e prendê-la no mesmo
# semáforo faria o fichamento de 9 s bloquear a reescrita do bloco seguinte —
# exatamente o que a Fase T desfez ao mover o trabalho para dentro da aula.
_semaforo = asyncio.Semaphore(1)

_providers: dict[str, Provider] = {"ollama": OllamaProvider()}
_forcado: Provider | None = None


def usar_provider(p: Provider | None) -> None:
    """Manda tudo para este provider — usado pelos testes e pelo bake-off.

    `None` devolve o roteamento normal. É um martelo de propósito: um teste que
    troca o provider quer que **nenhuma** chamada escape para a rede, inclusive
    a que a rota mandaria para fora.
    """
    global _forcado
    _forcado = p


def _obter(nome: str) -> Provider:
    if _forcado is not None:
        return _forcado
    if nome not in _providers:
        from app.llm.providers.gemini import GeminiProvider

        _providers[nome] = GeminiProvider()
    return _providers[nome]


def _casa(tarefa: Tarefa, agente: str | None, regras: list[str]) -> bool:
    """A regra bate pela tarefa exata ou por prefixo do agente.

    Dois critérios porque um não basta. `redigir` é a mesma tarefa em
    `conhecimento.transcricao.bloco3` (8× por aula, tem que ficar na GPU que a
    Fase T liberou) e em `candidatura.curriculo.experiencias` (o texto que vai
    para uma entrevista). O agente é o que os separa.
    """
    if tarefa in regras:
        return True
    return bool(agente) and any(agente.startswith(p) for p in regras)


def _sai_da_maquina(tarefa: Tarefa, agente: str | None) -> bool:
    """Só com chave configurada. Sem ela, o `.env` pode pedir o que quiser."""
    if not settings.gemini_api_key:
        return False
    return _casa(tarefa, agente, settings.gemini_tarefas_list) or _casa(
        tarefa, agente, settings.gemini_agentes_list
    )


def _modelo_de_fora(tarefa: Tarefa, agente: str | None) -> str:
    """Pesado onde errar custa caro; o padrão no resto."""
    if _casa(tarefa, agente, settings.gemini_pesado_list):
        return settings.gemini_model_pesado
    return settings.gemini_model


def rota(tarefa: Tarefa, agente: str | None = None) -> Rota:
    """Qual modelo atende cada tarefa.

    Tabela lida do settings a cada chamada, e não congelada no import: trocar
    de modelo é editar o `.env` e reiniciar, nunca mexer em código.

    A forma da tarefa (JSON ou não, temperatura) é decidida primeiro e vale para
    os dois providers — é propriedade da tarefa, não do servidor. Só depois o
    destino muda, se o `.env` mandar.
    """
    if tarefa in ("classificar", "extrair"):
        # Saída estruturada, temperatura baixa: aqui criatividade é defeito.
        r = Rota(modelo=settings.ollama_model_extracao, json_mode=True, temperatura=0.1)
    elif tarefa == "compreender":
        # Também devolve JSON, mas a semelhança para aí: "extrair" é achar o que
        # está escrito, e isto é **ler 3.000 palavras e dizer do que elas
        # tratam**. É a tarefa onde o modelo local não chegou: na aula de
        # 17/08/2026 o llama3.1:8b enunciou uma Lei de Morgan falsa. Ver
        # `settings.gemini_tarefas`.
        r = Rota(modelo=settings.ollama_model_pesado, json_mode=True, temperatura=0.1)
    else:
        r = Rota(modelo=settings.ollama_model_redacao, temperatura=0.7)

    if _sai_da_maquina(tarefa, agente):
        return replace(r, modelo=_modelo_de_fora(tarefa, agente), provider="gemini")
    return r


def rota_local(tarefa: Tarefa, agente: str | None = None) -> Rota:
    """A rota que valeria sem chave nenhuma — o destino da queda."""
    r = rota(tarefa, agente)
    if r.provider == "ollama":
        return r
    local = {
        "classificar": settings.ollama_model_extracao,
        "extrair": settings.ollama_model_extracao,
        "compreender": settings.ollama_model_pesado,
    }.get(tarefa, settings.ollama_model_redacao)
    return replace(r, modelo=local, provider="ollama")


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


async def _tentar(
    prompt: str,
    *,
    r: Rota,
    modelo_usado: str,
    agente: str,
    tarefa: Tarefa,
    json_schema: dict | None,
    tentativas_max: int,
    temperatura: float | None,
) -> tuple[LLMResult | None, Exception | None, _Tentativa]:
    """O laço de tentativas contra **um** destino. Não grava observabilidade.

    Separado de `gerar` porque agora existem dois destinos possíveis para a
    mesma chamada, e cada um precisa do seu próprio registro no `ai_calls` —
    uma falha da API que aparecesse no painel como sucesso do modelo local
    esconderia justamente o que se quer saber.
    """
    quer_json = json_schema is not None
    t0 = time.perf_counter()
    ultimo = _Tentativa()
    resultado: LLMResult | None = None
    erro: Exception | None = None
    tentativa = 0
    prompt_atual = prompt
    provider = _obter(r.provider)

    # Só o que disputa VRAM entra na fila. Ver o comentário do `_semaforo`.
    porteiro = _semaforo if r.provider == "ollama" else nullcontext()

    async with porteiro:
        while tentativa < tentativas_max:
            tentativa += 1
            base = temperatura if temperatura is not None else r.temperatura
            try:
                cru = await provider.gerar(
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

    if resultado is not None:
        resultado.latencia_ms = int((time.perf_counter() - t0) * 1000)
    return resultado, erro, ultimo


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
    reprompts, e `LLMIndisponivel` se nenhum destino respondeu. Nunca devolve
    resultado meio-válido: quem chama trata a exceção ou confia no retorno.

    **A queda para o local.** Quando a rota manda para fora, o modelo local
    entra como segundo destino se a API não responder. O 503 "high demand" do
    Gemini apareceu no primeiro teste desta integração — uma nota de aula não
    pode se perder porque um servidor de terceiro teve pico. A queda é só para
    `LLMIndisponivel`: JSON fora do schema é problema de prompt, e o modelo
    local erraria igual, mais devagar.
    """
    r = rota(tarefa, agente)
    tentativas_max = max_tentativas or settings.llm_max_tentativas

    destinos = [r]
    # `modelo=` explícito é o bake-off pedindo um modelo por nome. Cair para
    # outro seria medir a coisa errada.
    if r.provider != "ollama" and modelo is None:
        destinos.append(rota_local(tarefa, agente))

    erro_final: Exception | None = None
    for i, destino in enumerate(destinos):
        alvo = modelo or destino.modelo
        try:
            _checar_breaker(alvo)
        except LLMCircuitoAberto as e:
            # Circuito aberto não é motivo para desistir: é motivo para usar o
            # outro destino, que é justamente o que ele existe para permitir.
            erro_final = e
            continue

        t0 = time.perf_counter()
        resultado, erro, ultimo = await _tentar(
            prompt,
            r=destino,
            modelo_usado=alvo,
            agente=agente,
            tarefa=tarefa,
            json_schema=json_schema,
            tentativas_max=tentativas_max,
            temperatura=temperatura,
        )

        # Grava em todo desfecho, e um registro por destino. Uma falha de LLM
        # que não deixa rastro é uma hora de depuração depois.
        await registrar_ai_call(
            AiCallRecord(
                agente=agente,
                tarefa=tarefa,
                # Quem de fato atendeu, não quem a rota pediu: com o provider
                # forçado (teste, bake-off) os dois divergem, e o painel tem que
                # dizer a verdade sobre onde o token foi gasto.
                provider=getattr(_obter(destino.provider), "nome", destino.provider),
                modelo=alvo,
                prompt=prompt,
                resposta=ultimo.texto or None,
                tokens_input=ultimo.campos.get("tokens_input"),
                tokens_output=ultimo.campos.get("tokens_output"),
                latencia_ms=int((time.perf_counter() - t0) * 1000),
                sucesso=erro is None,
                finish_reason=ultimo.campos.get("finish_reason"),
                erro=f"{type(erro).__name__}: {erro}" if erro else None,
                alvo_ref=alvo_ref,
            )
        )

        if erro is None:
            _registrar_sucesso(alvo)
            assert resultado is not None
            return resultado

        _registrar_falha(alvo)
        erro_final = erro
        if not isinstance(erro, LLMIndisponivel):
            break
        if i + 1 < len(destinos):
            logger.warning(
                f"[{agente}/{tarefa}] {destino.provider} indisponível ({erro}); "
                f"caindo para o modelo local."
            )

    assert erro_final is not None
    raise erro_final


async def embedar(textos: list[str], *, modelo: str | None = None) -> list[list[float]]:
    """Vetores para o RAG. Em lote — uma chamada por texto seria absurdo.

    Sempre local: o índice é bge-m3 de 1024 dimensões, e trocar o embedder
    significaria reindexar 2.099 chunks e migrar a coluna do pgvector.
    """
    async with _semaforo:
        provider = _obter("ollama")
        return await provider.embedar(textos, modelo=modelo or settings.ollama_model_embedding)


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
