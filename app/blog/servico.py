"""As regras da redação: criar, salvar, versionar, mudar de estado, exportar.

Três coisas moram aqui e em nenhum outro lugar:

1. **Salvar que muda o corpo guarda a versão de antes.** Não é opcional e não
   depende de o painel pedir: autosave sem histórico perde parágrafo, e o
   parágrafo se perde justamente no salvamento que ninguém mandou fazer.
2. **`pronto` tem portão.** Só entra o post cujas cinco camadas estão verdes e
   cujo frontmatter passa no schema do blog. Os outros estados são livres — um
   rascunho pode voltar a ser pauta no dia em que eu desistir dele.
3. **Exportar não publica.** Escreve o `.mdx` e marca `exportado_em`. Commit,
   PR e merge continuam meus.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.blog import camadas as camadas_mod
from app.blog import mdx, taxonomia
from app.config import settings
from app.db.models.blog import ESTADOS, BlogPost, BlogPostVersao
from app.db.observability import registrar_evento
from app.db.session import get_session
from app.utils.logger import get_logger

logger = get_logger()

# Campos que o painel pode escrever. Lista branca e não `setattr` do que vier:
# o corpo do PATCH é JSON de fora, e `estado` tem portão próprio — deixá-lo
# entrar por aqui seria a porta dos fundos do `marcar_pronto`.
CAMPOS_EDITAVEIS = frozenset(
    {
        "titulo", "slug", "descricao", "pilar", "tags", "corpo", "notas", "origem",
        "data_publicacao", "linkedin_texto", "linkedin_em",
    }
)


class BlogErro(Exception):
    """Problema de uso que o chamador precisa tratar."""


class PostNaoEncontrado(BlogErro):
    pass


class EstadoInvalido(BlogErro):
    pass


class NaoEstaPronto(BlogErro):
    """As camadas ou o frontmatter reprovaram. A mensagem lista o que falta."""


# ── Post no ar ────────────────────────────────────────────────────
#
# Editar depois de publicado é permitido — corrigir número, trocar link morto é
# o que a auditoria trimestral pede. O que **não** muda é o endereço: `slug` e
# `data` de post no ar quebrariam o link que já foi compartilhado e a ordem do
# blog. E o site só muda quando eu publico a atualização (PR + merge), como na
# primeira vez.
TRAVADOS_NO_AR = frozenset({"slug", "data_publicacao"})


def assinatura(post: BlogPost) -> str:
    """O que o leitor vê, resumido num hash. Muda = há o que publicar."""
    import hashlib
    import json

    dados = {
        "titulo": post.titulo,
        "descricao": post.descricao,
        "pilar": post.pilar,
        "tags": list(post.tags or []),
        "origem": list(post.origem or []),
        "corpo": (post.corpo or "").strip(),
    }
    return hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()


def alteracoes_nao_publicadas(post: BlogPost) -> bool:
    return bool(
        post.estado == "publicado"
        and post.publicado_hash
        and assinatura(post) != post.publicado_hash
    )


def rascunho_no_arquivo(post: BlogPost) -> bool:
    """`draft: true` no MDX? Nunca para post no ar — ele sumiria do site."""
    return post.estado not in ("pronto", "publicado")


async def criar(
    *,
    titulo: str,
    pilar: str | None = None,
    origem: list[dict] | None = None,
    corpo: str = "",
    notas: str | None = None,
) -> BlogPost:
    """Nasce como pauta: um título e, quando houver, de onde a ideia veio."""
    async with get_session() as session:
        post = BlogPost(
            titulo=titulo.strip(),
            pilar=pilar,
            origem=origem or [],
            corpo=corpo,
            notas=notas,
            estado="rascunho" if corpo.strip() else "pauta",
            tags=[],
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)

    logger.info(f"Blog: nova {post.estado} — {post.titulo[:60]!r}")
    await registrar_evento("blog.criado", status="ok", detalhe=post.titulo[:120])
    return post


async def obter(post_id: UUID) -> BlogPost:
    async with get_session() as session:
        post = await session.get(BlogPost, post_id)
    if post is None:
        raise PostNaoEncontrado(f"Post {post_id} não existe.")
    return post


async def listar(
    *, estado: str | None = None, limite: int = 100, offset: int = 0
) -> tuple[int, list[BlogPost]]:
    """A lista do painel: o que eu mexi por último em cima."""
    filtros = []
    if estado:
        if estado not in ESTADOS:
            raise EstadoInvalido(f"estado inválido: {estado}. Use um de {list(ESTADOS)}.")
        filtros.append(BlogPost.estado == estado)

    async with get_session() as session:
        total = await session.scalar(select(func.count(BlogPost.id)).where(*filtros)) or 0
        itens = (
            await session.scalars(
                select(BlogPost)
                .where(*filtros)
                .order_by(BlogPost.updated_at.desc())
                .limit(limite)
                .offset(offset)
            )
        ).all()
    return int(total), list(itens)


async def contar_por_estado() -> dict[str, int]:
    async with get_session() as session:
        linhas = await session.execute(
            select(BlogPost.estado, func.count()).group_by(BlogPost.estado)
        )
    return {e: int(n) for e, n in linhas}


async def salvar(post_id: UUID, campos: dict[str, Any]) -> BlogPost:
    """Grava os campos editáveis. Se o corpo mudou, a versão de antes é guardada.

    A versão é escrita **na mesma transação** da edição: guardar depois, num
    worker ou num segundo commit, abre a janela em que o texto novo já existe e
    o antigo já não — que é exatamente o instante em que um crash apaga o
    parágrafo que eu queria de volta.
    """
    desconhecidos = set(campos) - CAMPOS_EDITAVEIS
    if desconhecidos:
        raise BlogErro(f"campo não editável: {', '.join(sorted(desconhecidos))}")

    async with get_session() as session:
        post = await session.get(BlogPost, post_id)
        if post is None:
            raise PostNaoEncontrado(f"Post {post_id} não existe.")

        if post.estado == "publicado":
            mudou = [
                c for c in TRAVADOS_NO_AR
                if c in campos and str(campos[c] or "") != str(getattr(post, c) or "")
            ]
            if mudou:
                raise BlogErro(
                    f"post no ar não muda {', '.join(sorted(mudou))}: "
                    "o link já compartilhado quebraria"
                )
            # Post publicado antes desta coluna existir: o que está no banco
            # agora é o que está no ar. Guardar antes da primeira edição.
            if not post.publicado_hash:
                post.publicado_hash = assinatura(post)

        corpo_novo = campos.get("corpo")
        mudou_corpo = corpo_novo is not None and corpo_novo != post.corpo
        if mudou_corpo:
            ultimo = await session.scalar(
                select(func.max(BlogPostVersao.numero)).where(BlogPostVersao.post_id == post.id)
            )
            session.add(
                BlogPostVersao(
                    post_id=post.id,
                    numero=int(ultimo or 0) + 1,
                    titulo=post.titulo,
                    corpo=post.corpo,
                    palavras=camadas_mod.palavras(post.corpo),
                )
            )

        for campo, valor in campos.items():
            if campo in ("titulo", "descricao", "notas", "linkedin_texto") and isinstance(
                valor, str
            ):
                valor = valor.strip() or (None if campo != "titulo" else post.titulo)
            if campo in ("data_publicacao", "linkedin_em") and isinstance(valor, str):
                valor = date.fromisoformat(valor)
            setattr(post, campo, valor)

        # Pauta que ganhou corpo virou rascunho. É a única transição automática:
        # as outras são decisão, e decisão tem botão.
        if post.estado == "pauta" and (post.corpo or "").strip():
            post.estado = "rascunho"

        await session.commit()
        await session.refresh(post)
    return post


async def versoes(post_id: UUID, *, limite: int = 20) -> list[BlogPostVersao]:
    async with get_session() as session:
        itens = (
            await session.scalars(
                select(BlogPostVersao)
                .where(BlogPostVersao.post_id == post_id)
                .order_by(BlogPostVersao.numero.desc())
                .limit(limite)
            )
        ).all()
    return list(itens)


def diagnostico(post: BlogPost) -> dict[str, Any]:
    """O que a coluna direita do editor mostra: camadas, frontmatter, tamanho."""
    camadas = camadas_mod.analisar(
        corpo=post.corpo or "",
        descricao=post.descricao,
        tags=list(post.tags or []),
        origem=list(post.origem or []),
    )
    erros_fm = taxonomia.validar_frontmatter(
        slug=post.slug,
        titulo=post.titulo,
        descricao=post.descricao,
        pilar=post.pilar,
        tags=list(post.tags or []),
        data=post.data_publicacao,
        origem=list(post.origem or []),
    )
    abertas = camadas_mod.faltas(post.corpo or "")
    return {
        "alteracoes_nao_publicadas": alteracoes_nao_publicadas(post),
        "faltas": abertas,
        "camadas": [
            {
                "id": c.id,
                "rotulo": c.rotulo,
                "publico": c.publico,
                "pergunta": c.pergunta,
                "ok": c.ok,
                "sinais": [{"ok": s.ok, "texto": s.texto, "dica": s.dica} for s in c.sinais],
            }
            for c in camadas
        ],
        "camadas_ok": camadas_mod.tudo_verde(camadas),
        "falta": camadas_mod.o_que_falta(camadas),
        "frontmatter_erros": erros_fm,
        "exportavel": camadas_mod.tudo_verde(camadas) and not erros_fm and not abertas,
        "palavras": camadas_mod.palavras(post.corpo or ""),
        "minutos": camadas_mod.minutos_de_leitura(post.corpo or ""),
    }


async def mudar_estado(post_id: UUID, estado: str) -> BlogPost:
    """Transição de estado. `pronto` é o único com portão."""
    if estado not in ESTADOS:
        raise EstadoInvalido(f"estado inválido: {estado}. Use um de {list(ESTADOS)}.")

    post = await obter(post_id)
    if estado == "pronto":
        d = diagnostico(post)
        if not d["exportavel"]:
            marcadores = [f"{{{{FALTA: {f}}}}} aberto" for f in d["faltas"]]
            raise NaoEstaPronto("; ".join(d["falta"] + d["frontmatter_erros"] + marcadores))

    async with get_session() as session:
        alvo = await session.get(BlogPost, post_id)
        alvo.estado = estado
        await session.commit()
        await session.refresh(alvo)

    await registrar_evento("blog.estado", status="ok", detalhe=f"{alvo.titulo[:60]} → {estado}")
    return alvo


def previa(post: BlogPost, *, rascunho: bool | None = None) -> str:
    """O `.mdx` que sairia — para olhar antes de escrever no repo do blog."""
    if rascunho is None:
        rascunho = post.estado != "pronto"
    return mdx.montar(post, rascunho=rascunho)


async def exportar(post_id: UUID, *, diretorio: str | Path | None = None) -> dict[str, Any]:
    """Escreve `content/blog/<slug>.mdx` no repo do blog. Não faz commit.

    O post vira `publicado` aqui? Não: vira quando o PR entra. O que esta função
    marca é `exportado_em` — o arquivo existe, e o resto do caminho é meu.
    """
    post = await obter(post_id)
    destino_dir = diretorio or settings.blog_content_dir
    caminho = mdx.exportar(post, diretorio=destino_dir, rascunho=rascunho_no_arquivo(post))

    async with get_session() as session:
        alvo = await session.get(BlogPost, post_id)
        alvo.exportado_em = datetime.now(UTC)
        await session.commit()

    logger.info(f"Blog: exportado {caminho}")
    await registrar_evento("blog.exportado", status="ok", detalhe=str(caminho.name))
    return {"caminho": str(caminho), "bytes": caminho.stat().st_size}
