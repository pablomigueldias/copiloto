"""Benchmark dos modelos locais — responde 'cabe?' e 'cabe junto?'.

A segunda pergunta é a que importa: em 6 GB o custo real não é a inferência, é
a **troca de modelo**. Um generalista de 8B cabe sozinho e expulsa o embedder,
transformando toda busca de RAG em descarrega-carrega de 6-12s no caminho
crítico. Dois especialistas residentes custam zero de troca.

Uso:
    python scripts/bench_modelos.py                 # todos os configurados
    python scripts/bench_modelos.py phi4-mini qwen3:4b
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

PROMPT = (
    "Escreva um parágrafo de cerca de 150 palavras explicando, para um "
    "desenvolvedor, por que rodar um modelo de linguagem localmente muda a "
    "forma como um assistente pessoal é construído."
)
SAIDA = Path(__file__).resolve().parent.parent / "data" / "bench_modelos.json"

# O bge-m3 herda o OLLAMA_CONTEXT_LENGTH global (8192) e tenta reservar 4,7 GB
# de buffer CUDA — em 6 GB isso mata a convivência com o modelo de extração.
# Chunk de RAG não passa de ~512 tokens; 2048 é folga com sobra.
EMBED_NUM_CTX = 2048


def vram_usada_mb() -> int:
    """VRAM ocupada na GPU 0, em MB. Zero se não houver nvidia-smi."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return 0


async def amostrar_vram(parar: asyncio.Event) -> int:
    """Pico de VRAM enquanto o evento não é setado (amostra a cada 200ms)."""
    pico = 0
    while not parar.is_set():
        pico = max(pico, vram_usada_mb())
        await asyncio.sleep(0.2)
    return max(pico, vram_usada_mb())


async def descarregar_tudo(client: httpx.AsyncClient) -> None:
    """keep_alive=0 força o Ollama a soltar a VRAM na hora."""
    r = await client.get("/api/ps")
    for m in r.json().get("models", []):
        await client.post(
            "/api/generate", json={"model": m["name"], "keep_alive": 0, "prompt": ""}
        )
    await asyncio.sleep(1.5)


async def medir(client: httpx.AsyncClient, modelo: str) -> dict:
    await descarregar_tudo(client)
    base_mb = vram_usada_mb()

    parar = asyncio.Event()
    amostra = asyncio.create_task(amostrar_vram(parar))
    t0 = time.perf_counter()
    resp = await client.post(
        "/api/generate",
        json={"model": modelo, "prompt": PROMPT, "stream": False},
    )
    parede_ms = int((time.perf_counter() - t0) * 1000)
    parar.set()
    pico_mb = await amostra

    resp.raise_for_status()
    d = resp.json()
    eval_count = d.get("eval_count") or 0
    eval_ns = d.get("eval_duration") or 0

    return {
        "modelo": modelo,
        "carga_ms": round((d.get("load_duration") or 0) / 1e6),
        "parede_ms": parede_ms,
        "tokens_saida": eval_count,
        "tokens_s": round(eval_count / (eval_ns / 1e9), 1) if eval_ns else None,
        "vram_pico_mb": pico_mb,
        "vram_modelo_mb": max(pico_mb - base_mb, 0),
    }


async def medir_embedding(client: httpx.AsyncClient, modelo: str) -> dict:
    await descarregar_tudo(client)
    base_mb = vram_usada_mb()

    parar = asyncio.Event()
    amostra = asyncio.create_task(amostrar_vram(parar))
    t0 = time.perf_counter()
    resp = await client.post(
        "/api/embed",
        json={"model": modelo, "input": [PROMPT] * 8, "options": {"num_ctx": EMBED_NUM_CTX}},
    )
    parede_ms = int((time.perf_counter() - t0) * 1000)
    parar.set()
    pico_mb = await amostra

    resp.raise_for_status()
    d = resp.json()
    return {
        "modelo": modelo,
        "carga_ms": round((d.get("load_duration") or 0) / 1e6),
        "parede_ms": parede_ms,
        "dimensoes": len(d["embeddings"][0]),
        "lote": len(d["embeddings"]),
        "vram_pico_mb": pico_mb,
        "vram_modelo_mb": max(pico_mb - base_mb, 0),
    }


async def medir_convivencia(client: httpx.AsyncClient, a: str, b: str) -> dict:
    """Os dois residentes ao mesmo tempo — o teste que decide a alocação."""
    await descarregar_tudo(client)
    base_mb = vram_usada_mb()
    await client.post("/api/generate", json={"model": a, "prompt": "oi", "stream": False})
    await client.post(
        "/api/embed",
        json={"model": b, "input": "oi", "options": {"num_ctx": EMBED_NUM_CTX}},
    )
    juntos_mb = vram_usada_mb()

    carregados = [m["name"] for m in (await client.get("/api/ps")).json().get("models", [])]
    return {
        "modelos": [a, b],
        "vram_juntos_mb": max(juntos_mb - base_mb, 0),
        "ambos_residentes": len(carregados) == 2,
        "carregados": carregados,
    }


async def main() -> None:
    modelos = sys.argv[1:] or [
        settings.ollama_model_extracao,
        settings.ollama_model_redacao,
    ]

    async with httpx.AsyncClient(base_url=settings.ollama_host, timeout=600.0) as client:
        try:
            await client.get("/api/version")
        except httpx.ConnectError:
            sys.exit("Ollama não responde. Rode ./scripts/ollama-serve.sh")

        geracao = [await medir(client, m) for m in modelos]
        embed = await medir_embedding(client, settings.ollama_model_embedding)
        junto = await medir_convivencia(
            client, settings.ollama_model_extracao, settings.ollama_model_embedding
        )

    print(f"\n{'modelo':<18} {'tok/s':>7} {'carga':>9} {'parede':>9} {'VRAM':>9}")
    print("─" * 56)
    for r in geracao:
        print(
            f"{r['modelo']:<18} {r['tokens_s'] or 0:>7.1f} {r['carga_ms']:>7} ms "
            f"{r['parede_ms']:>7} ms {r['vram_modelo_mb']:>6} MB"
        )
    print(
        f"{embed['modelo']:<18} {'—':>7} {embed['carga_ms']:>7} ms "
        f"{embed['parede_ms']:>7} ms {embed['vram_modelo_mb']:>6} MB "
        f"({embed['lote']} textos, {embed['dimensoes']} dim)"
    )
    print(
        f"\nResidentes juntos: {' + '.join(junto['modelos'])} = "
        f"{junto['vram_juntos_mb']} MB · ambos na VRAM: "
        f"{'sim' if junto['ambos_residentes'] else 'NÃO'}"
    )

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(
        json.dumps({"geracao": geracao, "embedding": embed, "convivencia": junto}, indent=2)
    )
    print(f"\n→ {SAIDA}")


if __name__ == "__main__":
    asyncio.run(main())
