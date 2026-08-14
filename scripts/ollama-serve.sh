#!/usr/bin/env bash
# Sobe o Ollama com as variáveis que fazem 6 GB de VRAM caberem dois modelos.
#
# Sem systemd de propósito: o unit do pacote roda como usuário `ollama` e
# editá-lo exige sudo — aqui o servidor é do usuário e as variáveis ficam
# versionadas junto do código que depende delas.
#
# O binário de ~/.local/ollama ganha do /usr/local/bin: o do sistema é a 0.15
# (instalada em janeiro), que nem puxa os modelos da geração atual. Os modelos
# ficam em ~/.ollama e são os mesmos para os dois.
set -euo pipefail

OLLAMA_BIN="${OLLAMA_BIN:-$HOME/.local/ollama/bin/ollama}"
[[ -x "$OLLAMA_BIN" ]] || OLLAMA_BIN="$(command -v ollama)"

export OLLAMA_FLASH_ATTENTION=1     # pré-requisito do KV cache quantizado
export OLLAMA_KV_CACHE_TYPE=q8_0    # ~40% menos VRAM de KV cache
export OLLAMA_CONTEXT_LENGTH=8192
export OLLAMA_KEEP_ALIVE=5m
export OLLAMA_MAX_LOADED_MODELS=2   # phi4-mini + bge-m3 residentes
export OLLAMA_NUM_PARALLEL=1        # a 2060 não roda duas inferências juntas

exec "$OLLAMA_BIN" serve
