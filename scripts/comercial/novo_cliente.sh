#!/usr/bin/env bash
# Cria a pasta de um cliente a partir de ~/Clientes/_modelo (passo 5.1).
#
#     scripts/comercial/novo_cliente.sh 2026 espaco-travessia
#
# Não sobrescreve pasta que já existe: cliente de novo no mesmo ano é outra
# pasta, com outro slug.
set -euo pipefail

CLIENTES="${CLIENTES_DIR:-$HOME/Clientes}"
MODELO="$CLIENTES/_modelo"

if [[ $# -ne 2 || ! $1 =~ ^[0-9]{4}$ || ! $2 =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    echo "uso: $0 <ano AAAA> <slug-em-minusculas>" >&2
    exit 2
fi
[[ -d $MODELO ]] || { echo "sem pasta-modelo em $MODELO" >&2; exit 1; }

DESTINO="$CLIENTES/$1-$2"
if [[ -e $DESTINO ]]; then
    echo "já existe: $DESTINO" >&2
    exit 1
fi
cp -r "$MODELO" "$DESTINO"
echo "criada: $DESTINO"
