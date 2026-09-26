"""O quadro de pendências: criar, mover, editar, apagar.

Duas regras moram aqui:

1. **`concluida_em` segue a coluna.** Entrou em "feito", ganha a data; saiu,
   perde. Se dependesse de quem chama lembrar, o "quando terminei" mentiria no
   primeiro cartão arrastado de volta.
2. **Cartão novo vai para o fim da coluna.** A ordem é de quem arrasta; o
   serviço só garante que ninguém nasce em cima de um cartão que já estava lá.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select

from app.db.models.pendencia import COLUNAS, Pendencia
from app.db.session import get_session

EDITAVEIS = ("titulo", "descricao", "topico", "quando", "prazo", "onde", "coluna", "ordem")


class PendenciaErro(Exception):
    """Problema de uso do quadro que o chamador precisa tratar."""


class PendenciaNaoEncontrada(PendenciaErro):
    pass


def _conferir_coluna(coluna: str) -> None:
    if coluna not in COLUNAS:
        raise PendenciaErro(f"coluna inválida: {coluna}. Use uma de {list(COLUNAS)}.")


async def listar(*, topico: str | None = None) -> Sequence[Pendencia]:
    """Todas, na ordem do quadro: coluna, posição, e o prazo mais perto primeiro."""
    async with get_session() as session:
        q = select(Pendencia)
        if topico:
            q = q.where(Pendencia.topico == topico)
        q = q.order_by(
            Pendencia.coluna,
            Pendencia.ordem,
            Pendencia.prazo.asc().nulls_last(),
            Pendencia.created_at,
        )
        return (await session.execute(q)).scalars().all()


async def topicos() -> list[str]:
    """Os tópicos em uso, na ordem em que apareceram (é a ordem das colunas do MD)."""
    async with get_session() as session:
        q = (
            select(Pendencia.topico, func.min(Pendencia.created_at).label("primeiro"))
            .group_by(Pendencia.topico)
            .order_by("primeiro", Pendencia.topico)
        )
        return [t for t, _ in (await session.execute(q)).all()]


async def obter(pendencia_id: UUID) -> Pendencia:
    async with get_session() as session:
        p = await session.get(Pendencia, pendencia_id)
        if p is None:
            raise PendenciaNaoEncontrada(f"pendência {pendencia_id} não existe")
        return p


async def _proxima_ordem(session, coluna: str) -> int:
    atual = await session.scalar(
        select(func.max(Pendencia.ordem)).where(Pendencia.coluna == coluna)
    )
    return (atual if atual is not None else -1) + 1


async def criar(
    *,
    titulo: str,
    topico: str,
    descricao: str | None = None,
    quando: str | None = None,
    prazo: date | None = None,
    onde: str | None = None,
    coluna: str = "a_fazer",
) -> Pendencia:
    _conferir_coluna(coluna)
    if not titulo.strip() or not topico.strip():
        raise PendenciaErro("título e tópico são obrigatórios")
    async with get_session() as session:
        p = Pendencia(
            titulo=titulo.strip(),
            topico=topico.strip(),
            descricao=(descricao or "").strip() or None,
            quando=(quando or "").strip() or None,
            prazo=prazo,
            onde=(onde or "").strip() or None,
            coluna=coluna,
            ordem=await _proxima_ordem(session, coluna),
            concluida_em=datetime.now(UTC) if coluna == "feito" else None,
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p


async def atualizar(pendencia_id: UUID, **campos) -> Pendencia:
    """Muda só o que veio. Mudar de coluna sem `ordem` põe o cartão no fim dela."""
    desconhecidos = set(campos) - set(EDITAVEIS)
    if desconhecidos:
        raise PendenciaErro(f"campo(s) não editável(is): {sorted(desconhecidos)}")
    async with get_session() as session:
        p = await session.get(Pendencia, pendencia_id)
        if p is None:
            raise PendenciaNaoEncontrada(f"pendência {pendencia_id} não existe")

        nova = campos.get("coluna")
        if nova is not None and nova != p.coluna:
            _conferir_coluna(nova)
            if "ordem" not in campos:
                campos["ordem"] = await _proxima_ordem(session, nova)
            p.concluida_em = datetime.now(UTC) if nova == "feito" else None

        for nome in ("titulo", "topico"):
            if nome in campos and not (campos[nome] or "").strip():
                raise PendenciaErro(f"{nome} não pode ficar vazio")
        # Texto vazio vira NULL; título e tópico já foram barrados acima.
        for nome, valor in campos.items():
            if isinstance(valor, str):
                valor = valor.strip() or None
            setattr(p, nome, valor)

        await session.commit()
        await session.refresh(p)
        return p


async def apagar(pendencia_id: UUID) -> None:
    async with get_session() as session:
        p = await session.get(Pendencia, pendencia_id)
        if p is None:
            raise PendenciaNaoEncontrada(f"pendência {pendencia_id} não existe")
        await session.delete(p)
        await session.commit()
