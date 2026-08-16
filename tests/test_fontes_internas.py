"""Perfil Mestre e vagas viram documentos indexáveis.

O que importa aqui não é o formato do markdown gerado, é o contrato com o resto
da fase: um documento por bloco, `fonte_ref` estável (senão toda varredura
reembeda tudo) e hash que muda quando — e só quando — o dado muda.
"""
from __future__ import annotations

import pytest

from app.conhecimento.fontes_internas import ler_perfil_mestre, ler_vagas
from app.conhecimento.indexador import indexar
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.models.pessoal.vaga import Vaga
from app.db.session import get_session
from app.llm import gateway


async def salvar(obj):
    async with get_session() as s:
        s.add(obj)
        await s.commit()
        await s.refresh(obj)
    return obj


@pytest.fixture
async def perfil():
    return await salvar(
        PerfilMestre(
            nome="Pablo",
            titulo="Dev Full-Stack",
            resumo="Construo sistemas que rodam sozinhos.",
            tom_escrita="Frases curtas. Sem adjetivo de venda.",
            habilidades=[{"nome": "Python", "nivel": "avançado", "onde_usou": "Copiloto"}],
            projetos=[
                {
                    "nome": "Copiloto",
                    "descricao": "Assistente local-first com RAG em pgvector",
                    "stack": ["FastAPI", "Postgres"],
                    "prova": "reduziu de 3h para 20min",
                }
            ],
            certificacoes=[{"nome": "AWS Cloud Practitioner", "ano": 2025}],
            contato={"email": "pablo@exemplo.dev"},
        )
    )


@pytest.fixture
async def vaga():
    return await salvar(
        Vaga(
            titulo="Engenheiro de Dados Pleno",
            empresa="Acme",
            localizacao="Remoto",
            senioridade="pleno",
            descricao="Necessário Airflow, dbt e Snowflake. Desejável Terraform.",
            notas="Recrutadora respondeu rápido.",
        )
    )


# ── Perfil Mestre ─────────────────────────────────────────────────


async def test_um_documento_por_bloco(perfil):
    docs = await ler_perfil_mestre()
    blocos = {d.metadados["bloco"] for d in docs}
    assert blocos == {"identidade", "habilidades", "projetos", "certificacoes"}
    # Bloco vazio não vira documento vazio ocupando o índice.
    assert "formacao" not in blocos


async def test_conteudo_do_bloco_carrega_o_fato(perfil):
    (projetos,) = [d for d in await ler_perfil_mestre() if d.metadados["bloco"] == "projetos"]
    assert "Copiloto" in projetos.conteudo
    assert "pgvector" in projetos.conteudo
    assert "reduziu de 3h para 20min" in projetos.conteudo  # a prova, que é o valioso
    assert "FastAPI, Postgres" in projetos.conteudo  # lista virou texto legível


async def test_identidade_traz_tom_de_escrita(perfil):
    (ident,) = [d for d in await ler_perfil_mestre() if d.metadados["bloco"] == "identidade"]
    assert "Frases curtas" in ident.conteudo
    assert "pablo@exemplo.dev" in ident.conteudo


async def test_fonte_ref_e_estavel_e_hash_segue_o_dado(perfil):
    antes = {d.fonte_ref: d.hash for d in await ler_perfil_mestre()}
    assert all(r.startswith(f"perfil:{perfil.id}#") for r in antes)

    depois = {d.fonte_ref: d.hash for d in await ler_perfil_mestre()}
    # Sem mudança no banco, hash idêntico — senão o incremental nunca pula nada.
    assert depois == antes

    async with get_session() as s:
        p = await s.get(PerfilMestre, perfil.id)
        p.habilidades = [{"nome": "Rust"}]
        await s.commit()

    novo = {d.fonte_ref: d.hash for d in await ler_perfil_mestre()}
    assert novo[f"perfil:{perfil.id}#habilidades"] != antes[f"perfil:{perfil.id}#habilidades"]
    assert novo[f"perfil:{perfil.id}#identidade"] == antes[f"perfil:{perfil.id}#identidade"]


async def test_perfil_inativo_fica_de_fora(perfil):
    async with get_session() as s:
        p = await s.get(PerfilMestre, perfil.id)
        p.ativo = False
        await s.commit()
    assert await ler_perfil_mestre() == []


# ── Vagas ─────────────────────────────────────────────────────────


async def test_vaga_vira_um_documento_com_ficha_e_descricao(vaga):
    (doc,) = await ler_vagas()
    assert doc.fonte_ref == f"vaga:{vaga.id}"
    assert doc.titulo == "Engenheiro de Dados Pleno — Acme"
    assert "Empresa: Acme" in doc.conteudo
    assert "Snowflake" in doc.conteudo
    assert "Recrutadora respondeu rápido" in doc.conteudo
    assert doc.metadados["status"] == "quero_candidatar"


async def test_vaga_sem_descricao_nao_entra():
    await salvar(Vaga(titulo="Vazia", descricao="   "))
    assert await ler_vagas() == []


async def test_vaga_recusada_continua_valendo_como_vocabulario(vaga):
    async with get_session() as s:
        v = await s.get(Vaga, vaga.id)
        v.status = "fim"
        await s.commit()
    docs = await ler_vagas()
    assert len(docs) == 1 and docs[0].metadados["status"] == "fim"


# ── Ponta a ponta com o indexador ─────────────────────────────────


class EmbedderFalso:
    nome = "falso"

    def __init__(self) -> None:
        self.textos: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("ingestão não gera texto")

    async def embedar(self, textos, *, modelo):
        self.textos.extend(textos)
        return [[0.001 * (len(t) % 100)] * 1024 for t in textos]


@pytest.fixture
def embedder():
    p = EmbedderFalso()
    gateway.usar_provider(p)
    yield p
    gateway.usar_provider(gateway.OllamaProvider())


async def test_indexa_e_a_segunda_passada_nao_reembeda(perfil, vaga, embedder):
    r1 = await indexar(await ler_perfil_mestre(), fonte_tipo="perfil")
    assert r1.indexados == 4 and r1.chunks >= 4

    embedder.textos.clear()
    r2 = await indexar(await ler_perfil_mestre(), fonte_tipo="perfil")
    # O ciclo fecha: dado de banco também é pulado quando não mudou.
    assert r2.inalterados == 4 and embedder.textos == []

    rv = await indexar(await ler_vagas(), fonte_tipo="vaga")
    assert rv.indexados == 1
