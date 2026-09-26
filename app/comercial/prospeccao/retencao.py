"""Supressão e retenção: o que sai da base e não volta.

`suprimir` atende o opt-out e o pedido do titular: apaga o que existe e grava
só o hash, que o importador consulta antes de gravar. Suprimir um CNPJ ou CNES
apaga o estabelecimento inteiro; suprimir um telefone ou e-mail apaga só o canal.

`aplicar_retencao` apaga o estabelecimento inativo há mais de 12 meses. Quando o
CRM da Fase 1 existir, estabelecimento com lead fica de fora (especificação).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.prospeccao import normalizacao as n
from app.db.models.comercial.prospeccao import (
    Atividade,
    Canal,
    Entidade,
    Estabelecimento,
    Identificador,
    MotivoSupressao,
    Origem,
    Situacao,
    Supressao,
    TipoCanal,
    TipoSupressao,
)

RETENCAO_INATIVO = timedelta(days=365)


def valor_canonico(tipo: TipoSupressao, valor: str) -> list[tuple[str, str]]:
    """(tipo de canal ou identificador, valor normalizado) que o valor cobre."""
    if tipo is TipoSupressao.TELEFONE:
        t = n.telefone(valor)
        return [(TipoCanal.TELEFONE, t.valor), (TipoCanal.CELULAR, t.valor)] if t else []
    if tipo is TipoSupressao.EMAIL:
        e = n.email(valor)
        return [(TipoCanal.EMAIL, e.valor)] if e else []
    d = n.so_digitos(valor)
    return [(tipo.value, d.zfill(7) if tipo is TipoSupressao.CNES else d)]


async def apagar_estabelecimentos(session: AsyncSession, ids: list[int]) -> None:
    """Apaga estabelecimentos e toda a proveniência deles (origem não tem FK)."""
    if not ids:
        return
    filhos = {
        Entidade.CANAL: Canal,
        Entidade.ATIVIDADE: Atividade,
        Entidade.IDENTIFICADOR: Identificador,
    }
    for entidade, modelo in filhos.items():
        sub = select(modelo.id).where(modelo.estabelecimento_id.in_(ids))
        await session.execute(delete(Origem).where(Origem.entidade == entidade, Origem.entidade_id.in_(sub)))
    await session.execute(
        delete(Origem).where(Origem.entidade == Entidade.ESTABELECIMENTO, Origem.entidade_id.in_(ids))
    )
    await session.execute(delete(Estabelecimento).where(Estabelecimento.id.in_(ids)))


async def suprimir(session: AsyncSession, tipo: TipoSupressao, valor: str, motivo: MotivoSupressao) -> int:
    """Apaga o que o valor cobre e grava o hash. Devolve quantas linhas saíram."""
    alvos = valor_canonico(tipo, valor)
    if not alvos:
        raise ValueError(f"valor inválido para {tipo}")
    apagadas = 0
    if tipo in (TipoSupressao.CNPJ, TipoSupressao.CNES):
        ids = list(
            await session.scalars(
                select(Identificador.estabelecimento_id).where(
                    Identificador.tipo == tipo.value, Identificador.valor == alvos[0][1]
                )
            )
        )
        await apagar_estabelecimentos(session, ids)
        apagadas = len(ids)
    else:
        canais = list(
            await session.scalars(
                select(Canal.id).where(Canal.valor == alvos[0][1], Canal.tipo.in_([t for t, _ in alvos]))
            )
        )
        if canais:
            await session.execute(delete(Origem).where(Origem.entidade == Entidade.CANAL, Origem.entidade_id.in_(canais)))
            await session.execute(delete(Canal).where(Canal.id.in_(canais)))
        apagadas = len(canais)
    await session.execute(
        insert(Supressao)
        .values(tipo=tipo.value, valor_hash=n.hash_valor(alvos[0][1]), motivo=motivo.value)
        .on_conflict_do_nothing(constraint="ux_prospeccao_supressao")
    )
    await session.commit()
    return apagadas


async def aplicar_retencao(session: AsyncSession, agora: datetime | None = None) -> int:
    """Apaga o inativo há mais de 12 meses. Devolve quantos saíram."""
    limite = (agora or datetime.now(UTC)) - RETENCAO_INATIVO
    ids = list(
        await session.scalars(
            select(Estabelecimento.id).where(
                Estabelecimento.situacao == Situacao.INATIVO, Estabelecimento.inativo_desde < limite
            )
        )
    )
    await apagar_estabelecimentos(session, ids)
    await session.commit()
    return len(ids)
