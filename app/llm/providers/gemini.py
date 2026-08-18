"""Provider da API do Gemini — o escape para fora da máquina.

É a segunda implementação do `Provider`, e o `tipos.py` já previa que ela
chegaria. O que ela **não** é: uma troca de "local" por "nuvem". O roteamento
manda uma tarefa só para cá — a que o modelo local media pior, e onde errar
custa caro.

## Por que uma tarefa e não todas

Medido na aula de 17/08/2026, mesmo corpo e mesmo prompt:

    llama3.1:8b        "A negação de P ou Q é P e Q"          ← lei falsa
    gemini-2.5-flash   "A negação de P ∧ Q é ¬P ∨ ¬Q"         ← correta
                       "Inverte Negando: P → Q ≡ ¬Q → ¬P"     ← o 8B não enunciou
                       "Não pode ver queijo: P → Q ≡ ¬P ∨ Q"  ← nem esta

As duas equivalências eram o assunto inteiro da aula. E onde faltou informação o
Gemini **omitiu**, enquanto o 8B preencheu a cota de cinco destaques com uma
fórmula inventada. Essa é a diferença que paga a chamada.

Redigir, classificar e extrair continuam locais: lá o modelo pequeno com o
contexto certo empata, e a regra do projeto (README) continua valendo.

## Sem SDK, pelo mesmo motivo do Ollama

É um endpoint e um JSON de resposta. O `google-genai` traria uma árvore de
dependências e uma versão para casar, em troca de nada que o `httpx` não faça.

## Embedding fica fora de propósito

O índice tem 2.099 chunks em 1024 dimensões do `bge-m3`. Trocar o embedder
significa reindexar tudo e migrar a coluna do pgvector — trabalho grande, ganho
nenhum, e uma conta por chunk indexado. `embedar` aqui existe só para satisfazer
o Protocol, e recusa alto.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.llm.tipos import LLMIndisponivel, RespostaCrua
from app.utils.logger import get_logger

logger = get_logger()

BASE = "https://generativelanguage.googleapis.com/v1beta"

# Respostas que somem sozinhas: pico de demanda, cota do minuto, erro interno.
# Separadas das outras porque o breaker do gateway trata as duas iguais, mas o
# log precisa dizer qual foi — 503 é esperar, 429 é gastar menos.
_TRANSITORIO = {429, 500, 502, 503, 504}


class GeminiProvider:
    nome = "gemini"

    def __init__(self, chave: str | None = None, timeout_s: float | None = None) -> None:
        self.chave = chave or settings.gemini_api_key
        self.timeout_s = timeout_s or settings.llm_timeout_s

    async def gerar(
        self,
        prompt: str,
        *,
        modelo: str,
        json_mode: bool = False,
        temperatura: float | None = None,
        opcoes: dict | None = None,
    ) -> RespostaCrua:
        if not self.chave:
            raise LLMIndisponivel("GEMINI_API_KEY não está no .env")

        config: dict = {**(opcoes or {})}
        if json_mode:
            # Garante JSON sintaticamente válido na origem. O reprompt do gateway
            # continua existindo para o caso de vir válido mas com chave faltando.
            config["responseMimeType"] = "application/json"
        if temperatura is not None:
            config["temperature"] = temperatura

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        if config:
            payload["generationConfig"] = config

        try:
            async with httpx.AsyncClient(base_url=BASE, timeout=self.timeout_s) as client:
                resp = await client.post(
                    f"/models/{modelo}:generateContent",
                    json=payload,
                    headers={"x-goog-api-key": self.chave},
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            raise LLMIndisponivel(f"Gemini não respondeu ({type(e).__name__}): {e}") from e

        if resp.status_code != 200:
            tipo = "sobrecarga/cota" if resp.status_code in _TRANSITORIO else "recusa"
            raise LLMIndisponivel(f"Gemini {resp.status_code} ({tipo}): {resp.text[:300]}")

        return self._ler(resp.json(), modelo)

    @staticmethod
    def _ler(d: dict, modelo: str) -> RespostaCrua:
        """Traduz a resposta para o contrato do gateway.

        O caminho sem `candidates` é real e silencioso: quando o filtro de
        segurança barra a entrada, a resposta é **200** com `promptFeedback` e
        nenhum candidato. Ler `candidates[0]` direto daria IndexError três
        camadas acima, num lugar que não sabe o que aconteceu.
        """
        candidatos = d.get("candidates") or []
        if not candidatos:
            motivo = (d.get("promptFeedback") or {}).get("blockReason", "sem candidato")
            raise LLMIndisponivel(f"Gemini não devolveu resposta ({motivo})")

        cand = candidatos[0]
        partes = (cand.get("content") or {}).get("parts") or []
        # O modelo com raciocínio pode marcar partes como `thought`. Elas não
        # entram no texto — misturá-las quebraria o parse de JSON de forma
        # intermitente, o mesmo defeito que o provider do Ollama já trata.
        texto = "".join(p.get("text", "") for p in partes if not p.get("thought"))
        pensamento = "".join(p.get("text", "") for p in partes if p.get("thought"))

        uso = d.get("usageMetadata") or {}
        saida = uso.get("candidatesTokenCount")
        pensados = uso.get("thoughtsTokenCount") or 0
        if saida is not None:
            # O token de pensamento é cobrado como saída. Somar aqui é o que faz
            # o painel de observabilidade mostrar o custo real, e não a metade.
            saida += pensados

        if not texto.strip():
            raise LLMIndisponivel(
                f"Gemini devolveu texto vazio (finishReason={cand.get('finishReason')})"
            )

        return RespostaCrua(
            texto=texto,
            modelo=modelo,
            tokens_input=uso.get("promptTokenCount"),
            tokens_output=saida,
            finish_reason=cand.get("finishReason"),
            thinking=pensamento,
        )

    async def embedar(self, textos: list[str], *, modelo: str) -> list[list[float]]:
        raise LLMIndisponivel(
            "Embedding não passa pelo Gemini: o índice é bge-m3 de 1024 dimensões "
            "e trocar exigiria reindexar os 2.099 chunks. Use o provider local."
        )

    async def disponivel(self) -> bool:
        if not self.chave:
            return False
        try:
            async with httpx.AsyncClient(base_url=BASE, timeout=10.0) as client:
                r = await client.get("/models", headers={"x-goog-api-key": self.chave})
                return r.status_code == 200
        except Exception:
            return False
