"""Documento → chunks → embeddings → Postgres, sem refazer o que não mudou.

O que separa um índice de um script de importação é esta linha:

    se o hash do documento bate com o que está no banco, ele nem é lido.

Reindexar tudo funciona com 300 chunks e morre com 30.000 — e a diferença
aparece justamente quando o sistema começou a ser útil.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select

from app.config import settings
from app.conhecimento.chunking import chunkar
from app.conhecimento.fontes import Documento
from app.db.models.conhecimento import ConhecimentoChunk
from app.db.observability import registrar_evento
from app.db.session import get_session
from app.llm import gateway
from app.utils.logger import get_logger

logger = get_logger()


@dataclass(slots=True)
class Resultado:
    documentos: int = 0
    inalterados: int = 0
    indexados: int = 0
    chunks: int = 0
    removidos: int = 0
    erros: int = 0

    def __str__(self) -> str:
        return (
            f"{self.documentos} documentos · {self.indexados} indexados "
            f"({self.chunks} chunks) · {self.inalterados} inalterados · "
            f"{self.removidos} removidos · {self.erros} erros"
        )


async def _hashes_no_banco(fonte_tipo: str) -> dict[str, str]:
    """`fonte_ref → hash` do que já está indexado, para comparar sem ler disco."""
    async with get_session() as session:
        linhas = await session.execute(
            select(ConhecimentoChunk.fonte_ref, ConhecimentoChunk.fonte_hash)
            .where(ConhecimentoChunk.fonte_tipo == fonte_tipo)
            .distinct()
        )
    return {ref: h for ref, h in linhas}


async def _substituir(doc: Documento, chunks: list, vetores: list[list[float]]) -> None:
    """Troca os chunks de um documento numa transação só.

    DELETE + INSERT em vez de upsert linha a linha: o número de chunks muda
    quando o texto muda, então casar por `ordem` deixaria sobra do texto velho.
    """
    async with get_session() as session:
        await session.execute(
            delete(ConhecimentoChunk).where(
                ConhecimentoChunk.fonte_tipo == doc.fonte_tipo,
                ConhecimentoChunk.fonte_ref == doc.fonte_ref,
            )
        )
        for chunk, vetor in zip(chunks, vetores, strict=True):
            session.add(
                ConhecimentoChunk(
                    fonte_tipo=doc.fonte_tipo,
                    fonte_ref=doc.fonte_ref,
                    fonte_hash=doc.hash,
                    ordem=chunk.ordem,
                    titulo=chunk.titulo,
                    conteudo=chunk.conteudo,
                    embedding=vetor,
                    metadados=chunk.metadados or None,
                )
            )
        await session.commit()


async def indexar(
    documentos: Iterable[Documento],
    *,
    fonte_tipo: str,
    forcar: bool = False,
    remover_ausentes: bool = True,
) -> Resultado:
    """Indexa os documentos de uma fonte e apaga o que sumiu dela."""
    res = Resultado()
    conhecidos = {} if forcar else await _hashes_no_banco(fonte_tipo)
    vistos: set[str] = set()
    lote = max(1, settings.conhecimento_lote_embedding)

    for doc in documentos:
        res.documentos += 1
        vistos.add(doc.fonte_ref)

        if conhecidos.get(doc.fonte_ref) == doc.hash:
            res.inalterados += 1
            continue

        chunks = chunkar(doc.conteudo, titulo_base=doc.titulo, metadados=doc.metadados)
        if not chunks:
            continue

        try:
            vetores: list[list[float]] = []
            for i in range(0, len(chunks), lote):
                fatia = chunks[i : i + lote]
                vetores.extend(await gateway.embedar([c.conteudo for c in fatia]))
            await _substituir(doc, chunks, vetores)
        except Exception as e:  # noqa: BLE001 — um documento ruim não para a varredura
            res.erros += 1
            logger.warning(f"Falhou ao indexar {doc.fonte_ref}: {type(e).__name__}: {e}")
            continue

        res.indexados += 1
        res.chunks += len(chunks)
        logger.info(f"{doc.fonte_ref} → {len(chunks)} chunks")

    if remover_ausentes:
        res.removidos = await _remover_ausentes(fonte_tipo, vistos)

    await registrar_evento(
        "conhecimento.indexar",
        status="erro" if res.erros else "ok",
        detalhe=str(res),
        alvo_ref=fonte_tipo,
    )
    return res


async def _remover_ausentes(fonte_tipo: str, vistos: set[str]) -> int:
    """Arquivo apagado do disco tem que sumir do índice.

    Sem isso o sistema responde citando um arquivo que não existe mais — pior
    que não responder, porque parece certo.
    """
    async with get_session() as session:
        refs = set(
            (
                await session.scalars(
                    select(ConhecimentoChunk.fonte_ref)
                    .where(ConhecimentoChunk.fonte_tipo == fonte_tipo)
                    .distinct()
                )
            ).all()
        )
        sumiram = refs - vistos
        if not sumiram:
            return 0
        await session.execute(
            delete(ConhecimentoChunk).where(
                ConhecimentoChunk.fonte_tipo == fonte_tipo,
                ConhecimentoChunk.fonte_ref.in_(sumiram),
            )
        )
        await session.commit()
    logger.info(f"{len(sumiram)} fonte(s) sumiram do disco e saíram do índice")
    return len(sumiram)


@dataclass(slots=True)
class FonteIndexada:
    fonte_tipo: str
    fonte_ref: str
    titulo: str | None
    chunks: int
    partes: int
    atualizado_em: datetime


# `#` separa o documento da sua parte: `livro.pdf#p47`, `perfil:<id>#projetos`.
# O indexador trabalha na parte (reindexa e apaga por ela); o inventário mostra
# o documento — senão um PDF de 800 páginas vira 800 linhas de listagem.
_DOCUMENTO = func.split_part(ConhecimentoChunk.fonte_ref, "#", 1)


async def inventario(
    *, fonte_tipo: str | None = None, limite: int = 200, offset: int = 0
) -> tuple[int, list[FonteIndexada]]:
    """O que está indexado: uma linha por documento, com chunks e de quando.

    É a tela "Conhecimento" do plano (§12) em forma de dado: sem isto, a única
    maneira de saber o que a IA sabe é perguntar e torcer.
    """
    agrupado = (
        select(
            ConhecimentoChunk.fonte_tipo,
            _DOCUMENTO.label("fonte_ref"),
            # Um dos títulos do grupo — todos compartilham a mesma raiz de
            # trilha, então qualquer um identifica a fonte.
            func.min(ConhecimentoChunk.titulo).label("titulo"),
            func.count().label("chunks"),
            # Páginas do PDF, blocos do perfil: 1 quando a fonte é um arquivo só.
            func.count(func.distinct(ConhecimentoChunk.fonte_ref)).label("partes"),
            func.max(ConhecimentoChunk.atualizado_em).label("atualizado_em"),
        )
        .group_by(ConhecimentoChunk.fonte_tipo, _DOCUMENTO)
        .order_by(func.max(ConhecimentoChunk.atualizado_em).desc())
    )
    if fonte_tipo:
        agrupado = agrupado.where(ConhecimentoChunk.fonte_tipo == fonte_tipo)

    async with get_session() as session:
        total = await session.scalar(
            select(func.count()).select_from(agrupado.order_by(None).subquery())
        )
        linhas = (await session.execute(agrupado.limit(limite).offset(offset))).all()

    return int(total or 0), [FonteIndexada(*linha) for linha in linhas]


async def totais_por_tipo() -> dict[str, int]:
    async with get_session() as session:
        linhas = await session.execute(
            select(ConhecimentoChunk.fonte_tipo, func.count()).group_by(
                ConhecimentoChunk.fonte_tipo
            )
        )
    return {tipo: int(n) for tipo, n in linhas}


async def apagar_fonte(fonte_tipo: str, fonte_ref: str) -> int:
    """Tira uma fonte do índice — o documento inteiro, não só a parte.

    Apagar `livro.pdf` tem que levar as 200 páginas junto: quem pede a remoção
    pensa no arquivo, e deixar 199 páginas órfãs seria pior que não apagar.
    """
    async with get_session() as session:
        r = await session.execute(
            delete(ConhecimentoChunk).where(
                ConhecimentoChunk.fonte_tipo == fonte_tipo,
                _DOCUMENTO == fonte_ref.split("#")[0],
            )
        )
        await session.commit()
    return r.rowcount or 0
