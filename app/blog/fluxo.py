"""O que o caminho até a `main` significa para o post, e o que fica gravado.

A divisão com `publicacao.py` é a de sempre nesta base: lá mora o **como**
(git, `gh`, worktree, saída de comando); aqui mora o **quê** (o post exige
estar pronto, o número do PR fica guardado, o estado muda uma vez só).

Ficou em módulo próprio, e não dentro do `servico.py`, porque são
responsabilidades diferentes: o serviço é o CRUD e a régua do texto; isto aqui
é a esteira que leva o texto para fora. Quem escreve post não mexe neste
arquivo, e quem mexe na esteira não precisa reler o CRUD.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.blog import publicacao, servico
from app.db.models.blog import BlogPost
from app.db.observability import registrar_evento
from app.db.session import get_session


async def abrir_pr(post_id: UUID) -> dict:
    """Branch, commit, push e PR — e guarda o número no post.

    Exige `pronto`. Não é burocracia: `pronto` é o estado que passou pelas
    cinco camadas e pelo frontmatter, e pedir revisão ao CI de um texto que a
    régua daqui já recusaria é gastar CI para ouvir o que eu já sabia.
    """
    post = await servico.obter(post_id)
    if post.estado != "pronto":
        raise servico.NaoEstaPronto(
            f"o post está como `{post.estado}` — marque pronto antes de publicar"
        )

    dados = await publicacao.abrir_pr(post)

    async with get_session() as session:
        alvo = await session.get(BlogPost, post_id)
        alvo.pr_numero = dados["pr_numero"]
        alvo.pr_url = dados["pr_url"]
        alvo.branch = dados["branch"]
        alvo.exportado_em = datetime.now(UTC)
        await session.commit()

    await registrar_evento("blog.pr", status="ok", detalhe=f"#{dados['pr_numero']}")
    return dados


async def situacao(post_id: UUID) -> dict:
    """O que a tela mostra enquanto o CI roda."""
    return await publicacao.estado_pr(await servico.obter(post_id))


async def concluir(post_id: UUID) -> dict:
    """Fecha o PR na `main` — o passo que leva o post ao ar.

    Só aqui o post vira `publicado`. Enquanto o PR está aberto ele continua
    `pronto`, porque PR aberto é texto esperando o CI, não texto publicado.
    """
    post = await servico.obter(post_id)
    dados = await publicacao.mergear(post)

    async with get_session() as session:
        alvo = await session.get(BlogPost, post_id)
        alvo.estado = "publicado"
        alvo.publicado_em = datetime.now(UTC)
        # A branch morre junto (`--delete-branch`); guardar o nome depois disso
        # seria apontar para o que não existe mais.
        alvo.branch = None
        await session.commit()

    await registrar_evento("blog.publicado", status="ok", detalhe=post.slug or "")
    return dados
