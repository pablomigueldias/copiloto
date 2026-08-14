#!/usr/bin/env bash
# Sobe o Ollama com as variáveis que fazem 6 GB de VRAM caberem dois modelos.
# Sem systemd de propósito: o serviço do pacote roda como usuário `ollama` e
# exigiria sudo pra editar o unit — aqui o servidor é do usuário.
set -euo pipefail
export OLLAMA_FLASH_ATTENTION=1     # pré-requisito do KV cache quantizado
export OLLAMA_KV_CACHE_TYPE=q8_0    # ~40% menos VRAM de KV cache
export OLLAMA_CONTEXT_LENGTH=8192
export OLLAMA_KEEP_ALIVE=5m
export OLLAMA_MAX_LOADED_MODELS=2   # phi4-mini + bge-m3 residentes
export OLLAMA_NUM_PARALLEL=1        # a 2060 não roda duas inferências juntas
exec ollama serve
