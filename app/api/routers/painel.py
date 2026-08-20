"""Rota do painel — `/api/painel`.

Um endpoint que devolve tudo que a tela pinta. Seis `fetch` em paralelo para
montar uma página seriam seis conexões, seis autenticações e seis chances de a
tela mostrar números de momentos diferentes — "3 pendentes" ao lado de uma fila
com 4 cards.

Cada bloco degrada sozinho: se o Ollama estiver fora, `saude.ollama` vem `false`
e o resto da tela continua funcionando. Painel que não abre porque uma parte do
sistema caiu é painel inútil justamente na hora em que ele seria útil.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.api.dependencies.auth import usuario_atual
from app.candidatura import metricas as painel_candidatura
from app.conhecimento.indexador import inventario, totais_por_tipo
from app.db.models.acao_pendente import AcaoPendente
from app.db.models.ai_call import AiCall
from app.db.models.auth.usuario import Usuario
from app.db.models.pipeline_event import PipelineEvent
from app.db.session import get_session
from app.fila import servico as fila
from app.llm.providers.ollama import OllamaProvider
from app.utils.logger import get_logger
from app.worker import vida

logger = get_logger()

UsuarioLogado = Annotated[Usuario, Depends(usuario_atual)]

router = APIRouter(prefix="/api/painel", tags=["painel"])


# O health check do Ollama não pode herdar o timeout de inferência (180 s): ele
# roda a cada refresco do painel, e um Ollama travado (OOM de VRAM, porta num
# firewall que faz DROP) penduraria `/api/painel` por três minutos a cada quinze
# segundos, empilhando conexões. Um servidor que não responde `/api/version` em
# 1,5 s não está saudável para a tela — que é a pergunta sendo feita.
TIMEOUT_SAUDE_S = 1.5
# E não precisa ser perguntado a cada refresco: memoizar por 10 s tira uma
# chamada HTTP de cada ciclo sem atrasar a notícia de que o Ollama caiu.
CACHE_SAUDE_S = 10.0

_ollama_visto: tuple[float, bool] | None = None


async def _ollama_vivo() -> bool:
    global _ollama_visto
    agora = monotonic()
    if _ollama_visto and agora - _ollama_visto[0] < CACHE_SAUDE_S:
        return _ollama_visto[1]

    vivo = await OllamaProvider(timeout_s=TIMEOUT_SAUDE_S).disponivel()
    _ollama_visto = (agora, vivo)
    return vivo


async def _saude() -> dict:
    """Está tudo de pé? A pergunta que se faz antes de olhar qualquer número."""
    ollama = await _ollama_vivo()

    async with get_session() as session:
        ultima_varredura = await session.scalar(
            select(func.max(PipelineEvent.created_at)).where(
                PipelineEvent.evento == "worker.reindexar"
            )
        )
        # O worker grava evento só quando algo muda; sem mudança recente, a
        # prova de vida é a última chamada de embedding que ele fez.
        ultima_atividade = await session.scalar(select(func.max(AiCall.created_at)))

    # O worker está vivo? Era a pergunta que ninguém estava fazendo — e por isso
    # 42 PDFs ficaram 14 h fora do índice sem nada na tela indicar. Ver
    # `app/worker/vida.py` para o porquê de o batimento morar no Redis.
    worker_visto_em = await vida.visto_em()

    return {
        "ollama": ollama,
        "worker": worker_visto_em is not None,
        "worker_visto_em": worker_visto_em,
        "ultima_varredura": ultima_varredura.isoformat() if ultima_varredura else None,
        "ultima_atividade": ultima_atividade.isoformat() if ultima_atividade else None,
    }


async def _conhecimento() -> dict:
    total_fontes, fontes = await inventario(limite=6)
    return {
        "chunks_por_tipo": await totais_por_tipo(),
        "fontes": total_fontes,
        "recentes": [
            {
                "fonte_tipo": f.fonte_tipo,
                "fonte_ref": f.fonte_ref,
                "titulo": f.titulo,
                "chunks": f.chunks,
                "partes": f.partes,
                "atualizado_em": f.atualizado_em.isoformat(),
            }
            for f in fontes
        ],
    }


async def _fila() -> dict:
    total, pendentes = await fila.listar(status="pendente", limite=5)
    return {
        "por_status": await fila.contar_por_status(),
        "pendentes": total,
        "itens": [
            {
                "id": str(a.id),
                "agente": a.agente,
                "tipo": a.tipo,
                "titulo": a.titulo,
                "contexto": a.contexto,
                "texto_gerado": a.texto_gerado,
                "criada_em": a.criada_em.isoformat(),
                "payload": a.payload or {},
            }
            for a in pendentes
        ],
    }


async def _modelo() -> dict:
    """Uso do LLM nas últimas 24 h — e as últimas chamadas, com o desfecho."""
    desde = datetime.now(UTC) - timedelta(hours=24)

    async with get_session() as session:
        agregado = (
            await session.execute(
                select(
                    func.count(AiCall.id),
                    func.sum(func.coalesce(AiCall.tokens_input, 0) + func.coalesce(AiCall.tokens_output, 0)),
                    func.avg(AiCall.latencia_ms),
                    func.count(AiCall.id).filter(AiCall.sucesso.is_(False)),
                ).where(AiCall.created_at >= desde)
            )
        ).one()
        ultimas = (
            await session.scalars(
                select(AiCall).order_by(AiCall.created_at.desc()).limit(6)
            )
        ).all()

    chamadas, tokens, latencia, falhas = agregado
    return {
        "chamadas_24h": int(chamadas or 0),
        "tokens_24h": int(tokens or 0),
        "latencia_media_ms": int(latencia) if latencia else None,
        "falhas_24h": int(falhas or 0),
        "ultimas": [
            {
                "agente": c.agente,
                "tarefa": c.tarefa,
                "modelo": c.modelo,
                "latencia_ms": c.latencia_ms,
                "sucesso": c.sucesso,
                "created_at": c.created_at.isoformat(),
            }
            for c in ultimas
        ],
    }


async def _candidaturas() -> dict:
    m = await painel_candidatura.calcular()
    return {
        "funil": m.funil,
        "por_status": m.por_status,
        "taxa_resposta": m.taxa_resposta,
        "dias_ate_resposta": m.dias_ate_resposta,
        "followup_vencido": m.followup_vencido,
        "score_medio": m.score_medio,
        "paradas": m.paradas[:5],
        "gaps_frequentes": m.gaps_frequentes[:8],
    }


BLOCOS: tuple[str, ...] = ("saude", "conhecimento", "fila", "candidaturas", "modelo")


def _bloco(nome: str):
    """A função do bloco, resolvida **na hora da chamada**.

    Guardar a função direto num dicionário congelaria a referência no import:
    trocar `_conhecimento` por um duplo (é o que o teste do bloco quebrado faz)
    não teria efeito nenhum, e o painel deixaria de ser testável justamente na
    parte que existe para mostrar defeito.
    """
    return globals()[f"_{nome}"]


@router.get("", summary="Tudo que a tela mostra, num request")
async def get_painel(usuario: UsuarioLogado, blocos: str | None = None) -> dict:
    """Os blocos do painel. `?blocos=saude,fila` traz só os pedidos.

    O filtro existe desde que as candidaturas ganharam página própria: cada
    bloco custa consulta ao banco, e `/candidaturas/` não tem onde pintar fila,
    conhecimento e modelo. Buscar os cinco a cada 15 s para jogar três fora é
    trabalho que ninguém vê.

    Sem o parâmetro vêm todos — o contrato antigo continua valendo para quem
    chama a API de fora da tela.
    """
    pedidos = [n.strip() for n in (blocos or "").split(",") if n.strip()]
    desconhecidos = [n for n in pedidos if n not in BLOCOS]
    if desconhecidos:
        raise HTTPException(
            status_code=422,
            detail=f"Bloco desconhecido: {', '.join(desconhecidos)}. "
            f"Conhecidos: {', '.join(BLOCOS)}.",
        )
    escolhidos = pedidos or list(BLOCOS)

    saida: dict = {"usuario": {"nome": usuario.nome, "email": usuario.email}}

    # Um bloco quebrado não pode derrubar a tela inteira: o painel é o que se
    # olha justamente quando alguma coisa está errada.
    for nome in escolhidos:
        try:
            saida[nome] = await _bloco(nome)()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Painel: bloco '{nome}' falhou ({type(e).__name__}: {e})")
            saida[nome] = {"erro": f"{type(e).__name__}: {e}"}

    async with get_session() as session:
        saida["acoes_decididas_hoje"] = int(
            await session.scalar(
                select(func.count(AcaoPendente.id)).where(
                    AcaoPendente.decidida_em >= datetime.now(UTC) - timedelta(days=1)
                )
            )
            or 0
        )
    return saida
