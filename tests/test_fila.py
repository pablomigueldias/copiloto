"""A fila de aprovação e o dataset que ela produz.

Sem Redis e sem Ollama: o que se testa aqui é a máquina de estados e a captura
do par `texto_gerado`/`texto_final` — a parte de que a F9 depende e que, se
falhar em silêncio, só se descobre daqui a seis meses, na hora de treinar.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.exemplo_estilo import ExemploEstilo
from app.db.session import get_session
from app.fila import exemplos, servico
from app.llm import gateway

GERADO = "Vi que vocês publicaram a vaga de dados. Trabalhei com Airflow por dois anos."
MEU = "Vi a vaga de dados de vocês. Rodei Airflow em produção por dois anos."


class EmbedderFalso:
    nome = "falso"

    def __init__(self) -> None:
        self.chamadas = 0

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        raise AssertionError("a fila não gera texto")

    async def embedar(self, textos, *, modelo):
        self.chamadas += 1
        return [self._vetor(t) for t in textos]

    @staticmethod
    def _vetor(texto: str) -> list[float]:
        v = [0.0] * 1024
        for palavra in texto.lower().split():
            v[hash(palavra) % 1024] += 1.0
        norma = sum(x * x for x in v) ** 0.5
        return [x / norma for x in v] if norma else [1.0] + [0.0] * 1023


@pytest.fixture
async def perfil_mestre():
    """Um Perfil Mestre mínimo — o PDF precisa do nome e do contato."""
    from app.db.models.pessoal.perfil_mestre import PerfilMestre

    async with get_session() as s:
        s.add(
            PerfilMestre(
                nome="Pablo Miguel Dias Ortiz",
                resumo="Dev Python.",
                contato={"email": "pablo@exemplo.dev"},
                habilidades=[{"nome": "Python"}, {"nome": "FastAPI"}],
                experiencias=[
                    {"empresa": "Sechat", "cargo": "Analista", "periodo": "2025",
                     "descricao": "Zoho One"}
                ],
            )
        )
        await s.commit()


@pytest.fixture
def embedder():
    p = EmbedderFalso()
    gateway.usar_provider(p)
    yield p
    gateway.usar_provider(gateway.OllamaProvider())


async def nova(**kw):
    base = dict(
        agente="outreach",
        tipo="email_frio",
        titulo="E-mail para a Acme",
        texto_gerado=GERADO,
        contexto="agência pequena que pediu orçamento de automação",
    )
    return await servico.criar(**{**base, **kw})


# ── Criar e listar ────────────────────────────────────────────────


async def test_acao_nasce_pendente(embedder):
    acao = await nova()
    assert acao.status == "pendente" and acao.decidida_em is None
    assert acao.decidida is False


async def test_fila_lista_a_mais_antiga_primeiro(embedder):
    primeira = await nova(titulo="Primeira")
    await nova(titulo="Segunda")

    total, itens = await servico.listar()
    assert total == 2
    # Decidir é FIFO: quem está esperando há mais tempo aparece antes.
    assert itens[0].id == primeira.id


async def test_lista_filtra_por_agente_e_status(embedder):
    await nova(agente="candidatura")
    outra = await nova(agente="outreach")
    await servico.decidir(outra.id, decisao="aprovar")

    _, pendentes = await servico.listar(status="pendente")
    assert [a.agente for a in pendentes] == ["candidatura"]

    total, _ = await servico.listar(status="aprovada", agente="outreach")
    assert total == 1


async def test_contagem_por_status(embedder):
    a, b = await nova(), await nova()
    await servico.decidir(a.id, decisao="rejeitar", motivo="tom errado")
    await servico.decidir(b.id, decisao="aprovar")

    assert await servico.contar_por_status() == {"rejeitada": 1, "aprovada": 1}


# ── A máquina de estados ──────────────────────────────────────────


async def test_aprovar_sem_mexer_no_texto(embedder):
    acao = await servico.decidir((await nova()).id, decisao="aprovar")

    assert acao.status == "aprovada"
    assert acao.decidida_em is not None
    # Grava o texto final mesmo idêntico: "aprovei sem mexer" é informação.
    assert acao.texto_final == GERADO


async def test_aprovar_com_texto_diferente_vira_editada(embedder):
    acao = await servico.decidir((await nova()).id, decisao="aprovar", texto_final=MEU)

    # O rótulo sai do texto, não da intenção de quem clicou — senão o dataset
    # da F9 dependeria de o usuário admitir que mexeu.
    assert acao.status == "editada"
    assert acao.texto_gerado == GERADO and acao.texto_final == MEU


async def test_editar_com_texto_igual_e_so_aprovacao(embedder):
    acao = await servico.decidir(
        (await nova()).id, decisao="editar", texto_final=f"  {GERADO}  "
    )
    # Espaço em branco não é edição.
    assert acao.status == "aprovada"


async def test_rejeitar_guarda_o_motivo(embedder):
    acao = await servico.decidir(
        (await nova()).id, decisao="rejeitar", motivo="genérico demais"
    )
    assert acao.status == "rejeitada" and acao.motivo == "genérico demais"
    assert acao.texto_final is None


async def test_decidir_duas_vezes_e_recusado(embedder):
    acao = await nova()
    await servico.decidir(acao.id, decisao="aprovar")

    with pytest.raises(servico.JaDecidida):
        await servico.decidir(acao.id, decisao="rejeitar", motivo="mudei de ideia")

    # E o primeiro veredito continua de pé.
    assert (await servico.obter(acao.id)).status == "aprovada"


async def test_acao_inexistente(embedder):
    import uuid

    with pytest.raises(servico.AcaoNaoEncontrada):
        await servico.decidir(uuid.uuid4(), decisao="aprovar")


# ── O que a decisão produz ────────────────────────────────────────


async def contar_exemplos() -> int:
    async with get_session() as s:
        return len((await s.scalars(select(ExemploEstilo))).all())


async def test_aprovar_vira_exemplo_de_estilo(embedder):
    await servico.decidir((await nova()).id, decisao="aprovar")

    async with get_session() as s:
        (e,) = (await s.scalars(select(ExemploEstilo))).all()
    assert e.tarefa == "email_frio"
    assert e.texto == GERADO
    assert e.contexto == "agência pequena que pediu orçamento de automação"
    # O embedding fica para o worker: aprovar não espera GPU.
    assert e.embedding is None
    assert embedder.chamadas == 0


async def test_editar_tambem_vira_exemplo_com_o_MEU_texto(embedder):
    await servico.decidir((await nova()).id, decisao="aprovar", texto_final=MEU)

    async with get_session() as s:
        (e,) = (await s.scalars(select(ExemploEstilo))).all()
    # O few-shot aprende com o que eu escrevi, não com o que a IA escreveu.
    assert e.texto == MEU


async def test_rejeitar_nao_vira_exemplo(embedder):
    await servico.decidir((await nova()).id, decisao="rejeitar", motivo="ruim")
    assert await contar_exemplos() == 0


async def test_acao_sem_texto_nao_vira_exemplo(embedder):
    acao = await nova(texto_gerado=None)
    await servico.decidir(acao.id, decisao="aprovar")
    assert await contar_exemplos() == 0


async def test_falha_ao_registrar_exemplo_nao_desfaz_a_decisao(embedder, monkeypatch):
    async def explode(_):
        raise RuntimeError("banco caiu no meio")

    monkeypatch.setattr(exemplos, "registrar", explode)
    acao = await servico.decidir((await nova()).id, decisao="aprovar")

    # A decisão é minha e já foi tomada; perder o exemplo é ruim, desfazer é pior.
    assert acao.status == "aprovada"


# ── Few-shot ──────────────────────────────────────────────────────


async def test_embedar_pendentes_preenche_e_e_idempotente(embedder):
    await servico.decidir((await nova()).id, decisao="aprovar")

    assert await exemplos.embedar_pendentes() == 1
    # Rodar de novo não reembeda nada — é job de worker, roda a toda hora.
    assert await exemplos.embedar_pendentes() == 0

    async with get_session() as s:
        (e,) = (await s.scalars(select(ExemploEstilo))).all()
    assert e.embedding is not None and len(e.embedding) == 1024


async def test_exemplos_para_escolhe_por_similaridade_de_contexto(embedder):
    a = await nova(contexto="agência de marketing pediu orçamento de automação")
    b = await nova(contexto="startup de logística quer integrar rastreamento de frota")
    await servico.decidir(a.id, decisao="aprovar", texto_final="Texto da agência.")
    await servico.decidir(b.id, decisao="aprovar", texto_final="Texto da logística.")
    await exemplos.embedar_pendentes()

    achados = await exemplos.exemplos_para(
        "email_frio", "empresa de logística quer rastreamento de frota", n=1
    )
    assert [e.texto for e in achados] == ["Texto da logística."]


async def test_exemplos_para_cai_para_os_recentes_sem_embedding(embedder):
    await servico.decidir((await nova()).id, decisao="aprovar", texto_final="Recente.")

    # Worker ainda não passou: melhor três exemplos meus quaisquer que nenhum.
    achados = await exemplos.exemplos_para("email_frio", "qualquer situação nova")
    assert [e.texto for e in achados] == ["Recente."]


async def test_exemplos_para_nao_mistura_tarefas(embedder):
    await servico.decidir((await nova()).id, decisao="aprovar")
    await exemplos.embedar_pendentes()

    assert await exemplos.exemplos_para("bullet_curriculo", "qualquer coisa") == []


async def test_bloco_few_shot_vazio_quando_nao_ha_exemplo():
    assert exemplos.bloco_few_shot([]) == ""


async def test_bloco_few_shot_traz_situacao_e_texto(embedder):
    await servico.decidir((await nova()).id, decisao="aprovar")
    bloco = exemplos.bloco_few_shot(await exemplos.exemplos_para("email_frio", ""))

    assert "agência pequena" in bloco and GERADO in bloco
    assert "voz" in bloco.lower()


# ── o texto aprovado tem que virar o documento ────────────────────


async def test_aprovar_curriculo_editado_atualiza_a_vaga_e_o_pdf(perfil_mestre):
    """O defeito relatado: eu corrigia na fila, aprovava, e o PDF que eu ia
    anexar continuava com o texto do modelo."""
    from app.candidatura import curriculo as gerador
    from app.candidatura import perfil as perfil_mod
    from app.candidatura import servico as candidatura
    from app.candidatura import vagas

    vaga = await vagas.criar(
        descricao="Vaga de Dev Python com FastAPI e PostgreSQL. " * 3,
        titulo="Dev Python",
    )
    fatos = await perfil_mod.carregar()
    original = gerador.Curriculo(
        titulo="Dev Python",
        resumo="Resumo do modelo.",
        experiencias=[
            {"empresa": "Sechat", "cargo": "Analista", "periodo": "2025",
             "bullets": ["Texto que o modelo escreveu."]}
        ],
    )

    from app.db.models.pessoal.vaga import Vaga
    from app.db.session import get_session

    async with get_session() as s:
        alvo = await s.get(Vaga, vaga.id)
        alvo.curriculo_json = original.como_json()
        await s.commit()

    acao = await servico.criar(
        agente="candidatura", tipo="curriculo", titulo="Currículo para Dev Python",
        texto_gerado=gerador.como_texto(original, fatos),
        payload={"vaga_id": str(vaga.id)},
    )

    meu_texto = gerador.como_texto(original, fatos).replace(
        "Texto que o modelo escreveu.", "Reduzi de 3h para 20min o fechamento."
    )
    await servico.decidir(acao.id, decisao="aprovar", texto_final=meu_texto)

    atualizada = await vagas.obter(vaga.id)
    bullets = atualizada.curriculo_json["experiencias"][0]["bullets"]
    assert bullets == ["Reduzi de 3h para 20min o fechamento."]

    # E o PDF, que reimprime do JSON, sai com o meu texto.
    caminho, _ = await candidatura.pdf_da_vaga(vaga.id)
    import pymupdf

    with pymupdf.open(caminho) as doc:
        lido = "".join(p.get_text() for p in doc)
    assert "Reduzi de 3h para 20min" in lido
    assert "Texto que o modelo escreveu" not in lido


async def test_aprovar_sem_editar_nao_mexe_no_curriculo(perfil_mestre):
    from app.candidatura import curriculo as gerador
    from app.candidatura import perfil as perfil_mod
    from app.candidatura import vagas

    vaga = await vagas.criar(descricao="Vaga de Dev Python. " * 6, titulo="Dev")
    fatos = await perfil_mod.carregar()
    c = gerador.Curriculo(titulo="Dev", resumo="Como saiu do modelo.")

    from app.db.models.pessoal.vaga import Vaga
    from app.db.session import get_session

    async with get_session() as s:
        alvo = await s.get(Vaga, vaga.id)
        alvo.curriculo_json = c.como_json()
        await s.commit()

    acao = await servico.criar(
        agente="candidatura", tipo="curriculo", titulo="Currículo",
        texto_gerado=gerador.como_texto(c, fatos), payload={"vaga_id": str(vaga.id)},
    )
    await servico.decidir(acao.id, decisao="aprovar")

    assert (await vagas.obter(vaga.id)).curriculo_json == c.como_json()
