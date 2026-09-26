#!/usr/bin/env bash
# Backup criptografado do que só existe nesta máquina (passo 5.4).
#
#     scripts/comercial/backup.sh                          # faz a cópia do dia
#     scripts/comercial/backup.sh restaurar <arquivo.gpg> <pasta-destino>
#
# O quê: ~/Clientes (dado de cliente), data/comercial (base e modelos, fora do
# git) e docs/ (fora do git). Para onde: /mnt/dados/backup-comercial, um .gpg
# por dia (AES-256, senha num arquivo 600), mantendo os 30 últimos.
#
# ⚠️ O /mnt/dados é um disco dentro deste PC: protege de arquivo apagado ou
# disco do /home morto, não de perder o PC (desvio aceito do 5.4, ver
# docs/motor-comercial/fase-0/operacao.md). A senha precisa estar também no
# Bitwarden: sem ela, o backup não abre.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DESTINO="${BACKUP_DESTINO:-/mnt/dados/backup-comercial}"
SENHA="${BACKUP_SENHA:-$HOME/.config/copiloto/backup-senha}"
MANTER=30

if [[ ${1:-} == restaurar ]]; then
    [[ $# -eq 3 ]] || { echo "uso: $0 restaurar <arquivo.gpg> <pasta-destino>" >&2; exit 2; }
    mkdir -p "$3"
    gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$SENHA" --decrypt "$2" | tar -xzf - -C "$3"
    echo "restaurado em: $3"
    exit 0
fi

if [[ ! -s $SENHA ]]; then
    mkdir -p "$(dirname "$SENHA")"
    (umask 077; gpg --gen-random --armor 1 32 > "$SENHA")
    echo "senha nova criada em $SENHA: copie para o Bitwarden agora." >&2
fi

mkdir -p "$DESTINO"
ARQUIVO="$DESTINO/$(date +%F).tar.gz.gpg"
tar -czf - -C / \
    "${HOME#/}/Clientes" \
    "${REPO#/}/data/comercial" \
    "${REPO#/}/docs" \
  | gpg --batch --quiet --yes --pinentry-mode loopback --passphrase-file "$SENHA" \
        --symmetric --cipher-algo AES256 -o "$ARQUIVO.tmp"
mv "$ARQUIVO.tmp" "$ARQUIVO"

ls -1t "$DESTINO"/*.tar.gz.gpg | tail -n +$((MANTER + 1)) | xargs -r rm --
echo "backup: $ARQUIVO ($(du -h "$ARQUIVO" | cut -f1))"
