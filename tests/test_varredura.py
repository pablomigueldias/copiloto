"""Varredura: agrupar por tipo antes de indexar, e não apagar o que não olhou.

Os dois testes que importam aqui protegem bugs silenciosos — o índice fica
errado e a busca só denuncia semanas depois.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.conhecimento.varredura import ingerir
from app.db.models.conhecimento import ConhecimentoChunk
from app.db.session import get_session
from app.llm import gateway

NOTA = "# {t}\n\n" + "Texto de nota com corpo suficiente para virar um chunk. " * 5


class EmbedderFalso:
    nome = "falso"

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("varredura não gera texto")

    async def embedar(self, textos, *, modelo):
        return [[0.002 * (len(t) % 50)] * 1024 for t in textos]


@pytest.fixture
def embedder():
    gateway.usar_provider(EmbedderFalso())
    yield
    gateway.usar_provider(gateway.OllamaProvider())


@pytest.fixture
def duas_pastas(tmp_path, monkeypatch):
    """Duas pastas com o MESMO fonte_tipo — o caso que quebra ingênuo."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    (a / "um.md").write_text(NOTA.format(t="Um"), encoding="utf-8")
    (b / "dois.md").write_text(NOTA.format(t="Dois"), encoding="utf-8")
    monkeypatch.setattr(settings, "conhecimento_fontes", f"repo:{a},repo:{b}")
    return a, b


async def refs() -> set[str]:
    async with get_session() as s:
        return set((await s.scalars(select(ConhecimentoChunk.fonte_ref))).all())


async def test_duas_pastas_do_mesmo_tipo_convivem(duas_pastas, embedder):
    a, b = duas_pastas
    r = await ingerir(tipos=["repo"])
    # Indexadas numa passada só: a segunda pasta não apaga a primeira.
    assert r["repo"].indexados == 2
    assert await refs() == {str(a / "um.md"), str(b / "dois.md")}


async def test_varredura_parcial_nao_remove_o_que_nao_olhou(duas_pastas, embedder):
    a, _ = duas_pastas
    await ingerir(tipos=["repo"])

    r = await ingerir(tipos=["repo"], caminho=a)
    assert r["repo"].removidos == 0
    # "não vi este arquivo" ali significa "não olhei", não "sumiu".
    assert len(await refs()) == 2


async def test_arquivo_apagado_some_na_varredura_completa(duas_pastas, embedder):
    a, b = duas_pastas
    await ingerir(tipos=["repo"])
    (b / "dois.md").unlink()

    r = await ingerir(tipos=["repo"])
    assert r["repo"].removidos == 1
    assert await refs() == {str(a / "um.md")}


async def test_tipo_desconhecido_e_erro_explicito(embedder):
    with pytest.raises(ValueError, match="desconhecido"):
        await ingerir(tipos=["obsidian"])


async def test_tipo_sem_pasta_configurada_e_pulado(duas_pastas, embedder):
    r = await ingerir(tipos=["nota", "repo"])
    assert "nota" not in r and "repo" in r


async def test_fontes_de_banco_ficam_de_fora_da_varredura_parcial(duas_pastas, embedder):
    r = await ingerir(tipos=["repo", "perfil", "vaga"], caminho=duas_pastas[0])
    assert set(r) == {"repo"}


async def test_config_aceita_caminho_sem_prefixo_de_tipo(monkeypatch, tmp_path, embedder):
    (tmp_path / "n.md").write_text(NOTA.format(t="Solta"), encoding="utf-8")
    monkeypatch.setattr(settings, "conhecimento_fontes", str(tmp_path))

    r = await ingerir(tipos=["nota"])
    assert r["nota"].indexados == 1

    async with get_session() as s:
        tipos = set((await s.scalars(select(ConhecimentoChunk.fonte_tipo))).all())
    assert tipos == {"nota"}


async def test_ingerir_tudo_passa_por_todos_os_tipos(duas_pastas, embedder):
    r = await ingerir()
    # Sem perfil nem vaga no banco, os tipos aparecem com zero documento — é
    # informação: a varredura olhou e não havia nada.
    assert set(r) >= {"repo", "perfil", "vaga"}
    assert r["perfil"].documentos == 0

    async with get_session() as s:
        assert await s.scalar(select(func.count(ConhecimentoChunk.id))) > 0
