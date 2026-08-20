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


class SemCurriculo(Exception):
    """Pediram o PDF de uma vaga que ainda não passou pelo gerador."""


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


async def texto_do_curriculo(vaga_id: UUID) -> str:
    """O currículo gerado, em texto puro — o que a tela abre para eu editar.

    Vem do `curriculo_json`, e não do PDF ou do texto guardado na ação da fila:
    é a mesma fonte que o `curriculo.pdf` reimprime, então o que eu leio no
    editor é literalmente o que sai no papel. Qualquer outra fonte poderia estar
    um passo atrás.
    """
    vaga = await vagas.obter(vaga_id)
    if not vaga.curriculo_json:
        raise SemCurriculo(f"A vaga {vaga.titulo!r} ainda não tem currículo gerado.")
    fatos = await perfil.carregar()
    return gerador.como_texto(gerador.Curriculo(**vaga.curriculo_json), fatos)


async def aplicar_texto_aprovado(
    vaga_id: UUID, texto: str, *, origem: str = "fila"
) -> Path | None:
    """O currículo que eu editei vira o currículo da vaga.

    Dois caminhos chegam aqui e é de propósito que seja o mesmo código: a
    aprovação com edição na fila, e o editor da gaveta da vaga. Duas rotinas de
    "aplicar texto editado" divergiriam no primeiro formato novo, e aí o PDF
    dependeria de por qual tela eu passei.

    Sem isto, aprovar com edição gravava `texto_final` na ação e mais nada: o
    `curriculo_json` continuava com a saída do modelo, e `curriculo.pdf` — que
    reimprime a partir dele — devolvia o texto que eu tinha acabado de corrigir.
    A correção existia no banco e não chegava ao documento que eu ia enviar.

    Devolve o PDF reimpresso, ou `None` quando nada mudou.
    """
    vaga = await vagas.obter(vaga_id)
    if not vaga.curriculo_json or not (texto or "").strip():
        return None

    fatos = await perfil.carregar()
    base = gerador.Curriculo(**vaga.curriculo_json)
    editado = gerador.de_texto(texto, base)

    if editado.como_json() == base.como_json():
        return None

    async with get_session() as session:
        alvo = await session.get(Vaga, vaga_id)
        alvo.curriculo_json = editado.como_json()
        await session.commit()

    caminho = pdf.gerar_pdf(editado, fatos, empresa=vaga.empresa)
    await vagas.registrar_evento(
        vaga_id, "editada", detalhe=f"currículo corrigido ({origem})"
    )
    logger.info(f"Currículo da vaga {str(vaga_id)[:8]} atualizado com o texto aprovado")
    return caminho


async def pdf_da_vaga(vaga_id: UUID) -> tuple[Path, str]:
    """O PDF do currículo já gerado — devolve o caminho e o nome para baixar.

    Renderiza a partir do `curriculo_json` guardado, em vez de confiar no
    arquivo em disco: o caminho salvo no payload pode ter sido apagado, movido
    ou nem existir se a geração rodou com `com_pdf=False`. Reimprimir custa
    milissegundos e nenhuma inferência — o texto já está decidido.
    """
    vaga = await vagas.obter(vaga_id)
    if not vaga.curriculo_json:
        raise SemCurriculo(
            f"A vaga {vaga.titulo!r} ainda não tem currículo gerado."
        )

    fatos = await perfil.carregar()
    curriculo = gerador.Curriculo(**vaga.curriculo_json)
    caminho = pdf.gerar_pdf(curriculo, fatos, empresa=vaga.empresa)
    return caminho, pdf.nome_do_arquivo(fatos.perfil.nome, curriculo.titulo, vaga.empresa)
