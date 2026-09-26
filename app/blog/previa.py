"""Ver o post como ele vai ficar — no blog de verdade, não numa imitação.

A alternativa era renderizar o MDX aqui dentro. Não vale: o blog tem Shiki,
KaTeX, Mermaid, `@tailwindcss/typography` e componentes próprios (`Callout`,
`Figure`, `CTA`), e reproduzir isso no painel seria manter **dois
renderizadores** — com a garantia de que, no dia em que discordarem, a prévia
mente e eu descubro depois de publicar. É a mesma razão de a régua das camadas
morar só no backend.

Então a prévia usa o blog: escreve o `.mdx` como rascunho, manda o blog regerar
o índice e devolve a URL do `next dev`. Rascunho já aparece no dev — o
`src/content/posts.ts` do blog inclui `draft: true` quando `NODE_ENV` não é
produção.

De brinde, o gerador do índice é quem roda o **linter de privacidade** e a
validação do frontmatter do blog (`scripts/gerar-indice-conteudo.ts`). Prévia
que falha por causa deles é a melhor hora possível para descobrir: antes do
commit, e não no CI de um PR.

O que a prévia **não** faz: marcar o post como exportado. Ela escreve o arquivo
(não tem como não escrever — o blog lê de `content/blog/`), mas sempre com
`draft: true`, e `exportado_em` continua significando "eu mandei de propósito".
"""
from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from urllib.parse import urlparse

from app.blog import mdx
from app.config import LOGS_DIR, settings
from app.utils.logger import get_logger

logger = get_logger()

# O gerador é rápido (lê uns poucos .mdx e escreve um arquivo). O limite existe
# para o caso de o npm resolver baixar algo: melhor um erro claro em um minuto
# do que um request pendurado até o proxy desistir.
TIMEOUT_S = 60
# Quanto esperar o `next dev` do blog abrir a porta depois de subir. Medido: o
# Next 16 abre em ~3 s; a compilação da primeira página vem depois, e quem espera
# por ela é a aba do navegador, não a API.
SUBIDA_S = 45


class PreviaErro(Exception):
    """A prévia não pôde ser montada. A mensagem é para eu ler e agir."""


def _servidor_de_pe(url: str) -> bool:
    """O `next dev` do blog está atendendo?

    Porta aberta, e não um GET: a resposta do Next para uma rota que ainda não
    existe é 404, e 404 aqui significaria "suba o servidor" quando o servidor
    está de pé e o índice é que não foi regerado — a mensagem errada para o
    problema certo.
    """
    alvo = urlparse(url)
    porta = alvo.port or (443 if alvo.scheme == "https" else 80)
    try:
        with socket.create_connection((alvo.hostname or "localhost", porta), timeout=1.5):
            return True
    except OSError:
        return False


async def gerar_indice(repo: Path) -> tuple[int, str]:
    """`npm run conteudo` no repo do blog: relê `content/blog/` e valida tudo.

    Devolve o código de saída e a saída junta (stdout + stderr) — o gerador
    escreve os erros de schema e de privacidade em texto, e é esse texto que
    tem valor para mim.
    """
    processo = await asyncio.create_subprocess_exec(
        "npm",
        "run",
        "conteudo",
        cwd=str(repo),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(), timeout=TIMEOUT_S)
    except TimeoutError:
        processo.kill()
        raise PreviaErro(
            f"`npm run conteudo` passou de {TIMEOUT_S}s no repo do blog"
        ) from None
    return processo.returncode or 0, saida.decode("utf-8", "replace").strip()


async def subir_blog(repo: Path, url_dev: str) -> bool:
    """Sobe o `next dev` do blog, se estiver parado, e espera a porta abrir.

    Era o passo que eu esquecia: a prévia abria uma aba morta e o aviso dizia
    "rode `npm run dev`". Agora a API sobe o servidor, em sessão própria (não
    morre quando a API reinicia) e com a saída num log, não no terminal de
    ninguém.
    """
    if _servidor_de_pe(url_dev):
        return True
    porta = str(urlparse(url_dev).port or 3000)
    log = open(LOGS_DIR / "blog-dev.log", "ab")  # noqa: SIM115 — fica aberto com o processo
    await asyncio.create_subprocess_exec(
        "npm", "run", "dev", "--", "-p", porta,
        cwd=str(repo),
        stdout=log,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )
    logger.info(f"Blog: subindo o `next dev` na porta {porta}")
    for _ in range(SUBIDA_S * 2):
        await asyncio.sleep(0.5)
        if _servidor_de_pe(url_dev):
            return True
    return False


async def montar(post, *, repo: Path | None = None, url_dev: str | None = None) -> dict:
    """Escreve o rascunho, regera o índice e devolve a URL para abrir."""
    repo = Path(repo or settings.blog_repo_dir).expanduser()
    url_dev = (url_dev or settings.blog_dev_url).rstrip("/")

    if not (repo / "content" / "blog").is_dir():
        raise PreviaErro(
            f"não achei o repo do blog em {repo} — ajuste BLOG_REPO_DIR"
        )

    # Rascunho: a prévia não é a hora de decidir que o post está pronto. Post no
    # ar é a exceção — escrevê-lo como rascunho no repo seria um `draft: true`
    # esperando para ser commitado por engano.
    caminho = mdx.exportar(
        post, diretorio=repo / "content" / "blog", rascunho=post.estado != "publicado"
    )

    codigo, saida = await gerar_indice(repo)
    if codigo != 0:
        # O gerador reprova por frontmatter inválido **ou** pelo linter de
        # privacidade. Os dois são coisas que eu preciso ver inteiras.
        raise PreviaErro(saida or f"`npm run conteudo` saiu com {codigo}")

    de_pe = await subir_blog(repo, url_dev)
    logger.info(f"Blog: prévia de {post.slug} ({'dev de pé' if de_pe else 'dev fora'})")
    return {
        "url": f"{url_dev}/blog/{post.slug}",
        "caminho": str(caminho),
        "servidor_de_pe": de_pe,
        "aviso": None
        if de_pe
        else f"o `next dev` do blog não subiu em {SUBIDA_S}s — veja logs/blog-dev.log",
    }
