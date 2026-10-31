"""O Chatwoot local do bot comercial (`docs/bot-comercial/07`, passo 1).

    python scripts/comercial/chatwoot.py subir     # banco, chave e contêineres
    python scripts/comercial/chatwoot.py setup     # conta, eu, caixa, Agent Bot
    python scripts/comercial/chatwoot.py simular "oi, quero saber do atendente"
    python scripts/comercial/chatwoot.py descer

`setup` é idempotente: rodar de novo só confere e acerta o que mudou (a URL do
webhook, por exemplo). Os ids, o token do bot e a minha senha vão para o
`.env`, que não entra no git.

A caixa é do tipo API: o "lead" é simulado pela API pública dela, sem Meta. A
caixa de WhatsApp de verdade é o passo 3b.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ENV = RAIZ / ".env"
URL = "http://127.0.0.1:3100"
CONTEINER = "copiloto-chatwoot"
CAIXA = "WhatsApp (dev)"
BOT = "Copiloto"


def _env() -> dict[str, str]:
    if not ENV.exists():
        return {}
    pares = (linha.split("=", 1) for linha in ENV.read_text().splitlines() if "=" in linha and not linha.startswith("#"))
    return {k.strip(): v.strip() for k, v in pares}


def _gravar_env(valores: dict[str, str]) -> None:
    """Acerta as chaves no `.env`: troca a linha se existe, acrescenta se não."""
    texto = ENV.read_text() if ENV.exists() else ""
    novas = []
    for chave, valor in valores.items():
        linha = f"{chave}={valor}"
        if re.search(rf"^{chave}=", texto, flags=re.M):
            texto = re.sub(rf"^{chave}=.*$", linha, texto, flags=re.M)
        else:
            novas.append(linha)
    if novas:
        if texto and not texto.endswith("\n"):
            texto += "\n"
        texto += "\n# Chatwoot do bot comercial (scripts/comercial/chatwoot.py)\n" + "\n".join(novas) + "\n"
    ENV.write_text(texto)


def _rodar(*cmd: str, entrada: str | None = None) -> str:
    r = subprocess.run(cmd, cwd=RAIZ, input=entrada, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"falhou: {' '.join(cmd[:4])}…\n{r.stderr[-2000:]}")
    return r.stdout


def _compose(*args: str) -> str:
    return _rodar("docker", "compose", "--profile", "chatwoot", *args)


def _no_ar() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api", timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def subir(_: argparse.Namespace) -> None:
    env = _env()
    faltam = {}
    if not env.get("CHATWOOT_SECRET_KEY_BASE"):
        faltam["CHATWOOT_SECRET_KEY_BASE"] = secrets.token_hex(64)
    if not env.get("CHATWOOT_WEBHOOK_SEGREDO"):
        faltam["CHATWOOT_WEBHOOK_SEGREDO"] = secrets.token_urlsafe(32)
    if faltam:
        _gravar_env(faltam)
        print(f"gerei no .env: {', '.join(faltam)}")

    _rodar("docker", "compose", "up", "-d", "--wait", "db", "redis")
    existe = _rodar(
        "docker", "exec", "copiloto-db", "psql", "-U", "copiloto", "-d", "postgres", "-tAc",
        "SELECT 1 FROM pg_database WHERE datname = 'chatwoot'",
    ).strip()
    if not existe:
        _rodar("docker", "exec", "copiloto-db", "createdb", "-U", "copiloto", "chatwoot")
        print("banco chatwoot criado")

    print("preparando o banco do Chatwoot (a primeira vez leva uns minutos)…")
    _compose("run", "--rm", "--no-deps", "chatwoot-rails", "bundle", "exec", "rails", "db:chatwoot_prepare")
    _compose("up", "-d", "chatwoot-rails", "chatwoot-sidekiq")
    for _ in range(90):
        if _no_ar():
            print(f"Chatwoot no ar em {URL}")
            return
        time.sleep(2)
    sys.exit("o Chatwoot não respondeu em 3 min: docker logs copiloto-chatwoot")


# O setup roda dentro do Rails: conta, usuário, caixa e bot são modelos dele, e
# a API de administração exigiria um usuário que ainda não existe.
_RUBY = r"""
require "json"
a = JSON.parse(ENV.fetch("SETUP"))
::Redis::Alfred.delete(::Redis::Alfred::CHATWOOT_INSTALLATION_ONBOARDING)

conta = Account.find_or_create_by!(name: a["conta"])
conta.update!(locale: "pt_BR") if conta.locale != "pt_BR"

u = User.find_by(email: a["email"])
senha = nil
unless u
  senha = a["senha"]
  u = User.new(name: a["nome"], email: a["email"], password: senha, password_confirmation: senha)
  u.skip_confirmation!
  u.save!
end
AccountUser.find_or_create_by!(account: conta, user: u) { |au| au.role = :administrator }

caixa = conta.inboxes.find_by(name: a["caixa"])
unless caixa
  canal = Channel::Api.create!(account: conta)
  caixa = conta.inboxes.create!(name: a["caixa"], channel: canal)
end

bot = AgentBot.find_or_initialize_by(name: a["bot"], account_id: conta.id)
bot.outgoing_url = a["webhook"]
bot.description = "O bot comercial do Copiloto (docs/bot-comercial)"
bot.save!
AgentBotInbox.find_or_create_by!(inbox: caixa, agent_bot: bot) { |abi| abi.account_id = conta.id }

puts "SETUP=" + {
  conta_id: conta.id, caixa_id: caixa.id, caixa_identificador: caixa.channel.identifier,
  bot_token: bot.access_token.token, senha: senha
}.to_json
"""


def setup(args: argparse.Namespace) -> None:
    if not _no_ar():
        sys.exit("o Chatwoot não está no ar: rode `subir` antes")
    env = _env()
    segredo = env.get("CHATWOOT_WEBHOOK_SEGREDO")
    if not segredo:
        sys.exit("falta CHATWOOT_WEBHOOK_SEGREDO no .env: rode `subir`")
    dados = {
        "conta": "Pablo Ortiz · comercial",
        "nome": "Pablo",
        "email": args.email,
        "senha": secrets.token_urlsafe(12) + "!9a",
        "caixa": CAIXA,
        "bot": BOT,
        "webhook": f"{args.api.rstrip('/')}/api/comercial/chatwoot/webhook?token={segredo}",
    }
    saida = _rodar(
        "docker", "exec", "-e", f"SETUP={json.dumps(dados)}", "-i", CONTEINER,
        "bundle", "exec", "rails", "runner", "-", entrada=_RUBY,
    )
    linha = next((x for x in saida.splitlines() if x.startswith("SETUP=")), None)
    if not linha:
        sys.exit(f"o setup não devolveu os ids:\n{saida[-2000:]}")
    r = json.loads(linha.removeprefix("SETUP="))
    valores = {
        "CHATWOOT_CONTA_ID": str(r["conta_id"]),
        "CHATWOOT_BOT_TOKEN": r["bot_token"],
        "CHATWOOT_CAIXA_IDENTIFICADOR": r["caixa_identificador"],
        "CHATWOOT_ADMIN_EMAIL": args.email,
    }
    if r["senha"]:
        valores["CHATWOOT_ADMIN_SENHA"] = r["senha"]
    _gravar_env(valores)
    print(f"conta {r['conta_id']}, caixa {r['caixa_id']} ({CAIXA}), Agent Bot '{BOT}' → {args.api}")
    print(f"entre em {URL} com {args.email}; a senha está no .env (CHATWOOT_ADMIN_SENHA)")
    print("reinicie a API do Copiloto para ela ler o token novo do .env")


def _post(caminho: str, corpo: dict) -> dict:
    req = urllib.request.Request(
        URL + caminho, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def simular(args: argparse.Namespace) -> None:
    """Escreve como um lead, pela API pública da caixa (sem login)."""
    caixa = _env().get("CHATWOOT_CAIXA_IDENTIFICADOR")
    if not caixa:
        sys.exit("falta CHATWOOT_CAIXA_IDENTIFICADOR no .env: rode `setup`")
    base = f"/public/api/v1/inboxes/{caixa}/contacts"
    if args.contato:
        fonte, conversa = args.contato, args.conversa
    else:
        contato = _post(base, {"name": args.nome, "phone_number": args.telefone})
        fonte = contato["source_id"]
        conversa = _post(f"{base}/{fonte}/conversations", {})["id"]
    _post(f"{base}/{fonte}/conversations/{conversa}/messages", {"content": args.texto})
    print(f"mensagem na conversa {conversa} (contato {fonte})")
    print(f"para continuar a mesma conversa: simular --contato {fonte} --conversa {conversa} \"…\"")


def descer(_: argparse.Namespace) -> None:
    _compose("stop", "chatwoot-rails", "chatwoot-sidekiq")
    print("Chatwoot parado; os dados ficam")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("subir").set_defaults(f=subir)
    s = sub.add_parser("setup")
    s.add_argument("--email", default="pablo@copiloto.local", help="o meu login no Chatwoot local")
    s.add_argument("--api", default="http://127.0.0.1:8010", help="onde o Chatwoot acha a API do Copiloto")
    s.set_defaults(f=setup)
    s = sub.add_parser("simular")
    s.add_argument("texto")
    s.add_argument("--nome", default="Lead de teste")
    s.add_argument("--telefone", default=None)
    s.add_argument("--contato", help="source_id de um contato já simulado")
    s.add_argument("--conversa", type=int, help="id da conversa desse contato")
    s.set_defaults(f=simular)
    sub.add_parser("descer").set_defaults(f=descer)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
