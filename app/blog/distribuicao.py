"""Um post, uma saída a mais: o texto do LinkedIn, na mesma régua de voz.

É o **N4** do plano do blog (§9.4) e a rotina da Etapa 11 (§11.5): a cada post
publicado, um post próprio no LinkedIn — a cena da abertura, o número do
resultado, uma frase do que aprendi, e o link no fim. Sem o código.

O Copiloto **não posta**. Gera, eu edito no painel, copio e colo. Integração
com a API do LinkedIn seria um token de rede social guardado aqui em troca de
economizar um Ctrl+V por semana.
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.blog import geracao, servico
from app.config import settings
from app.db.models.blog import BlogPost
from app.db.observability import registrar_evento
from app.db.session import get_session
from app.llm import gateway
from app.llm import voz as voz_mod

MAX_PALAVRAS = 220
MAX_HASHTAGS = 3
_HASHTAG = re.compile(r"(?:^|\s)#\w+")


def url_do_post(slug: str) -> str:
    return f"{settings.blog_url.rstrip('/')}/blog/{slug}"


def proxima_data(publicado: date) -> date:
    """Quarta seguinte à publicação — a rotina da Etapa 11 (§11.5)."""
    dias = (2 - publicado.weekday()) % 7 or 7
    return publicado + timedelta(days=dias)


def checar(texto: str, *, slug: str) -> list[str]:
    """A régua do LinkedIn: tamanho, link, voz. Lista vazia = passou."""
    problemas: list[str] = []
    palavras = len(texto.split())
    if palavras > MAX_PALAVRAS:
        problemas.append(f"{palavras} palavras (máximo {MAX_PALAVRAS})")
    if url_do_post(slug) not in texto:
        problemas.append("falta o link do post no fim")
    if "```" in texto:
        problemas.append("tem bloco de código — no LinkedIn, só o resultado")
    if len(_HASHTAG.findall(texto)) > MAX_HASHTAGS:
        problemas.append(f"mais de {MAX_HASHTAGS} hashtags")
    baixo = texto.lower()
    for padrao, rotulo in voz_mod.FRASES_PROIBIDAS:
        if achado := re.search(padrao, baixo):
            problemas.append(f"frase proibida ({rotulo}): {achado.group(0)!r}")
    if voz_mod._EMOJI.search(texto):
        problemas.append("tem emoji")
    return problemas


def _prompt(titulo: str, corpo: str, url: str) -> str:
    proibidas = "\n".join(f"- {rotulo}" for _, rotulo in voz_mod.FRASES_PROIBIDAS)
    return f"""Escreva o post do LinkedIn que divulga o post do blog abaixo.

Quem lê no LinkedIn é recrutador e cliente, rolando a tela. A ordem:

1. A cena da abertura do post, em uma ou duas frases. Nunca "Novo post no blog!".
2. O número do resultado, com unidade (antes e depois, se houver).
3. Uma frase do que eu aprendi ou faria diferente — opinião, não resumo.
4. O link, sozinho na última linha: {url}

Regras:
- No máximo {MAX_PALAVRAS} palavras. Parágrafos de uma ou duas frases.
- Sem código, sem emoji, sem negrito, no máximo {MAX_HASHTAGS} hashtags no fim.
- Primeira pessoa, português do Brasil.
- Nada que não esteja no post: nenhum número, empresa ou tecnologia a mais.

Frases proibidas:
{proibidas}

## O post

Título: {titulo}

{geracao.higienizar(corpo)}

Devolva só o texto do LinkedIn, sem título e sem aspas em volta.
"""


async def gerar_linkedin(post_id: UUID) -> dict:
    """Gera o texto, mede, e se reprovar devolve ao modelo o que faltou — uma vez."""
    post = await servico.obter(post_id)
    if post.estado not in ("pronto", "publicado"):
        raise geracao.GeracaoErro("o LinkedIn sai de post pronto ou publicado")
    if not post.slug:
        raise geracao.GeracaoErro("o post precisa de slug: é o link do LinkedIn")
    await geracao._exigir_orcamento()

    url = url_do_post(post.slug)
    r = await gateway.gerar(
        _prompt(post.titulo, post.corpo or "", url),
        tarefa="redigir",
        agente="blog.linkedin",
        alvo_ref=str(post.id),
    )
    texto = r.texto.strip().strip('"')
    problemas = checar(texto, slug=post.slug)
    if problemas:
        await geracao._exigir_orcamento()
        lista = "\n".join(f"- {p}" for p in problemas)
        r = await gateway.gerar(
            f"Corrija só isto no texto abaixo e devolva o texto inteiro:\n{lista}\n\n"
            f"O link tem que ser a última linha: {url}\n\n{texto}",
            tarefa="redigir",
            agente="blog.linkedin",
            alvo_ref=str(post.id),
        )
        texto = r.texto.strip().strip('"')
        problemas = checar(texto, slug=post.slug)

    campos: dict = {"linkedin_texto": texto}
    if post.linkedin_em is None:
        base = post.publicado_em.date() if post.publicado_em else date.today()
        campos["linkedin_em"] = proxima_data(base).isoformat()
    await servico.salvar(post.id, campos)

    await registrar_evento("blog.linkedin_gerado", status="ok", detalhe=post.slug)
    return {"texto": texto, "pendentes": problemas, "gasto_usd": await geracao.gasto_do_mes()}


async def marcar_postado(post_id: UUID) -> BlogPost:
    """Eu postei. O painel para de cobrar este post."""
    await servico.obter(post_id)
    async with get_session() as session:
        alvo = await session.get(BlogPost, post_id)
        alvo.linkedin_postado_em = datetime.now(UTC)
        await session.commit()
        await session.refresh(alvo)
    await registrar_evento("blog.linkedin_postado", status="ok", detalhe=alvo.slug or "")
    return alvo
