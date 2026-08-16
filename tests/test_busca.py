"""Busca híbrida — o teste é a tese: uma metade acha o que a outra erra.

Sem Ollama. Dois embedders falsos e determinísticos:

- `EmbedderCego` devolve o mesmo vetor para tudo. A metade vetorial vira ruído,
  então o que sobreviver veio do full-text.
- `EmbedderTrigrama` aproxima palavras por trigrama de caractere ("vetores" e
  "vetorial" ficam perto). Serve para o caso oposto: achar sem casar palavra,
  onde o stemmer do Postgres não liga uma coisa à outra.
"""
from __future__ import annotations

import pytest

from app.conhecimento.busca import K_RRF, Trecho, _fundir, buscar
from app.conhecimento.fontes import Documento
from app.conhecimento.indexador import indexar
from app.db.models.conhecimento import ConhecimentoChunk
from app.llm import gateway

DIM = 1024


class EmbedderCego:
    nome = "cego"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("busca não gera texto")

    async def embedar(self, textos, *, modelo):
        return [[0.1] * DIM for _ in textos]


class EmbedderTrigrama(EmbedderCego):
    nome = "trigrama"

    async def embedar(self, textos, *, modelo):
        return [self._vetor(t) for t in textos]

    @staticmethod
    def _vetor(texto: str) -> list[float]:
        v = [0.0] * DIM
        t = texto.lower()
        for i in range(len(t) - 2):
            v[hash(t[i : i + 3]) % DIM] += 1.0
        norma = sum(x * x for x in v) ** 0.5
        return [x / norma for x in v] if norma else [1.0] + [0.0] * (DIM - 1)


class EmbedderQuebrado(EmbedderCego):
    nome = "quebrado"

    async def embedar(self, textos, *, modelo):
        raise RuntimeError("Ollama fora do ar")


@pytest.fixture
def cego():
    gateway.usar_provider(EmbedderCego())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


def usar(provider) -> None:
    gateway.usar_provider(provider)


def _encher(frase: str) -> str:
    """Texto acima do mínimo do chunker, e diferente em cada documento.

    Se as três notas compartilhassem o mesmo enchimento, os três vetores
    ficariam quase iguais e a metade vetorial não teria o que ordenar — o teste
    passaria ou falharia por acaso.
    """
    return " ".join([frase] * 5)


DOCS = [
    Documento(
        fonte_tipo="nota",
        fonte_ref="/notas/banco.md",
        titulo="Banco",
        conteudo="# Banco\n\nO índice usa pgvector com HNSW. "
        + _encher("Cada trecho guarda um vetorial de mil dimensões no Postgres."),
        metadados={"tags": ["infra", "postgres"]},
    ),
    Documento(
        fonte_tipo="nota",
        fonte_ref="/notas/fila.md",
        titulo="Fila",
        conteudo="# Fila\n\nO worker roda em arq sobre Redis. "
        + _encher("A tarefa entra na fila e o processo de fundo consome depois."),
        metadados={"tags": ["infra"]},
    ),
    Documento(
        fonte_tipo="repo",
        fonte_ref="/repo/README.md",
        titulo="Leia-me",
        conteudo="# Leia-me\n\nInstalação e primeiros passos do projeto. "
        + _encher("Suba o compose, aplique a migration e rode a suíte de teste."),
        metadados={"tags": ["doc"]},
    ),
]


@pytest.fixture
async def indexado(cego):
    """As três notas no banco, com vetor inútil de propósito."""
    for tipo in ("nota", "repo"):
        await indexar([d for d in DOCS if d.fonte_tipo == tipo], fonte_tipo=tipo)


# ── Fusão (lógica pura) ───────────────────────────────────────────


def _chunk(ref: str, id_: int) -> ConhecimentoChunk:
    import uuid

    c = ConhecimentoChunk(
        fonte_tipo="nota", fonte_ref=ref, fonte_hash="x", ordem=0, conteudo=ref, titulo=ref
    )
    c.id = uuid.UUID(int=id_)
    return c


def test_rrf_prefere_quem_aparece_nas_duas_listas():
    primeiro_so_no_vetor = _chunk("/so-vetor.md", 1)
    nas_duas = _chunk("/nas-duas.md", 2)

    saida = _fundir([primeiro_so_no_vetor, nas_duas], [nas_duas])

    # 1/(60+2) + 1/(60+1) bate 1/(60+1): estar nas duas listas vale mais que ser
    # o primeiro de uma só. É o motivo de existir a busca híbrida.
    assert saida[0].fonte_ref == "/nas-duas.md"
    assert saida[0].origem == "ambas"
    assert saida[1].origem == "vetorial"


def test_score_do_rrf_e_soma_de_um_sobre_k_mais_posicao():
    c = _chunk("/a.md", 1)
    (t,) = _fundir([c], [c])
    assert t.score == pytest.approx(2 / (K_RRF + 1))
    assert t.posicao_vetorial == 1 and t.posicao_lexical == 1


def test_trecho_sabe_de_onde_veio():
    t = Trecho(
        id=_chunk("/a.md", 1).id,
        fonte_tipo="nota",
        fonte_ref="/a.md",
        ordem=0,
        titulo=None,
        conteudo="x",
        posicao_lexical=3,
    )
    assert t.origem == "lexical"


# ── Busca ─────────────────────────────────────────────────────────


async def test_consulta_vazia_nao_toca_no_banco(indexado):
    assert await buscar("   ") == []


async def test_lexical_acha_o_termo_raro_que_o_vetor_erra(indexado):
    # Todos os vetores são idênticos: se vier o trecho certo, veio do full-text.
    trechos = await buscar("pgvector")
    assert trechos[0].fonte_ref == "/notas/banco.md"
    assert trechos[0].posicao_lexical == 1


async def test_nome_de_biblioteca_curto_tambem_e_encontrado(indexado):
    trechos = await buscar("arq redis")
    assert trechos[0].fonte_ref == "/notas/fila.md"


async def test_vetorial_acha_sem_casar_palavra(indexado):
    """"vetores" não casa com "pgvector" no stemmer, mas casa por trigrama."""
    usar(EmbedderTrigrama())
    # Reindexa com vetores que significam algo.
    for tipo in ("nota", "repo"):
        await indexar(
            [d for d in DOCS if d.fonte_tipo == tipo], fonte_tipo=tipo, forcar=True
        )

    trechos = await buscar("armazenamento de vetores")
    assert trechos, "a metade vetorial deveria responder sozinha"
    assert trechos[0].fonte_ref == "/notas/banco.md"
    assert trechos[0].posicao_vetorial == 1


async def test_ollama_fora_do_ar_degrada_para_lexical(indexado):
    usar(EmbedderQuebrado())
    trechos = await buscar("pgvector")
    assert trechos and trechos[0].fonte_ref == "/notas/banco.md"
    assert all(t.origem == "lexical" for t in trechos)


async def test_filtro_por_fonte_tipo(indexado):
    trechos = await buscar("projeto instalação passos", fonte_tipo="nota")
    assert all(t.fonte_tipo == "nota" for t in trechos)
    assert not any(t.fonte_ref == "/repo/README.md" for t in trechos)


async def test_filtro_por_fonte_tipo_aceita_lista(indexado):
    trechos = await buscar("anotação de estudo", fonte_tipo=["nota", "repo"])
    assert {t.fonte_tipo for t in trechos} <= {"nota", "repo"}


async def test_filtro_por_tag(indexado):
    trechos = await buscar("anotação de estudo", tags=["postgres"])
    assert trechos and all(t.fonte_ref == "/notas/banco.md" for t in trechos)


async def test_filtro_por_tag_e_aplicado_antes_do_corte(indexado):
    # Com o filtro depois da fusão, "doc" (1 chunk) seria engolido pelas notas.
    trechos = await buscar("anotação de estudo", tags=["doc"], limite=5)
    assert trechos and all(t.fonte_tipo == "repo" for t in trechos)


async def test_limite_e_respeitado(indexado):
    trechos = await buscar("anotação de estudo", limite=2)
    assert len(trechos) == 2


async def test_devolve_titulo_e_caminho_para_citar(indexado):
    (t, *_) = await buscar("pgvector")
    assert t.fonte_ref.endswith("banco.md")
    assert t.titulo and "Banco" in t.titulo
    assert t.metadados.get("tags") == ["infra", "postgres"]


# ── Distância (a medida de confiança da F3) ───────────────────────


async def test_trecho_traz_a_distancia_de_cosseno(indexado):
    usar(EmbedderTrigrama())
    for tipo in ("nota", "repo"):
        await indexar([d for d in DOCS if d.fonte_tipo == tipo], fonte_tipo=tipo, forcar=True)

    trechos = await buscar("armazenamento de vetores")
    assert trechos[0].distancia is not None
    # Cosseno normalizado: 0 = idêntico, 2 = oposto.
    assert 0.0 <= trechos[0].distancia <= 2.0
    # O primeiro colocado é o mais próximo — a lista vetorial vem ordenada por
    # distância, e é isso que o piso da F3 vai ler.
    distancias = [t.distancia for t in trechos if t.distancia is not None]
    assert distancias == sorted(distancias)


async def test_chunk_que_veio_so_do_full_text_nao_tem_distancia(indexado):
    usar(EmbedderQuebrado())
    (t, *_) = await buscar("pgvector")
    assert t.origem == "lexical" and t.distancia is None
