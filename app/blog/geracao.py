"""Rascunho gerado pelo Gemini, na voz de post, medido pela régua das camadas.

O que torna isto diferente de colar a nota no chat:

1. **A régua volta para o modelo.** Depois de gerar, o texto é medido com as
   mesmas cinco camadas que o portão do `pronto` usa, e o que faltou volta ao
   modelo como lista ("falta número com unidade", "a abertura tem 90 palavras")
   em vez de "melhore". No máximo `RODADAS` voltas; o que sobrar vermelho fica
   na coluna da direita do editor, para mim.
2. **O vazio é admitido.** Onde a matéria-prima não tem experiência própria, o
   modelo escreve `{{FALTA: …}}` em vez de inventar. O marcador bloqueia o
   `pronto` (`servico.diagnostico`) e quebraria o build do MDX de qualquer jeito.
3. **Nada é publicado.** O texto entra no corpo do post, que é versionado: a
   versão de antes fica guardada, e daí para a frente é o caminho de sempre —
   eu reescrevo, marco pronto, abro PR, mergeio.

## O que sai da máquina (§10.3 C do plano do blog)

Só a matéria-prima lida da `origem` — nota de pasta liberada do vault, ou doc
do próprio Copiloto — passada pelo `higienizar`, mais os posts **já publicados**
(que são públicos). Nunca o campo `notas` do post, nunca o perfil.

## Dinheiro

Chave própria (`GEMINI_API_KEY_BLOG`) e teto do mês conferido **antes** de cada
chamada, somando `ai_calls` dos agentes `blog.*`.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import func, select

from app.blog import camadas as camadas_mod
from app.blog import servico, vault
from app.config import BASE_DIR, settings
from app.conhecimento.fontes import _frontmatter
from app.db.models.ai_call import AiCall
from app.db.models.blog import BlogPost
from app.db.observability import registrar_evento
from app.db.session import get_session
from app.llm import gateway
from app.llm import voz as voz_mod
from app.utils.logger import get_logger

logger = get_logger()

SPEC_POST = BASE_DIR / "prompts" / "voz-post.md"
RODADAS = 3
MAX_MATERIA_PALAVRAS = 6000
MAX_EXEMPLO_PALAVRAS = 900


class GeracaoErro(servico.BlogErro):
    """Falta chave, estourou o teto, ou não há matéria-prima."""


# ── Dinheiro ──────────────────────────────────────────────────────


async def gasto_do_mes() -> float:
    """O que os agentes `blog.*` gastaram desde o dia 1º, em US$."""
    inicio = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with get_session() as session:
        total = await session.scalar(
            select(func.coalesce(func.sum(AiCall.custo_usd), 0)).where(
                AiCall.agente.like("blog.%"), AiCall.created_at >= inicio
            )
        )
    return float(total or 0)


async def situacao() -> dict:
    """O que o painel mostra ao lado dos botões de gerar."""
    gasto = await gasto_do_mes()
    teto = settings.blog_gemini_teto_usd_mes
    if not settings.gemini_api_key_blog:
        motivo = "falta a GEMINI_API_KEY_BLOG no .env do Copiloto"
    elif gasto >= teto:
        motivo = f"o teto do mês (US$ {teto:.2f}) foi atingido"
    else:
        motivo = None
    return {
        "disponivel": motivo is None,
        "motivo": motivo,
        "gasto_usd": round(gasto, 4),
        "teto_usd": teto,
        "modelo": settings.blog_gemini_modelo,
    }


async def _exigir_orcamento() -> None:
    s = await situacao()
    if not s["disponivel"]:
        raise GeracaoErro(s["motivo"])


# ── O que o modelo recebe ─────────────────────────────────────────

_CAMINHO_ABS = re.compile(r"(?:/home|/mnt|/root|/Users|/var|/etc|/tmp)/[^\s`'\")\]]+")
_WINDOWS = re.compile(r"[A-Za-z]:\\[^\s`'\"]+")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_TOKEN = re.compile(
    r"(?:AIza[\w-]{20,}|sk-[\w-]{16,}|ghp_\w{20,}|github_pat_\w{20,}|Bearer\s+[\w.-]{16,}"
    r"|postgres(?:ql)?(?:\+\w+)?://\S+)"
)


def higienizar(texto: str) -> str:
    """Tira do texto o que não pode sair da máquina nem entrar num post.

    É a mesma lista do linter de privacidade do blog (§10.3 B), aplicada
    **antes** do prompt: o linter do blog barra no CI, mas aí o texto já teria
    ido para a API.
    """
    texto = _TOKEN.sub("SEU_TOKEN_AQUI", texto)
    texto = _CAMINHO_ABS.sub("<caminho local>", texto)
    texto = _WINDOWS.sub("<caminho local>", texto)
    texto = _IP.sub("<ip>", texto)
    texto = _EMAIL.sub(
        lambda m: m.group(0) if m.group(0) == "contato@pabloortiz.dev" else "<e-mail>", texto
    )
    return texto


def _copiloto_liberado(relativo: str) -> bool:
    """Do repo do Copiloto, só `docs/*.md` e o README: é onde está o case."""
    rel = PurePosixPath(relativo)
    if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".md":
        return False
    return str(rel) == "README.md" or (len(rel.parts) == 2 and rel.parts[0] == "docs")


def _cortar(texto: str, maximo: int) -> str:
    palavras = texto.split(" ")
    return texto if len(palavras) <= maximo else " ".join(palavras[:maximo]) + " […]"


def materia_prima(post: BlogPost) -> list[tuple[str, str]]:
    """`[(rótulo, texto higienizado)]` a partir da `origem` do post."""
    saida: list[tuple[str, str]] = []
    for item in post.origem or []:
        if not isinstance(item, dict):
            continue
        if rel := item.get("vault"):
            _, corpo = vault.ler_nota(rel)
            saida.append((f"nota do vault: {rel}", corpo))
        elif rel := item.get("copiloto"):
            if not _copiloto_liberado(rel):
                raise GeracaoErro(f"`{rel}`: do Copiloto só entram docs/*.md e o README")
            arquivo = BASE_DIR / rel
            if not arquivo.is_file():
                raise GeracaoErro(f"`{rel}` não existe no Copiloto")
            saida.append((f"doc do Copiloto: {rel}", arquivo.read_text(encoding="utf-8")))
    return [(r, _cortar(higienizar(t), MAX_MATERIA_PALAVRAS)) for r, t in saida]


def publicados() -> list[dict]:
    """Os posts no ar, lidos do repo do blog: título, URL e corpo.

    Do disco e não do índice: o few-shot precisa do texto inteiro e em ordem,
    e o índice guarda pedaços.
    """
    raiz = settings.blog_content_dir
    if not raiz.is_dir():
        return []
    saida = []
    for arquivo in raiz.glob("*.mdx"):
        fm, corpo = _frontmatter(arquivo.read_text(encoding="utf-8"))
        if str(fm.get("draft", "false")).lower() == "true":
            continue
        saida.append(
            {
                "slug": arquivo.stem,
                "titulo": fm.get("titulo") or arquivo.stem,
                "data": str(fm.get("data") or ""),
                "url": f"/blog/{arquivo.stem}",
                "corpo": corpo.strip(),
            }
        )
    return sorted(saida, key=lambda p: p["data"], reverse=True)


def _prompt(post: BlogPost, materia: list[tuple[str, str]]) -> str:
    no_ar = [p for p in publicados() if p["slug"] != post.slug]
    exemplos = "\n\n".join(
        f"### Exemplo: {p['titulo']}\n\n{_cortar(p['corpo'], MAX_EXEMPLO_PALAVRAS)}"
        for p in no_ar[:2]
    )
    links = "\n".join(f"- {p['titulo']} → {p['url']}" for p in no_ar) or "(nenhum ainda)"
    fontes = "\n\n".join(f"### {rotulo}\n\n{texto}" for rotulo, texto in materia)

    return f"""{SPEC_POST.read_text(encoding="utf-8").strip()}

## Frases proibidas (as mesmas das mensagens)

{_proibidas_legiveis()}

## Posts já publicados (linke quando o assunto encostar, com o caminho relativo)

{links}

## Como eu escrevo (posts meus, só para o estilo — não copie o assunto)

{exemplos or "(ainda não há post publicado para servir de exemplo)"}

## A pauta

Título provisório: {post.titulo}
Pilar: {post.pilar or "—"}

## A matéria-prima

Tudo o que eu vivi, medi ou construí e que pode aparecer no post está aqui
embaixo. O que não está aqui, eu não vivi: não escreva em primeira pessoa sobre
isso — use {{{{FALTA: …}}}}.

{fontes}

## O que devolver

Exatamente este formato, sem mais nada antes ou depois:

DESCRICAO: <uma frase de 50 a 160 caracteres com o resultado, não o tema>
---
<o corpo do post em MDX, sem frontmatter e sem o título>
"""


def _proibidas_legiveis() -> str:
    return "\n".join(f"- {rotulo}" for _, rotulo in voz_mod.FRASES_PROIBIDAS)


def _revisao(corpo: str, descricao: str, problemas: list[str]) -> str:
    lista = "\n".join(f"- {p}" for p in problemas)
    return f"""{SPEC_POST.read_text(encoding="utf-8").strip()}

O rascunho abaixo foi medido e reprovou nestes pontos, e só nestes:

{lista}

Corrija **só** o que a lista pede. Não reescreva o que passou. Onde a correção
exigiria um fato que não está no texto (um número, um link de repositório),
use {{{{FALTA: …}}}} em vez de inventar.

Devolva no mesmo formato:

DESCRICAO: {descricao}
---
{corpo}
"""


def _ler_saida(texto: str) -> tuple[str, str]:
    """`DESCRICAO: …` / `---` / corpo. Tolerante a cerca de código em volta."""
    limpo = texto.strip()
    if limpo.startswith("```"):
        limpo = re.sub(r"^```\w*\n|\n```$", "", limpo).strip()
    m = re.match(r"DESCRI[ÇC][ÃA]O:\s*(.+?)\n-{3,}\n(.*)$", limpo, re.DOTALL | re.IGNORECASE)
    if not m:
        return "", limpo
    return m.group(1).strip(), m.group(2).strip()


def _problemas(post: BlogPost, corpo: str, descricao: str) -> list[str]:
    """Os sinais vermelhos **que o texto resolve**, cada um com a dica da régua.

    Tags ficam de fora da medida: são escolha minha, da lista curada do blog, e
    mandar "faltam tags" ao modelo gastaria uma rodada para ele não poder fazer
    nada. A dica vai junto porque é ela que diz *como* consertar.
    """
    tags = list(post.tags or []) or ["_"] * camadas_mod.MIN_TAGS
    camadas = camadas_mod.analisar(
        corpo=corpo,
        descricao=descricao or post.descricao,
        tags=tags,
        origem=list(post.origem or []),
    )
    problemas = [
        f"{c.rotulo}: {s.texto}" + (f" — {s.dica}" if s.dica else "")
        for c in camadas
        for s in c.sinais
        if not s.ok
    ]
    baixo = corpo.lower()
    for padrao, rotulo in voz_mod.FRASES_PROIBIDAS:
        if achado := re.search(padrao, baixo):
            problemas.append(f"frase proibida ({rotulo}): {achado.group(0)!r}")
    return problemas


async def gerar_rascunho(post_id: UUID) -> dict:
    """Gera, mede, devolve ao modelo o que faltou, e grava no corpo do post."""
    post = await servico.obter(post_id)
    if post.estado in ("publicado", "arquivado"):
        raise GeracaoErro(f"o post está `{post.estado}` — gerar aqui apagaria o que foi ao ar")
    materia = materia_prima(post)
    if not materia:
        raise GeracaoErro("sem matéria-prima: preencha a origem (nota do vault ou doc do Copiloto)")
    await _exigir_orcamento()

    r = await gateway.gerar(
        _prompt(post, materia), tarefa="redigir", agente="blog.rascunho", alvo_ref=str(post.id)
    )
    descricao, corpo = _ler_saida(r.texto)
    rodadas = 1
    problemas = _problemas(post, corpo, descricao)
    while problemas and rodadas < RODADAS:
        await _exigir_orcamento()
        r = await gateway.gerar(
            _revisao(corpo, descricao, problemas),
            tarefa="redigir",
            agente="blog.revisao",
            alvo_ref=str(post.id),
        )
        descricao, corpo = _ler_saida(r.texto)
        rodadas += 1
        problemas = _problemas(post, corpo, descricao)

    campos: dict = {"corpo": corpo}
    if descricao and not (post.descricao or "").strip():
        campos["descricao"] = descricao
    await servico.salvar(post.id, campos)

    await registrar_evento(
        "blog.rascunho_gerado", status="ok", detalhe=f"{post.titulo[:60]} · {rodadas} rodada(s)"
    )
    return {
        "rodadas": rodadas,
        "pendentes": problemas,
        "faltas": camadas_mod.faltas(corpo),
        "palavras": camadas_mod.palavras(corpo),
        "gasto_usd": round(await gasto_do_mes(), 4),
    }


def fonte_legivel(post: BlogPost) -> list[dict]:
    """A matéria-prima como o painel mostra: o que vai para o modelo, já limpo."""
    try:
        return [{"rotulo": r, "texto": t} for r, t in materia_prima(post)]
    except servico.BlogErro as e:
        return [{"rotulo": "erro", "texto": str(e)}]
