"""Provider do Ollama — o único que existe hoje.

Fala HTTP puro com `/api/generate` e `/api/embed`. Sem SDK: são dois endpoints
e um JSON de resposta; uma dependência a mais só traria versão para casar.
"""
from __future__ import annotations

import httpx

from app.config import settings
from app.llm.tipos import LLMIndisponivel, RespostaCrua
from app.utils.logger import get_logger

logger = get_logger()

# O bge-m3 herda o OLLAMA_CONTEXT_LENGTH global (8192) e tenta reservar ~4,7 GB
# de buffer CUDA, o que estoura os 6 GB assim que o modelo de extração está
# carregado. Com 2048 os dois ficam residentes em 4,5 GB. Chunk de RAG não
# chega perto desse limite.
EMBED_NUM_CTX = 2048


class OllamaProvider:
    nome = "ollama"

    def __init__(self, host: str | None = None, timeout_s: float | None = None) -> None:
        self.host = host or settings.ollama_host
        self.timeout_s = timeout_s or settings.llm_timeout_s

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.host, timeout=self.timeout_s)

    async def gerar(
        self,
        prompt: str,
        *,
        modelo: str,
        json_mode: bool = False,
        temperatura: float | None = None,
        opcoes: dict | None = None,
    ) -> RespostaCrua:
        payload: dict = {"model": modelo, "prompt": prompt, "stream": False}
        if json_mode:
            payload["format"] = "json"

        # Sem `num_predict` de propósito. Modelo com raciocínio (qwen3) gasta
        # ~2.000 tokens pensando ANTES de escrever; qualquer teto que pareça
        # generoso corta a resposta no meio do pensamento e devolve texto vazio.
        options = {**(opcoes or {})}
        if temperatura is not None:
            options["temperature"] = temperatura
        if options:
            payload["options"] = options

        try:
            async with self._client() as client:
                resp = await client.post("/api/generate", json=payload)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            raise LLMIndisponivel(f"Ollama não respondeu ({type(e).__name__}): {e}") from e

        if resp.status_code >= 500 or resp.status_code == 404:
            # 404 = modelo não puxado; 500 costuma ser OOM de VRAM no runner.
            raise LLMIndisponivel(f"Ollama {resp.status_code}: {resp.text[:300]}")
        if resp.status_code != 200:
            raise LLMIndisponivel(f"Ollama recusou ({resp.status_code}): {resp.text[:300]}")

        d = resp.json()
        if "error" in d:
            raise LLMIndisponivel(f"Ollama: {d['error'][:300]}")

        # O Ollama separa o raciocínio em `thinking`. Ler `response` direto é o
        # que evita o parse de JSON quebrar de forma intermitente quando o
        # modelo resolve pensar em voz alta.
        return RespostaCrua(
            texto=d.get("response") or "",
            modelo=modelo,
            tokens_input=d.get("prompt_eval_count"),
            tokens_output=d.get("eval_count"),
            finish_reason=d.get("done_reason"),
            thinking=d.get("thinking") or "",
        )

    async def embedar(self, textos: list[str], *, modelo: str) -> list[list[float]]:
        if not textos:
            return []
        try:
            async with self._client() as client:
                resp = await client.post(
                    "/api/embed",
                    json={
                        "model": modelo,
                        "input": textos,
                        "options": {"num_ctx": EMBED_NUM_CTX},
                    },
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            raise LLMIndisponivel(f"Ollama não respondeu ({type(e).__name__}): {e}") from e

        if resp.status_code != 200:
            raise LLMIndisponivel(f"Embedding falhou ({resp.status_code}): {resp.text[:300]}")

        d = resp.json()
        if "error" in d:
            raise LLMIndisponivel(f"Embedding: {d['error'][:300]}")
        return d["embeddings"]

    async def disponivel(self) -> bool:
        try:
            async with self._client() as client:
                return (await client.get("/api/version")).status_code == 200
        except Exception:
            return False
