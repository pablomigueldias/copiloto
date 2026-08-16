"""O fluxo da candidatura, de ponta a ponta.

    colar a vaga → extrair requisitos → match → currículo → PDF → fila

Cada etapa é um módulo que funciona sozinho; aqui elas viram um caminho, com o
estado gravado a cada passo. Se a geração falhar na terceira vaga de uma lista
de dez, as duas primeiras continuam analisadas — e a quarta não recomeça do zero.

O que este módulo **não** faz: enviar. A carta e a mensagem ao recrutador viram
ação pendente na fila da F4, e é lá que eu decido. O envio é da F6.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.candidatura import curriculo as gerador
from app.candidatura import extrator, match, pdf, perfil, vagas
from app.db.models.pessoal.vaga import Vaga
from app.db.session import get_session
from app.fila import servico as fila
from app.utils.logger import get_logger

logger = get_logger()


@dataclass(slots=True)
class Analise:
    vaga: Vaga
    requisitos: extrator.Requisitos
    match: match.Match


async def analisar(vaga_id: UUID, *, forcar: bool = False) -> Analise:
    """Extrai requisitos e cruza com o Perfil Mestre.

    Guarda tudo na vaga: reanalisar custa duas inferências, e a segunda vez que
    eu abrir a mesma vaga não deveria pagar de novo.
    """
    vaga = await vagas.obter(vaga_id)
    fatos = await perfil.carregar()

    if vaga.analise_json and not forcar:
        requisitos = extrator.Requisitos(**{
            k: v for k, v in vaga.analise_json.items()
            if k in extrator.Requisitos.__slots__
        })
    else:
        requisitos = await extrator.extrair(vaga.descricao, alvo_ref=f"vaga:{vaga.id}")

    resultado = await match.calcular(requisitos, fatos)

    async with get_session() as session:
        alvo = await session.get(Vaga, vaga_id)
        alvo.analise_json = requisitos.como_json()
        alvo.match_json = resultado.como_json()
        alvo.match_score = resultado.score
        if requisitos.senioridade and not alvo.senioridade:
            alvo.senioridade = requisitos.senioridade[:50]
        if requisitos.modelo and not alvo.modelo:
            alvo.modelo = requisitos.modelo[:30]
        await session.commit()
        await session.refresh(alvo)

    await vagas.registrar_evento(
        vaga_id, "analisada", detalhe=f"score {resultado.score} · {len(resultado.gaps)} gaps"
    )
    return Analise(vaga=alvo, requisitos=requisitos, match=resultado)


@dataclass(slots=True)
class Gerado:
    vaga: Vaga
    curriculo: gerador.Curriculo
    pdf: Path | None = None
    acao_id: UUID | None = None


async def gerar_curriculo(
    vaga_id: UUID, *, com_pdf: bool = True, para_fila: bool = True
) -> Gerado:
    """Currículo adaptado, PDF ATS e (opcionalmente) a ação na fila."""
    vaga = await vagas.obter(vaga_id)
    fatos = await perfil.carregar()

    if not vaga.analise_json:
        analise = await analisar(vaga_id)
        vaga, requisitos, resultado = analise.vaga, analise.requisitos, analise.match
    else:
        requisitos = extrator.Requisitos(**{
            k: v for k, v in vaga.analise_json.items()
            if k in extrator.Requisitos.__slots__
        })
        resultado = match.Match(
            score=vaga.match_score or 0,
            gaps=(vaga.match_json or {}).get("gaps") or [],
            destaques=(vaga.match_json or {}).get("destaques") or [],
        )

    curriculo = await gerador.gerar(
        fatos=fatos,
        requisitos=requisitos,
        match=resultado,
        titulo_vaga=vaga.titulo,
        descricao_vaga=vaga.descricao,
        empresa_vaga=vaga.empresa,
    )

    saida = Gerado(vaga=vaga, curriculo=curriculo)
    if com_pdf:
        saida.pdf = pdf.gerar_pdf(curriculo, fatos, empresa=vaga.empresa)

    async with get_session() as session:
        alvo = await session.get(Vaga, vaga_id)
        alvo.curriculo_json = curriculo.como_json()
        from datetime import UTC, datetime

        alvo.curriculo_gerado_em = datetime.now(UTC)
        await session.commit()

    if para_fila:
        acao = await fila.criar(
            agente="candidatura",
            tipo="curriculo",
            titulo=f"Currículo para {vaga.titulo}"
            + (f" — {vaga.empresa}" if vaga.empresa else ""),
            texto_gerado=gerador.como_texto(curriculo, fatos),
            contexto=(
                f"vaga {vaga.titulo}"
                + (f" na {vaga.empresa}" if vaga.empresa else "")
                + f"; requisitos: {', '.join(requisitos.obrigatorios[:6])}"
            ),
            payload={
                "vaga_id": str(vaga.id),
                "pdf": str(saida.pdf) if saida.pdf else None,
                "match_score": resultado.score,
                "gaps": resultado.gaps,
                "rejeitados": curriculo.rejeitados,
                "avisos": curriculo.avisos,
            },
            alvo_ref=f"vaga:{vaga.id}",
        )
        saida.acao_id = acao.id

    await vagas.registrar_evento(
        vaga_id,
        "gerada",
        detalhe=f"{len(curriculo.rejeitados)} rejeitado(s) pela anti-alucinação",
    )
    logger.info(f"Currículo gerado para {vaga.titulo!r} · PDF: {saida.pdf}")
    return saida
