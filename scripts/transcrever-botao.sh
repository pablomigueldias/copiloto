#!/usr/bin/env bash
# O "botão": abre um terminal já gravando o que está tocando na máquina.
#
# Existe porque `cd ~/Documentos/copiloto && source .venv/bin/activate && python
# scripts/transcrever.py` não é algo que se digita com a reunião já começando.
# Um atalho de teclado dispara este arquivo e a gravação começa em dois segundos.
#
# Instalar como atalho global (GNOME):
#   Configurações → Teclado → Atalhos → Personalizados → +
#   Comando: /home/pablo/Documentos/copiloto/scripts/transcrever-botao.sh
#   Tecla:   Ctrl+Alt+T  (ou a que estiver livre)
#
# Também dá para pôr no menu de aplicativos:
#   cp scripts/copiloto-transcrever.desktop ~/.local/share/applications/
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# O terminal fica aberto ao fim (`exec bash`) de propósito: a tela que pergunta
# o título e a pasta vem depois da gravação, e um terminal que fecha sozinho
# levaria a nota junto.
COMANDO="cd '$RAIZ' && source .venv/bin/activate && python scripts/transcrever.py $* ; echo; echo '[enter para fechar]'; read"

for term in gnome-terminal konsole xfce4-terminal alacritty kitty x-terminal-emulator xterm; do
  command -v "$term" >/dev/null 2>&1 || continue
  case "$term" in
    gnome-terminal) exec "$term" --title="Copiloto · transcrevendo" -- bash -c "$COMANDO" ;;
    konsole)        exec "$term" --hold -e bash -c "$COMANDO" ;;
    *)              exec "$term" -e bash -c "$COMANDO" ;;
  esac
done

echo "Nenhum emulador de terminal encontrado. Rode direto:" >&2
echo "  cd $RAIZ && source .venv/bin/activate && python scripts/transcrever.py" >&2
exit 1
