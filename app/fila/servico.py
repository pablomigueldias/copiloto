"""A máquina de estados da aprovação — e a captura do dataset, de brinde.

Três regras que moram aqui, e em nenhum outro lugar:

1. **Só `pendente` transiciona.** Decidir de novo é erro (`JaDecidida`), nunca
   sobrescrita: o par de treino não pode mudar de valor depois de contado.
2. **Aprovar com texto diferente é editar.** Quem chama não escolhe o rótulo —
   se `texto_final != texto_gerado`, o status é `editada`. Se dependesse de o
   usuário marcar "eu mexi", o dataset da F9 morreria de omissão.
3. **Rejeitada não vira exemplo de estilo.** Ensinar o few-shot com o texto que
   eu recusei é o jeito mais eficiente de o sistema aprender a escrever mal.

A gravação do par não é responsabilidade do agente que criou a ação. Se fosse,
algum agente esqueceria — e o dataset da F9 depende de **nenhum** esquecer.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select

from app.db.models.acao_pendente import AcaoPendente
from app.db.observability import registrar_evento
from app.db.session import get_session
from app.integrations import telegram
from app.utils.logger import get_logger

logger = get_logger()

Decisao = Literal["aprovar", "editar", "rejeitar"]


class FilaErro(Exception):
    """Problema de uso da fila que o chamador precisa tratar."""


class AcaoNaoEncontrada(FilaErro):
    pass


class JaDecidida(FilaErro):
    """A ação já saiu de `pendente`. Decisão é transição, e acontece uma vez."""


async def criar(
    *,
    agente: str,
    tipo: str,
    titulo: str,
    texto_gerado: str | None = None,
    contexto: str | None = None,
    payload: dict | None = None,
    alvo_ref: str | None = None,
    ai_call_id: UUID | None = None,
) -> AcaoPendente:
    """Enfileira uma ação para eu decidir. O agente para aqui."""
    async with get_session() as session:
        acao = AcaoPendente(
            agente=agente,
            tipo=tipo,
            titulo=titulo.strip(),
            texto_gerado=texto_gerado,
            contexto=contexto,
            payload=payload or {},
            alvo_ref=alvo_ref,
            ai_call_id=ai_call_id,
        )
        session.add(acao)
        await session.commit()
        await session.refresh(acao)

    logger.info(f"Fila: nova ação {acao.agente}/{acao.tipo} — {acao.titulo[:60]!r}")
    await registrar_evento(
        "fila.criada", status="ok", detalhe=f"{acao.agente}/{acao.tipo}", alvo_ref=alvo_ref
    )
    # Desligado sem token no .env, e nunca levanta: o aviso é conveniência.
    await telegram.avisar_acao_pendente(acao)
    return acao


async def obter(acao_id: UUID) -> AcaoPendente:
    async with get_session() as session:
        acao = await session.get(AcaoPendente, acao_id)
    if acao is None:
        raise AcaoNaoEncontrada(f"Ação {acao_id} não existe.")
    return acao


async def listar(
    *,
    status: str | Sequence[str] | None = "pendente",
    agente: str | None = None,
    tipo: str | None = None,
    limite: int = 50,
    offset: int = 0,
) -> tuple[int, list[AcaoPendente]]:
    """A fila. Pendentes primeiro as mais antigas — decidir é FIFO."""
    filtros = []
    if status:
        alvos = [status] if isinstance(status, str) else list(status)
        filtros.append(AcaoPendente.status.in_(alvos))
    if agente:
        filtros.append(AcaoPendente.agente == agente)
    if tipo:
        filtros.append(AcaoPendente.tipo == tipo)

    # Pendente: a mais velha primeiro (é o que está esperando há mais tempo).
    # Decidida: a mais recente primeiro (é o histórico que se olha).
    so_pendentes = status == "pendente"
    ordem = AcaoPendente.criada_em.asc() if so_pendentes else AcaoPendente.criada_em.desc()

    async with get_session() as session:
        total = await session.scalar(select(func.count(AcaoPendente.id)).where(*filtros)) or 0
        itens = (
            await session.scalars(
                select(AcaoPendente).where(*filtros).order_by(ordem).limit(limite).offset(offset)
            )
        ).all()
    return int(total), list(itens)


async def contar_por_status() -> dict[str, int]:
    async with get_session() as session:
        linhas = await session.execute(
            select(AcaoPendente.status, func.count()).group_by(AcaoPendente.status)
        )
    return {s: int(n) for s, n in linhas}


def _resolver_status(decisao: Decisao, acao: AcaoPendente, texto_final: str | None) -> str:
    """O rótulo sai do texto, não da intenção de quem clicou.

    Aprovar mexendo no texto é editar — e é justamente esse caso que produz o
    par de preferência que a F9 precisa.
    """
    if decisao == "rejeitar":
        return "rejeitada"
    mudou = texto_final is not None and texto_final.strip() != (acao.texto_gerado or "").strip()
    return "editada" if mudou else "aprovada"


async def decidir(
    acao_id: UUID,
    *,
    decisao: Decisao,
    texto_final: str | None = None,
    motivo: str | None = None,
) -> AcaoPendente:
    """Aprova, edita ou rejeita — uma vez só, numa transação só."""
    async with get_session() as session:
        acao = await session.get(AcaoPendente, acao_id, with_for_update=True)
        if acao is None:
            raise AcaoNaoEncontrada(f"Ação {acao_id} não existe.")
        if acao.status != "pendente":
            raise JaDecidida(
                f"Ação {acao_id} já está '{acao.status}' desde {acao.decidida_em:%d/%m %H:%M}."
            )

        acao.status = _resolver_status(decisao, acao, texto_final)
        acao.decidida_em = datetime.now(UTC)
        acao.motivo = motivo
        if decisao != "rejeitar":
            # Sempre grava o texto final, mesmo idêntico: é o que eu mandei, e
            # "aprovei sem mexer" também é informação sobre a qualidade.
            acao.texto_final = (
                texto_final.strip() if texto_final is not None else acao.texto_gerado
            )

        await session.commit()
        await session.refresh(acao)

    # Aprovada ou editada vira exemplo de estilo — fora da transação da
    # decisão, porque falhar aqui não pode desfazer o que eu já decidi.
    if acao.status in ("aprovada", "editada"):
        from app.fila import exemplos

        try:
            await exemplos.registrar(acao)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Decisão gravada, exemplo de estilo não: {type(e).__name__}: {e}")

    logger.info(f"Fila: {acao.status} — {acao.titulo[:60]!r}")
    await registrar_evento(
        f"fila.{acao.status}",
        status="ok",
        detalhe=f"{acao.agente}/{acao.tipo}",
        alvo_ref=acao.alvo_ref,
    )
    return acao
