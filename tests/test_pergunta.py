"""Resposta ancorada — o teste é a regra: sem trecho, sem resposta.

Sem Ollama. O provider falso devolve o texto que o teste mandar, e registra o
prompt que recebeu — que é o que importa verificar: os trechos entraram
numerados, com fonte, e a pergunta chegou até o modelo.
"""
from __future__ import annotations

from zlib import crc32

import pytest
from sqlalchemy import select

from app.conhecimento.busca import Trecho
from app.conhecimento.fontes import Documento
from app.conhecimento.indexador import indexar
from app.conhecimento.pergunta import (
    DISTANCIA_MAXIMA,
    montar_prompt,
    perguntar,
)
from app.db.models.pipeline_event import PipelineEvent
from app.db.session import get_session
from app.llm import gateway
from app.llm.tipos import LLMIndisponivel, RespostaCrua

DIM = 1024

BANCO = (
    "# Normalização\n\nNormalizar é projetar as tabelas de modo que nenhuma anomalia "
    "de inserção, remoção ou alteração apareça. A terceira forma normal elimina "
    "dependência transitiva entre atributos não-chave, e é onde a maioria dos "
    "esquemas para de doer na prática do dia a dia."
)
FILA = (
    "# Fila\n\nO worker roda em arq sobre Redis. A tarefa entra na fila, o processo "
    "de fundo consome depois, e a API não fica presa esperando GPU para devolver "
    "resposta ao usuário que está do outro lado da tela."
)



# `hash()` de str é salgado por processo (PYTHONHASHSEED): o mesmo texto dá
# vetores diferentes a cada execução, e o ranking vira sorteio. Custou um teste
# que falhava em ~5% das rodadas — e, pior, uma vez em que eu commitei no
# vermelho achando que era instabilidade sem causa. `crc32` é estável.
def _estavel(texto: str) -> int:
    return crc32(texto.encode())

class LLMFalso:
    """Devolve `resposta` e guarda o prompt que recebeu."""

    nome = "falso"

    def __init__(self, resposta: str = "A normalização elimina anomalias [1].") -> None:
        self.resposta = resposta
        self.prompts: list[str] = []
        self.distancias: dict[str, float] = {}

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        return RespostaCrua(
            texto=self.resposta, modelo=modelo, tokens_input=100, tokens_output=20
        )

    async def embedar(self, textos, *, modelo):
        # Vetor por bag-of-words: perguntas que compartilham palavras com um
        # chunk ficam perto dele, e as que não compartilham ficam longe — que é
        # exatamente o que o piso precisa distinguir.
        return [self._vetor(t) for t in textos]

    @staticmethod
    def _vetor(texto: str) -> list[float]:
        v = [0.0] * DIM
        for palavra in texto.lower().split():
            v[_estavel(palavra) % DIM] += 1.0
        norma = sum(x * x for x in v) ** 0.5
        return [x / norma for x in v] if norma else [1.0] + [0.0] * (DIM - 1)


class LLMForaDoAr(LLMFalso):
    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise LLMIndisponivel("Ollama não respondeu")


@pytest.fixture
async def indexado():
    p = LLMFalso()
    gateway.usar_provider(p)
    await indexar(
        [
            Documento(fonte_tipo="nota", fonte_ref="/notas/banco.md", titulo="Banco",
                      conteudo=BANCO, metadados={"tags": ["bd"]}),
            Documento(fonte_tipo="nota", fonte_ref="/notas/fila.md", titulo="Fila",
                      conteudo=FILA),
        ],
        fonte_tipo="nota",
    )
    yield p
    gateway.usar_provider(gateway.OllamaProvider())


def usar(p) -> None:
    gateway.usar_provider(p)


def trecho(n: int, conteudo: str = "conteúdo", **kw) -> Trecho:
    import uuid

    base = dict(
        id=uuid.UUID(int=n),
        fonte_tipo="nota",
        fonte_ref=f"/notas/{n}.md",
        ordem=0,
        titulo=f"Nota {n}",
        conteudo=conteudo,
        posicao_vetorial=n,
        distancia=0.3,
    )
    return Trecho(**{**base, **kw})


# ── Prompt ────────────────────────────────────────────────────────


def test_prompt_numera_os_trechos_e_identifica_a_fonte():
    p = montar_prompt("o que é normalização?", [trecho(1, "normalizar é..."), trecho(2)])

    assert "[1] Nota 1 — /notas/1.md" in p
    assert "[2] Nota 2 — /notas/2.md" in p
    assert "normalizar é..." in p


def test_prompt_termina_com_a_pergunta():
    p = montar_prompt("o que é normalização?", [trecho(1)])
    # Modelo pequeno presta mais atenção no fim do prompt.
    assert p.rstrip().endswith("Resposta:")
    assert p.index("o que é normalização?") > p.index("[1]")


def test_prompt_manda_admitir_quando_nao_sabe():
    p = montar_prompt("qualquer coisa", [trecho(1)])
    assert "NAO_INDEXADO" in p
    assert "APENAS os trechos" in p


def test_prompt_traz_a_pagina_do_pdf_quando_existe():
    t = trecho(1, titulo="edital > p. 47", metadados={"pagina": 47})
    assert "p. 47" in montar_prompt("q", [t])


# ── Piso: o que NÃO chega ao modelo ───────────────────────────────


async def test_pergunta_fora_do_indice_nao_gasta_gpu(indexado):
    r = await perguntar("qual a capital da Mongólia e como fazer bolo de cenoura")

    assert r.respondeu is False and r.motivo == "sem_indice"
    assert r.texto == "Não tenho isso indexado."
    # O ponto da defesa mais barata: nenhum token gerado.
    assert indexado.prompts == []
    assert r.distancia and r.distancia > DISTANCIA_MAXIMA


async def test_pergunta_dentro_do_indice_chega_ao_modelo(indexado):
    r = await perguntar("o que é normalização e anomalia de inserção?")

    assert r.respondeu is True
    assert len(indexado.prompts) == 1
    assert "Normalizar é projetar" in indexado.prompts[0]


async def test_termo_exato_salva_a_pergunta_do_piso(indexado):
    """Acerto lexical vale salvo-conduto mesmo com embedding discordando."""
    r = await perguntar("arq")
    assert r.respondeu is True


async def test_indice_vazio_responde_que_nao_tem(indexado):
    r = await perguntar("qualquer pergunta", fonte_tipo="pdf")
    assert r.respondeu is False and r.motivo == "sem_indice"


async def test_pergunta_vazia_nao_busca(indexado):
    r = await perguntar("   ")
    assert r.respondeu is False and indexado.prompts == []


# ── Citação: o que volta do modelo ────────────────────────────────


async def test_resposta_traz_as_fontes_citadas(indexado):
    usar(LLMFalso("A normalização elimina anomalias de inserção [1]."))
    r = await perguntar("o que é normalização e anomalia de inserção?")

    assert r.respondeu is True
    assert [f.fonte_ref for f in r.fontes] == ["/notas/banco.md"]
    assert r.modelo and r.latencia_ms is not None and r.tokens == 120


async def test_resposta_sem_citacao_nao_conta_como_resposta(indexado):
    usar(LLMFalso("Normalização é dividir tabelas para evitar repetição."))
    r = await perguntar("o que é normalização e anomalia de inserção?")

    # Sem [n] não há como conferir de onde saiu — e "ancorado" viraria promessa.
    assert r.respondeu is False and r.motivo == "sem_citacao"
    assert r.texto  # o texto volta, para inspeção


async def test_citacao_inventada_e_ignorada_mas_nao_derruba(indexado):
    usar(LLMFalso("Vale o que diz [1], e também [9]."))
    r = await perguntar("o que é normalização e anomalia de inserção?")

    assert r.respondeu is True
    assert len(r.fontes) == 1 and r.fontes[0].fonte_ref == "/notas/banco.md"


async def test_modelo_pode_recusar_na_zona_cinzenta(indexado):
    usar(LLMFalso("NAO_INDEXADO"))
    r = await perguntar("o que é normalização e anomalia de inserção?")

    assert r.respondeu is False and r.motivo == "recusou"
    assert r.texto == "Não tenho isso indexado."


async def test_citacao_repetida_nao_duplica_a_fonte(indexado):
    usar(LLMFalso("Diz [1]. E ainda [1]. Sempre [1]."))
    r = await perguntar("o que é normalização e anomalia de inserção?")
    assert len(r.fontes) == 1


async def test_llm_fora_do_ar_devolve_motivo_e_nao_explode(indexado):
    usar(LLMForaDoAr())
    r = await perguntar("o que é normalização e anomalia de inserção?")

    assert r.respondeu is False and r.motivo == "erro_llm"
    assert r.trechos, "os trechos encontrados voltam mesmo sem resposta"


# ── Observabilidade ───────────────────────────────────────────────


async def test_toda_pergunta_deixa_rastro(indexado):
    await perguntar("o que é normalização e anomalia de inserção?")
    await perguntar("qual a capital da Mongólia e como fazer bolo de cenoura")

    async with get_session() as s:
        eventos = (
            await s.scalars(
                select(PipelineEvent).where(PipelineEvent.evento == "conhecimento.pergunta")
            )
        ).all()

    assert {e.status for e in eventos} == {"ok", "vazio"}
