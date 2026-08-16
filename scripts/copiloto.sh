#!/usr/bin/env bash
# O Copiloto inteiro, num comando.
#
#   ./scripts/copiloto.sh up        sobe o que estiver faltando
#   ./scripts/copiloto.sh status    o que está de pé (e o que não está)
#   ./scripts/copiloto.sh down      derruba os processos deste projeto
#   ./scripts/copiloto.sh logs api|worker|ollama
#
# ## Por que este arquivo existe
#
# Subir o sistema eram quatro terminais e uma ordem que só existia na minha
# cabeça: docker, ollama, migration, worker, api. Errar a ordem não dá erro —
# dá comportamento estranho depois. E **o worker era a peça que eu esquecia**,
# porque nada na tela reclamava: 42 PDFs ficaram 14 h fora do índice por isso.
#
# ## Idempotente de propósito
#
# `up` roda com o sistema meio de pé e conserta só o que falta. Isso importa
# porque o comando que eu vou digitar quando algo está estranho é este mesmo, e
# ele não pode derrubar o que está funcionando para "começar limpo".
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

VERDE=$'\033[32m'; VERMELHO=$'\033[31m'; AMARELO=$'\033[33m'
CINZA=$'\033[90m'; NEGRITO=$'\033[1m'; FIM=$'\033[0m'

PORTA_API=8010
PORTA_OLLAMA=11434
PORTA_PG=5434
PORTA_REDIS=6380

PIDS="$RAIZ/logs/pids"
mkdir -p "$RAIZ/logs" "$PIDS"

ok()    { echo "  ${VERDE}✓${FIM} $*"; }
falta() { echo "  ${VERMELHO}✗${FIM} $*"; }
nota()  { echo "  ${CINZA}$*${FIM}"; }

# Porta ocupada é o teste mais honesto de "está de pé": não depende de PID
# guardado, que fica velho quando o processo morre sem avisar.
porta_ocupada() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- ; }

# ── um serviço de fundo, com PID e log próprios ───────────────────

subir_em_fundo() {
  local nome="$1" porta="$2"; shift 2
  if porta_ocupada "$porta"; then ok "$nome já está de pé (:$porta)"; return; fi

  # `setsid` desgruda do terminal: fechar a janela não leva o serviço junto.
  setsid "$@" >>"$RAIZ/logs/$nome.log" 2>&1 &
  echo $! >"$PIDS/$nome.pid"

  for _ in $(seq 40); do
    porta_ocupada "$porta" && { ok "$nome subiu (:$porta)"; return; }
    sleep 0.25
  done
  falta "$nome não respondeu em 10 s — veja logs/$nome.log"
  return 1
}

# O worker não abre porta nenhuma, então aqui o PID é o que há.
worker_rodando() {
  local pid; pid="$(cat "$PIDS/worker.pid" 2>/dev/null || true)"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

# ── comandos ──────────────────────────────────────────────────────

cmd_up() {
  echo "${NEGRITO}subindo o Copiloto${FIM}"

  echo "${CINZA}banco e fila${FIM}"
  if porta_ocupada "$PORTA_PG" && porta_ocupada "$PORTA_REDIS"; then
    ok "postgres e redis já estão de pé"
  else
    docker compose up -d >/dev/null
    # `up -d` volta antes do healthcheck passar; a migration precisa do banco
    # aceitando conexão, não do contêiner existindo.
    for _ in $(seq 60); do porta_ocupada "$PORTA_PG" && break; sleep 0.5; done
    porta_ocupada "$PORTA_PG" && ok "postgres (:$PORTA_PG) e redis (:$PORTA_REDIS)" \
      || { falta "postgres não subiu"; return 1; }
  fi

  echo "${CINZA}modelo local${FIM}"
  subir_em_fundo ollama "$PORTA_OLLAMA" "$RAIZ/scripts/ollama-serve.sh" || true

  echo "${CINZA}migrations${FIM}"
  if "$RAIZ/.venv/bin/python" -m alembic upgrade head >>"$RAIZ/logs/alembic.log" 2>&1; then
    ok "schema em dia"
  else
    falta "alembic falhou — veja logs/alembic.log"; return 1
  fi

  echo "${CINZA}worker${FIM}"
  if worker_rodando; then
    ok "worker já está de pé (pid $(cat "$PIDS/worker.pid"))"
  else
    setsid "$RAIZ/.venv/bin/python" -m arq app.worker.main.WorkerSettings \
      >>"$RAIZ/logs/worker.log" 2>&1 &
    echo $! >"$PIDS/worker.pid"
    sleep 1.5
    worker_rodando && ok "worker subiu (pid $(cat "$PIDS/worker.pid"))" \
      || { falta "worker morreu ao subir — veja logs/worker.log"; return 1; }
  fi

  echo "${CINZA}api + painel${FIM}"
  subir_em_fundo api "$PORTA_API" \
    "$RAIZ/.venv/bin/python" -m uvicorn app.api.main:app --port "$PORTA_API"

  echo
  echo "  ${NEGRITO}painel:${FIM} http://localhost:$PORTA_API"
}

cmd_status() {
  echo "${NEGRITO}Copiloto${FIM}"
  porta_ocupada "$PORTA_PG"     && ok "postgres  :$PORTA_PG"     || falta "postgres  :$PORTA_PG"
  porta_ocupada "$PORTA_REDIS"  && ok "redis     :$PORTA_REDIS"  || falta "redis     :$PORTA_REDIS"
  porta_ocupada "$PORTA_OLLAMA" && ok "ollama    :$PORTA_OLLAMA" || falta "ollama    :$PORTA_OLLAMA"
  porta_ocupada "$PORTA_API"    && ok "api       :$PORTA_API"    || falta "api       :$PORTA_API"

  if worker_rodando; then
    ok "worker    pid $(cat "$PIDS/worker.pid")"
    # A pergunta que interessa não é "o processo existe", é "ele bateu ponto".
    local visto
    visto="$(docker exec copiloto-redis redis-cli GET copiloto:worker:vivo 2>/dev/null || true)"
    [[ -n "$visto" ]] && nota "último batimento: $visto" \
      || nota "sem batimento no Redis ainda (o primeiro sai em até 1 min)"
  else
    falta "worker    parado — o índice não se atualiza sozinho"
  fi

  echo
  if porta_ocupada "$PORTA_API"; then
    echo "  painel: http://localhost:$PORTA_API"
  else
    echo "  ${AMARELO}rode: ./scripts/copiloto.sh up${FIM}"
  fi
}

cmd_down() {
  echo "${NEGRITO}derrubando${FIM}"
  for nome in api worker ollama; do
    local pid; pid="$(cat "$PIDS/$nome.pid" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      # O grupo inteiro: `uvicorn --reload` e o `arq` têm filhos.
      kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
      ok "$nome parado"
    else
      nota "$nome não estava rodando"
    fi
    rm -f "$PIDS/$nome.pid"
  done
  # Postgres e Redis ficam de pé: são contêineres com dado dentro, e derrubar
  # por reflexo é como se perde banco de desenvolvimento. `docker compose down`
  # quando eu quiser mesmo.
  nota "postgres e redis continuam de pé (docker compose down para derrubar)"
}

cmd_logs() {
  local alvo="${1:-api}"
  local arquivo="$RAIZ/logs/$alvo.log"
  [[ -f "$arquivo" ]] || { echo "sem log de '$alvo' em $arquivo"; exit 1; }
  tail -f "$arquivo"
}

case "${1:-status}" in
  up)     cmd_up ;;
  status) cmd_status ;;
  down)   cmd_down ;;
  logs)   cmd_logs "${2:-api}" ;;
  *)      sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \?//' ; exit 1 ;;
esac
