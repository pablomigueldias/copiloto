"""Contratos do pacote `llm` — o que entra e o que sai do gateway."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

# As quatro tarefas do sistema. Não é enfeite: é por este campo que o gateway
# escolhe o modelo e que a observabilidade responde "qual tarefa gasta token".
Tarefa = Literal["classificar", "extrair", "compreender", "redigir", "resumir"]


class LLMErro(Exception):
    """Falha de chamada de LLM que o chamador precisa tratar."""


class LLMIndisponivel(LLMErro):
    """Servidor fora do ar, timeout, ou modelo que não carrega (OOM de VRAM)."""


class LLMCircuitoAberto(LLMIndisponivel):
    """O breaker desligou este modelo — nem tentamos."""


class JSONInvalido(LLMErro):
    """O modelo não produziu JSON válido nem depois dos reprompts."""


@dataclass(slots=True)
class LLMResult:
    texto: str
    modelo: str
    latencia_ms: int
    json: dict | list | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    finish_reason: str | None = None
    tentativas: int = 1
    # Modelo com "thinking" gasta token raciocinando antes de escrever. Não vai
    # para `texto`, mas é token pago em tempo de GPU — então é medido.
    thinking_chars: int = 0


@dataclass(slots=True)
class RespostaCrua:
    """O que um provider devolve, antes de qualquer parse."""

    texto: str
    modelo: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    finish_reason: str | None = None
    thinking: str = ""


@runtime_checkable
class Provider(Protocol):
    """Implementado hoje só pelo Ollama.

    O escape para API externa da §10 do plano (gerar dados de treino) entra
    como outra implementação deste Protocol, na fase em que houver fila de
    aprovação para produzir os pares — não antes.
    """

    nome: str

    async def gerar(
        self,
        prompt: str,
        *,
        modelo: str,
        json_mode: bool = False,
        temperatura: float | None = None,
        opcoes: dict | None = None,
    ) -> RespostaCrua: ...

    async def embedar(self, textos: list[str], *, modelo: str) -> list[list[float]]: ...


@dataclass(slots=True)
class Rota:
    """Para onde vai cada tarefa.

    `provider` nasceu quando `compreender` saiu da máquina: a tarefa continua a
    mesma, o modelo e o servidor é que mudam. Quem chama o gateway não sabe —
    e não deve saber — se a resposta veio da GPU ou de uma API.
    """

    modelo: str
    json_mode: bool = False
    temperatura: float | None = None
    opcoes: dict = field(default_factory=dict)
    provider: str = "ollama"
