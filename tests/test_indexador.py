"""Indexação incremental — a parte que decide se isto é um índice ou um script.

Sem Ollama: o embedder é falso e determinístico. O que se testa aqui é o
controle de mudança (hash, remoção, substituição), não a qualidade do vetor.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.conhecimento.fontes import Documento
from app.conhecimento.indexador import apagar_fonte, indexar
from app.db.models.conhecimento import ConhecimentoChunk
from app.db.session import get_session
from app.llm import gateway


class EmbedderFalso:
    nome = "falso"

    def __init__(self) -> None:
        self.textos: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("indexador não deve gerar texto")

    async def embedar(self, textos, *, modelo):
        self.textos.extend(textos)
        return [[0.001 * (len(t) % 100)] * 1024 for t in textos]


@pytest.fixture
def embedder():
    p = EmbedderFalso()
    gateway.usar_provider(p)
    yield p
    gateway.usar_provider(gateway.OllamaProvider())


def doc(ref: str, conteudo: str, titulo: str = "Nota") -> Documento:
    return Documento(fonte_tipo="nota", fonte_ref=ref, titulo=titulo, conteudo=conteudo)


LONGO = "Conteúdo com tamanho suficiente para virar um chunk de verdade. " * 6


async def contar() -> int:
    async with get_session() as s:
        return await s.scalar(select(func.count(ConhecimentoChunk.id))) or 0


async def test_indexa_e_grava_chunks(embedder):
    r = await indexar([doc("/a.md", LONGO)], fonte_tipo="nota")
    assert r.indexados == 1 and r.chunks >= 1
    assert await contar() == r.chunks

    async with get_session() as s:
        chunk = await s.scalar(select(ConhecimentoChunk))
    assert chunk.fonte_ref == "/a.md"
    assert chunk.titulo.startswith("Nota")
    assert len(chunk.embedding) == 1024


async def test_segunda_passada_nao_reembeda_nada(embedder):
    docs = [doc("/a.md", LONGO), doc("/b.md", LONGO + "outro")]
    await indexar(docs, fonte_tipo="nota")
    embedder.textos.clear()

    r = await indexar(docs, fonte_tipo="nota")
    assert r.inalterados == 2 and r.indexados == 0
    # O ponto da fase: documento sem mudança não custa nem uma chamada de GPU.
    assert embedder.textos == []


async def test_forcar_reindexa_mesmo_sem_mudanca(embedder):
    await indexar([doc("/a.md", LONGO)], fonte_tipo="nota")
    embedder.textos.clear()
    r = await indexar([doc("/a.md", LONGO)], fonte_tipo="nota", forcar=True)
    assert r.indexados == 1 and embedder.textos


async def test_documento_editado_substitui_os_chunks_antigos(embedder):
    await indexar([doc("/a.md", LONGO)], fonte_tipo="nota")

    novo = "Texto completamente diferente agora. " * 30
    await indexar([doc("/a.md", novo)], fonte_tipo="nota")

    async with get_session() as s:
        conteudos = (await s.scalars(select(ConhecimentoChunk.conteudo))).all()
    # Nada do texto velho sobrou: é DELETE + INSERT, não upsert por posição.
    assert all("Conteúdo com tamanho" not in c for c in conteudos)


async def test_arquivo_que_sumiu_sai_do_indice(embedder):
    await indexar([doc("/a.md", LONGO), doc("/b.md", LONGO + "b")], fonte_tipo="nota")
    r = await indexar([doc("/a.md", LONGO)], fonte_tipo="nota")
    assert r.removidos == 1

    async with get_session() as s:
        refs = set((await s.scalars(select(ConhecimentoChunk.fonte_ref))).all())
    assert refs == {"/a.md"}


async def test_remocao_pode_ser_desligada(embedder):
    await indexar([doc("/a.md", LONGO), doc("/b.md", LONGO + "b")], fonte_tipo="nota")
    r = await indexar([doc("/a.md", LONGO)], fonte_tipo="nota", remover_ausentes=False)
    assert r.removidos == 0
    assert await contar() > 0


async def test_fontes_diferentes_nao_se_apagam(embedder):
    await indexar([doc("/a.md", LONGO)], fonte_tipo="nota")
    outro = Documento(fonte_tipo="repo", fonte_ref="/r.md", titulo="R", conteudo=LONGO)
    r = await indexar([outro], fonte_tipo="repo")
    assert r.removidos == 0

    async with get_session() as s:
        tipos = set((await s.scalars(select(ConhecimentoChunk.fonte_tipo))).all())
    assert tipos == {"nota", "repo"}


async def test_falha_de_embedding_nao_para_a_varredura(embedder):
    class MeioQuebrado(EmbedderFalso):
        async def embedar(self, textos, *, modelo):
            if any("veneno" in t for t in textos):
                raise RuntimeError("OOM de VRAM")
            return await super().embedar(textos, modelo=modelo)

    gateway.usar_provider(MeioQuebrado())
    r = await indexar(
        [doc("/ruim.md", "veneno " + LONGO), doc("/bom.md", LONGO)], fonte_tipo="nota"
    )
    assert r.erros == 1 and r.indexados == 1


async def test_apagar_fonte(embedder):
    await indexar([doc("/a.md", LONGO)], fonte_tipo="nota")
    assert await apagar_fonte("nota", "/a.md") > 0
    assert await contar() == 0
