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

from datetime import UTC, date, datetime
from uuid import UUID

from app.blog import publicacao, servico, vault
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
    if post.estado == "publicado":
        # Atualização de post no ar: o mesmo portão do `pronto`, e só se houver
        # o que publicar. A data da correção entra no frontmatter (`atualizado`).
        d = servico.diagnostico(post)
        if not d["exportavel"]:
            marcadores = [f"{{{{FALTA: {f}}}}} aberto" for f in d["faltas"]]
            raise servico.NaoEstaPronto(
                "; ".join(d["falta"] + d["frontmatter_erros"] + marcadores)
            )
        if not servico.alteracoes_nao_publicadas(post):
            raise servico.NaoEstaPronto("nada mudou desde a publicação")
        async with get_session() as session:
            alvo = await session.get(BlogPost, post_id)
            alvo.atualizado = max(date.today(), alvo.data_publicacao or date.today())
            await session.commit()
        post = await servico.obter(post_id)
    elif post.estado != "pronto":
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
    atualizacao = post.estado == "publicado"
    dados = await publicacao.mergear(post)

    async with get_session() as session:
        alvo = await session.get(BlogPost, post_id)
        alvo.estado = "publicado"
        # Atualização não muda a data de publicação: o post é o mesmo, com
        # `atualizado` no frontmatter.
        if not atualizacao:
            alvo.publicado_em = datetime.now(UTC)
        alvo.publicado_hash = servico.assinatura(alvo)
        # A branch morre junto (`--delete-branch`); guardar o nome depois disso
        # seria apontar para o que não existe mais.
        alvo.branch = None
        await session.commit()

    # A nota do vault que originou o post passa a `publicado` (§9.3 do plano do
    # blog). Falhar aqui não desfaz o merge: é uma propriedade no Obsidian.
    for item in post.origem or []:
        if isinstance(item, dict) and item.get("vault"):
            try:
                vault.marcar(item["vault"], "publicado")
            except (vault.VaultErro, OSError):
                pass

    await registrar_evento(
        "blog.atualizado" if atualizacao else "blog.publicado", status="ok", detalhe=post.slug or ""
    )
    return dados
