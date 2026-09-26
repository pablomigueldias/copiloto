"""Do "pronto" ao "no ar": branch, commit, PR, checks e merge — sem terminal.

Publicar um post eram oito passos à mão (exportar, criar branch, commitar,
empurrar, abrir PR, esperar o CI, rebasear quando a `main` andou, mergear).
Trabalho repetido é do sistema, não do autor. O que **não** muda é quem decide:
abrir o PR e mergear são dois botões separados, e o segundo só acende com os
checks verdes. O sistema prepara, eu executo — a mesma regra da fila.

## O que este módulo nunca faz

1. **Não commita nada além do arquivo do post.** Nunca `git add -A`. Se o repo
   do blog tiver outras mudanças em andamento, elas ficam onde estão — sweep de
   working tree alheia é como segredo entra em commit sem ninguém ver.
2. **Não toca na árvore de trabalho do blog.** Tudo acontece num `git worktree`
   temporário criado a partir da `origin/main`. Você pode estar editando outra
   coisa, em outra branch, com o `next dev` rodando: publicar não interrompe.
3. **Não commita na `main`.** Ela é protegida (PR obrigatório, check `ci`,
   histórico linear) e continua assim — o caminho é branch → PR → merge.
4. **Não mergeia sozinho.** Nem quando tudo está verde.

## Por que branch nova da `origin/main` toda vez

A proteção da `main` é `strict`: branch atrás da `main` não mergeia. Rebasear
depois é o passo que mais dói (e o que mais me fez pedir ajuda). Criar a branch
já a partir da `origin/main` faz o problema não existir.

## `gh` e não a API do GitHub

O `gh` já está autenticado nesta máquina, com o token no keyring. Falar direto
com a API exigiria guardar um token no `.env` do Copiloto — um segredo a mais
para vazar, para rotacionar e para explicar, em troca de nada.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

from app.blog import mdx
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger()

TIMEOUT_S = 120
# Onde os worktrees temporários nascem. Fora do repo do blog de propósito: um
# diretório dentro dele apareceria no `git status` do Pablo e, pior, no `next
# dev` como arquivo novo para recompilar.
BASE_WORKTREE = Path.home() / ".cache" / "copiloto" / "publicacao"


class PublicacaoErro(Exception):
    """Falhou um passo do caminho. A mensagem traz a saída do comando."""


async def _rodar(*args: str, cwd: Path) -> str:
    """Executa e devolve a saída. Erro vira exceção com o texto do comando.

    `args` é sempre uma lista fixa montada aqui — nada de string com `shell=True`.
    O único valor que vem de fora é o slug, e ele já passou pelo
    `taxonomia.SLUG_RE` antes de virar nome de branch ou de arquivo.
    """
    processo = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(), timeout=TIMEOUT_S)
    except TimeoutError:
        processo.kill()
        raise PublicacaoErro(f"`{' '.join(args[:2])}` passou de {TIMEOUT_S}s") from None

    texto = saida.decode("utf-8", "replace").strip()
    if processo.returncode != 0:
        raise PublicacaoErro(f"`{' '.join(args[:3])}` falhou:\n{texto}")
    return texto


def _repo() -> Path:
    repo = Path(settings.blog_repo_dir).expanduser()
    if not (repo / ".git").exists():
        raise PublicacaoErro(f"{repo} não é um repo git — ajuste BLOG_REPO_DIR")
    return repo


def _branch(slug: str) -> str:
    return f"post/{slug}"


def _mensagem(post) -> tuple[str, str]:
    """Assunto e corpo do commit. Sem trailer de co-autoria: decisão do Pablo."""
    # Correção de post no ar tem assunto próprio: no histórico do blog, "publica"
    # e "atualiza" são coisas diferentes de procurar.
    prefixo = "post: atualiza" if post.estado == "publicado" else "post:"
    assunto = f"{prefixo} {post.titulo}"
    if len(assunto) > 72:
        assunto = f"{prefixo} {post.slug}"
    corpo = (post.descricao or "").strip()
    return assunto, corpo


async def abrir_pr(post, *, repo: Path | None = None) -> dict:
    """Branch da `origin/main`, commit do `.mdx`, push e PR. Não mergeia.

    Idempotente na prática: rodar de novo em cima de um post já publicado
    recria a branch com o conteúdo atual e reabre (ou atualiza) o PR.
    """
    repo = repo or _repo()
    if not post.slug:
        raise PublicacaoErro("o post não tem slug — sem ele não há arquivo nem branch")

    branch = _branch(post.slug)
    trabalho = BASE_WORKTREE / f"{post.slug}-{uuid4().hex[:8]}"
    trabalho.parent.mkdir(parents=True, exist_ok=True)

    await _rodar("git", "fetch", "origin", "main", "--quiet", cwd=repo)
    # `-B`: cria ou redefine a branch, sempre a partir da `origin/main`.
    await _rodar(
        "git", "worktree", "add", "-B", branch, str(trabalho), "origin/main", cwd=repo
    )
    try:
        destino = trabalho / "content" / "blog"
        # Publicar é tirar o rascunho: o `draft` sai do estado, não de um botão.
        # Post no ar nunca sai como rascunho: `draft: true` o tiraria do site.
        caminho = mdx.exportar(
            post, diretorio=destino, rascunho=post.estado not in ("pronto", "publicado")
        )
        relativo = str(caminho.relative_to(trabalho))

        # Só o arquivo deste post. Nunca `-A`.
        await _rodar("git", "add", "--", relativo, cwd=trabalho)
        mudou = await _rodar("git", "status", "--porcelain", "--", relativo, cwd=trabalho)
        if not mudou:
            raise PublicacaoErro(
                "nada mudou em relação à `main` — este post já está publicado como está"
            )

        assunto, corpo = _mensagem(post)
        await _rodar("git", "commit", "-m", assunto, "-m", corpo, cwd=trabalho)
        await _rodar(
            "git", "push", "--force-with-lease", "-u", "origin", branch, cwd=trabalho
        )

        existente = await _pr_da_branch(branch, cwd=trabalho)
        if existente:
            pr = existente
        else:
            url = await _rodar(
                "gh", "pr", "create",
                "--base", "main",
                "--head", branch,
                "--title", assunto,
                "--body", _corpo_do_pr(post, trabalho),
                cwd=trabalho,
            )
            pr = {"url": url.splitlines()[-1].strip(), "numero": None}
            pr["numero"] = int(pr["url"].rstrip("/").rsplit("/", 1)[-1])
    finally:
        await _limpar(repo, trabalho)

    logger.info(f"Blog: PR #{pr['numero']} para {post.slug}")
    return {"pr_numero": pr["numero"], "pr_url": pr["url"], "branch": branch}


def _checklist_do_blog(trabalho: Path) -> str:
    """O checklist do template de PR do blog, do primeiro `## Checklist` em diante.

    Com `--body`, o `gh` não usa o template, e o checklist de privacidade (§10.5
    do plano) sumia justo dos PRs de post. Ler do worktree, e não copiar para
    cá, mantém a lista num lugar só: mudou no blog, muda no próximo PR.
    """
    template = trabalho / ".github" / "pull_request_template.md"
    if not template.is_file():
        return ""
    texto = template.read_text(encoding="utf-8")
    inicio = texto.find("## Checklist")
    return texto[inicio:].strip() if inicio >= 0 else ""


def _corpo_do_pr(post, trabalho: Path) -> str:
    camadas = (
        "| abertura | entusiasta |\n"
        "| problema e resultado | cliente |\n"
        "| como foi feito | técnico |\n"
        "| prova e origem | recrutador |\n"
        "| fechamento | todos |"
    )
    corpo = (
        f"{(post.descricao or '').strip()}\n\n"
        "Gerado pela redação do Copiloto. O post fechou as cinco camadas antes de "
        "poder ser exportado:\n\n"
        "| Camada | Público |\n|---|---|\n"
        f"{camadas}\n\n"
        "O frontmatter sai dos campos e é validado contra o mesmo "
        "`src/content/schema.ts` que o CI usa."
    )
    checklist = _checklist_do_blog(trabalho)
    return f"{corpo}\n\n{checklist}" if checklist else corpo


async def _pr_da_branch(branch: str, *, cwd: Path) -> dict | None:
    """O PR aberto desta branch, se houver. Sem PR, `gh` devolve lista vazia."""
    try:
        bruto = await _rodar(
            "gh", "pr", "list", "--head", branch, "--state", "open",
            "--json", "number,url", cwd=cwd,
        )
    except PublicacaoErro:
        return None
    itens = json.loads(bruto or "[]")
    if not itens:
        return None
    return {"numero": itens[0]["number"], "url": itens[0]["url"]}


async def _limpar(repo: Path, trabalho: Path) -> None:
    """Some com o worktree temporário, doa ou não tenha dado certo."""
    try:
        await _rodar("git", "worktree", "remove", "--force", str(trabalho), cwd=repo)
    except PublicacaoErro:
        # `remove` falha se o `add` nem chegou a acontecer. O diretório solto é
        # o que sobra, e ele não pode ficar: na próxima vez o `add` recusaria.
        shutil.rmtree(trabalho, ignore_errors=True)
        await _rodar("git", "worktree", "prune", cwd=repo)


async def estado_pr(post, *, repo: Path | None = None) -> dict:
    """Situação do PR: estado, checks e se dá para mergear.

    `pendente` e "não existe" são coisas diferentes, e a tela precisa das duas:
    post sem PR mostra o botão de publicar; post com PR mostra os checks.
    """
    if not post.pr_numero:
        return {"existe": False, "estado": None, "checks": [], "mergeavel": False}

    repo = repo or _repo()
    bruto = await _rodar(
        "gh", "pr", "view", str(post.pr_numero),
        "--json", "state,url,mergeable,mergeStateStatus,statusCheckRollup",
        cwd=repo,
    )
    dados = json.loads(bruto)
    checks = [
        {
            "nome": c.get("name") or c.get("context") or "?",
            "resultado": (c.get("conclusion") or c.get("state") or "PENDENTE").upper(),
            "url": c.get("detailsUrl") or c.get("targetUrl"),
        }
        for c in dados.get("statusCheckRollup") or []
    ]
    verdes = bool(checks) and all(c["resultado"] == "SUCCESS" for c in checks)
    return {
        "existe": True,
        "estado": dados.get("state"),
        "url": dados.get("url"),
        "checks": checks,
        "checks_verdes": verdes,
        # `CLEAN` é o único estado do GitHub que significa "pode mergear agora".
        # `BLOCKED` costuma ser check pendente; `BEHIND`, branch atrás da main —
        # que aqui não acontece, porque a branch nasce da `origin/main`.
        "merge_status": dados.get("mergeStateStatus"),
        "mergeavel": dados.get("state") == "OPEN"
        and verdes
        and dados.get("mergeStateStatus") == "CLEAN",
    }


async def mergear(post, *, repo: Path | None = None) -> dict:
    """Squash merge do PR — o passo que põe o post no ar.

    `--subject` e `--body` explícitos de propósito: sem eles o GitHub monta a
    mensagem do squash juntando os commits da branch, trailers inclusive, e
    este projeto não quer linha de co-autoria no histórico.
    """
    if not post.pr_numero:
        raise PublicacaoErro("este post não tem PR aberto")

    repo = repo or _repo()
    situacao = await estado_pr(post, repo=repo)
    if situacao["estado"] != "OPEN":
        raise PublicacaoErro(f"o PR #{post.pr_numero} está {situacao['estado']}")
    if not situacao["mergeavel"]:
        vermelhos = [c["nome"] for c in situacao["checks"] if c["resultado"] != "SUCCESS"]
        raise PublicacaoErro(
            "ainda não dá para mergear: "
            + (f"checks {', '.join(vermelhos)}" if vermelhos else situacao["merge_status"])
        )

    assunto, _ = _mensagem(post)
    await _rodar(
        "gh", "pr", "merge", str(post.pr_numero),
        "--squash", "--delete-branch",
        "--subject", f"{assunto} (#{post.pr_numero})",
        "--body", (post.descricao or "").strip(),
        cwd=repo,
    )
    logger.info(f"Blog: PR #{post.pr_numero} mergeado — {post.slug}")
    return {"pr_numero": post.pr_numero, "url": f"{settings.blog_url}/blog/{post.slug}"}
