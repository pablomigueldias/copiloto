"""O simulado e o ciclo de reforço — a regra que trava a próxima prova.

A montagem é função pura (o sorteio entra por parâmetro); o ciclo — entregar,
abrir reforço, aprovar com 75%, liberar — roda contra o Postgres, porque o que
importa ali é o estado gravado.
"""
from __future__ import annotations

import os
import random
import uuid
from collections import Counter
from pathlib import Path

import pytest

from app.db.models.estudo.questao import Modulo, Topico
from app.db.session import get_session
from app.estudo import assuntos as cat
from app.estudo import servico
from app.estudo import simulado as sim

# ── A montagem, pura ─────────────────────────────────────────────────────


def _pool(por_assunto: int = 4, texto: dict[str, str] | None = None) -> dict:
    """Um estoque com `por_assunto` questões em cada assunto do catálogo."""
    texto = texto or {}
    pool: dict[str, list[sim.Candidata]] = {}
    for m in cat.MATERIAS:
        pool[m.chave] = [
            sim.Candidata(uuid.uuid4(), a, texto.get(a))
            for g in m.grupos for a in g.assuntos for _ in range(por_assunto)
        ]
    return pool


def test_caderno_tem_as_quantidades_do_edital():
    caderno = sim.montar(_pool(), sim.Historico(), random.Random(1))
    por_materia = Counter(e.materia for e in caderno)
    assert por_materia == {"pt": 10, "mat": 10, "en": 10, "bd": 30}
    assert [e.materia for e in caderno] == sorted(
        (e.materia for e in caderno), key=["bd", "mat", "pt", "en"].index
    ), "o caderno abre com os específicos, depois Matemática, Português e Inglês"
    assert len({e.questao_id for e in caderno}) == 60, "questão repetida no caderno"


def test_peso_da_banca_manda_nas_vagas():
    """Classes de palavras (33,5%) e interpretação (24,5%) somam 6 de 10 em PT."""
    caderno = sim.montar(_pool(), sim.Historico(), random.Random(7))
    grupos = Counter(cat.ONDE[e.assunto][1].nome for e in caderno if e.materia == "pt")
    assert grupos["Classes de palavras"] == 3
    assert grupos["Interpretação de texto"] >= 2


def test_assunto_errado_volta_no_simulado_seguinte():
    hist = sim.Historico(errados=["Triggers", "Crase", "Área e perímetro"])
    caderno = sim.montar(_pool(), hist, random.Random(3))
    revisoes = {e.assunto for e in caderno if e.revisao}
    assert revisoes == {"Triggers", "Crase", "Área e perímetro"}


def test_revisao_nao_passa_de_30_por_cento_da_materia():
    errados = list(cat.PT.grupos[0].assuntos)  # 9 assuntos de PT errados
    caderno = sim.montar(_pool(), sim.Historico(errados=errados), random.Random(3))
    assert sum(1 for e in caderno if e.materia == "pt" and e.revisao) == 3


def test_questao_nunca_usada_vem_antes_da_usada():
    pool = _pool(por_assunto=3)
    usadas = Counter({c.id: 1 for cs in pool.values() for c in cs[::3]})
    caderno = sim.montar(pool, sim.Historico(uso=usadas), random.Random(5))
    assert not any(usadas[e.questao_id] for e in caderno)


def test_estoque_curto_redistribui_e_nao_inventa():
    """Inglês com 5 questões no estoque dá 5 questões, não 10 nem erro."""
    pool = _pool()
    pool["en"] = pool["en"][:5]
    caderno = sim.montar(pool, sim.Historico(), random.Random(1))
    assert Counter(e.materia for e in caderno)["en"] == 5


def test_questoes_do_mesmo_texto_ficam_juntas():
    pool = _pool(texto={"Interpretação: inferência e sentido de trecho": "T1",
                        "Interpretação: informação explícita no texto": "T1"})
    caderno = sim.montar(pool, sim.Historico(), random.Random(11))
    pt = [e for e in caderno if e.materia == "pt"]
    textos = [i for i, e in enumerate(pt) if e.assunto.startswith("Interpretação: inf")]
    assert textos == list(range(textos[0], textos[0] + len(textos)))


def test_cotas_respeitam_o_que_existe():
    grupos = cat.BD.grupos
    disponivel = {g.nome: 100 for g in grupos} | {"Backup e recuperação": 0}
    cotas = sim._cotas(grupos, 30, disponivel, set(), random.Random(0))
    assert sum(cotas.values()) == 30
    assert cotas["Backup e recuperação"] == 0


# ── O ciclo, contra o banco ──────────────────────────────────────────────

ASSUNTOS_TESTE = {
    "pt": "Crase",
    "mat": "Teorema de Pitágoras",
    "en": "Referência pronominal",
    "bd": "Triggers",
}


async def _semear(por_materia: int = 3) -> None:
    async with get_session() as s:
        mod = Modulo(nome="Estoque", trilha="concurso")
        s.add(mod)
        await s.flush()
        top = Topico(modulo_id=mod.id, nome="Tudo")
        s.add(top)
        await s.commit()
        topico_id = top.id
    for materia, assunto in ASSUNTOS_TESTE.items():
        for n in range(por_materia):
            await servico.criar_questao({
                "topico_id": topico_id,
                "assunto": assunto,
                "formato": "multipla_escolha",
                "enunciado": f"{materia} {n}",
                "alternativas": [{"letra": letra, "texto": letra} for letra in "ABCDE"],
                "afirmacoes": [],
                "gabarito": "A",
                "dificuldade": 2,
            })


async def _reforco_com_questoes(reforco_id: str) -> None:
    async with get_session() as s:
        top = (await s.execute(Topico.__table__.select())).first()
    ids = []
    for n in range(5):
        q = await servico.criar_questao({
            "topico_id": top.id,
            "formato": "multipla_escolha",
            "enunciado": f"reforço {n}",
            "alternativas": [{"letra": letra, "texto": letra} for letra in "ABCDE"],
            "afirmacoes": [],
            "gabarito": "B",
            "dificuldade": 2,
        })
        ids.append(q.id)
    await sim.vincular_reforco(uuid.UUID(reforco_id), ids)


async def test_nota_pela_formula_do_edital_e_branco_e_erro():
    await _semear()
    s = await sim.iniciar(semente=1)
    dados = await sim.obter(s.id)
    assert dados["total"] == 12
    # Durante a prova, nada que entregue a resposta.
    assert all(it["questao"]["gabarito"] is None for it in dados["itens"])
    assert all(it["assunto"] is None for it in dados["itens"])

    # 6 certas, 3 erradas, 3 em branco.
    for it in dados["itens"][:6]:
        await sim.marcar(s.id, it["ordem"], "A")
    for it in dados["itens"][6:9]:
        await sim.marcar(s.id, it["ordem"], "C")
    r = await sim.finalizar(s.id)

    assert r["acertos"] == 6
    assert r["nota"] == pytest.approx(100 / 12 * 6)  # P = 100/Q × TA
    assert r["habilitado"] is True  # 50,00 é o mínimo do item 12.6
    assert len(r["erros"]) == 6
    assert all(e["questao"]["gabarito"] == "A" for e in r["erros"])


async def test_entregar_abre_um_reforco_por_assunto_errado_e_trava():
    await _semear()
    s = await sim.iniciar(semente=1)
    dados = await sim.obter(s.id)
    for it in dados["itens"]:
        # Erra só Triggers e Crase.
        certo = it["materia"] in ("mat", "en")
        await sim.marcar(s.id, it["ordem"], "A" if certo else "E")
    r = await sim.finalizar(s.id)

    assert {x["assunto"] for x in r["reforcos"]} == {"Triggers", "Crase"}
    assert all(x["estado"] == "aguardando_questoes" for x in r["reforcos"])
    estado = await sim.estado()
    assert estado["liberado"] is False
    with pytest.raises(sim.SimuladoBloqueado):
        await sim.iniciar()


async def test_reforco_com_75_por_cento_libera_e_com_menos_abre_outra_rodada():
    await _semear()
    s = await sim.iniciar(semente=1)
    for it in (await sim.obter(s.id))["itens"]:
        await sim.marcar(s.id, it["ordem"], "A" if it["materia"] != "bd" else "E")
    r = await sim.finalizar(s.id)
    (pendente,) = r["reforcos"]
    assert pendente["assunto"] == "Triggers"

    # Rodada 1: 3 de 5 (60%) não passa.
    await _reforco_com_questoes(pendente["id"])
    for ordem, resposta in enumerate("BBBCC", 1):
        out = await sim.responder_reforco(uuid.UUID(pendente["id"]), ordem, resposta)
    assert out["reforco"]["estado"] == "reprovado"
    (segunda,) = (await sim.estado())["reforcos_pendentes"]
    assert (segunda["assunto"], segunda["rodada"]) == ("Triggers", 2)
    assert segunda["estado"] == "aguardando_questoes"

    # Rodada 2: 4 de 5 (80%) passa, e o simulado seguinte abre.
    await _reforco_com_questoes(segunda["id"])
    for ordem, resposta in enumerate("BBBBC", 1):
        out = await sim.responder_reforco(uuid.UUID(segunda["id"]), ordem, resposta)
    assert out["reforco"]["estado"] == "aprovado"
    assert (await sim.estado())["liberado"] is True

    # E Triggers volta no simulado nº 2, marcada como revisão.
    s2 = await sim.iniciar(semente=2)
    assert s2.numero == 2
    revisoes = [it for it in s2.itens if it.revisao]
    assert [it.assunto for it in revisoes] == ["Triggers"]


async def test_simulado_entregue_nao_aceita_resposta():
    await _semear()
    s = await sim.iniciar(semente=1)
    await sim.finalizar(s.id)
    with pytest.raises(sim.EstadoInvalido):
        await sim.marcar(s.id, 1, "A")


async def test_reforco_sem_questoes_nao_aceita_resposta():
    await _semear()
    s = await sim.iniciar(semente=1)
    r = await sim.finalizar(s.id)  # tudo em branco: 4 reforços
    with pytest.raises(sim.EstadoInvalido, match="ainda não tem questões"):
        await sim.responder_reforco(uuid.UUID(r["reforcos"][0]["id"]), 1, "A")


async def test_insumo_da_rodada_2_traz_o_erro_do_reforco_anterior():
    """Quem escreve a rodada 2 precisa ver onde a rodada 1 falhou."""
    await _semear()
    s = await sim.iniciar(semente=1)
    for it in (await sim.obter(s.id))["itens"]:
        await sim.marcar(s.id, it["ordem"], "A" if it["materia"] != "bd" else "E")
    (pendente,) = (await sim.finalizar(s.id))["reforcos"]
    await _reforco_com_questoes(pendente["id"])
    for ordem, resposta in enumerate("BBCCC", 1):
        await sim.responder_reforco(uuid.UUID(pendente["id"]), ordem, resposta)

    (insumo,) = await sim.para_escrever()
    assert (insumo["assunto"], insumo["rodada"]) == ("Triggers", 2)
    onde = [e["onde"] for e in insumo["erros"]]
    assert onde.count("reforço rodada 1") == 3
    assert any(o.startswith("simulado nº 1") for o in onde)
    assert len(insumo["origens_ja_usadas"]) == 5


# ── O botão "Gerar reforço" ──────────────────────────────────────────────


async def _um_reforco_pendente() -> dict:
    await _semear()
    s = await sim.iniciar(semente=1)
    for it in (await sim.obter(s.id))["itens"]:
        await sim.marcar(s.id, it["ordem"], "A" if it["materia"] != "bd" else "E")
    (pendente,) = (await sim.finalizar(s.id))["reforcos"]
    return pendente


async def test_gerar_marca_gerando_e_dispara_um_processo(monkeypatch):
    pendente = await _um_reforco_pendente()
    disparos = []
    monkeypatch.setattr(sim, "_disparar_processo", lambda ids: disparos.append(ids) or os.getpid())

    (r,) = await sim.gerar([uuid.UUID(pendente["id"])])
    assert r["geracao"] == "gerando"
    assert disparos == [[pendente["id"]]]

    # Clique duplo não dispara outro processo.
    assert await sim.gerar([uuid.UUID(pendente["id"])]) == []
    assert len(disparos) == 1


async def test_gerando_de_processo_morto_aparece_como_erro(monkeypatch):
    pendente = await _um_reforco_pendente()
    monkeypatch.setattr(sim, "_disparar_processo", lambda ids: 999_999_999)  # pid que não existe
    await sim.gerar([uuid.UUID(pendente["id"])])

    (r,) = (await sim.estado())["reforcos_pendentes"]
    assert r["geracao"] == "erro"
    assert "interrompida" in r["geracao_erro"]


async def test_gerar_recusa_reforco_que_ja_tem_questoes(monkeypatch):
    pendente = await _um_reforco_pendente()
    await _reforco_com_questoes(pendente["id"])
    monkeypatch.setattr(sim, "_disparar_processo", lambda ids: os.getpid())
    with pytest.raises(sim.EstadoInvalido, match="já tem questões"):
        await sim.gerar([uuid.UUID(pendente["id"])])


async def test_quem_decide_o_resultado_da_geracao_e_o_banco():
    """O modelo pode dizer 'pronto'; se o reforço não foi importado, é erro."""
    gerador = _carregar_gerador()
    pendente = await _um_reforco_pendente()
    rid = uuid.UUID(pendente["id"])

    assert await gerador.finalizar(rid, "Pronto! As 5 questões cobram triggers.") == "erro"
    (r,) = (await sim.estado())["reforcos_pendentes"]
    assert r["geracao"] == "erro" and "Pronto!" in r["geracao_erro"]

    await _reforco_com_questoes(pendente["id"])
    assert await gerador.finalizar(rid, "") == "ok"


def _carregar_gerador():
    import importlib.util

    caminho = Path(__file__).resolve().parents[1] / "scripts/simulado/gerar_reforco.py"
    spec = importlib.util.spec_from_file_location("gerar_reforco", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_prompt_leva_o_erro_e_os_caminhos_do_assunto():
    gerador = _carregar_gerador()

    class Q:
        texto_base = codigo = comando = explicacao = None
        enunciado = "Em um trigger BEFORE INSERT no MySQL, altera-se"
        afirmacoes = []
        alternativas = [{"letra": "A", "texto": "NEW.preco"}, {"letra": "B", "texto": "OLD.preco"}]
        gabarito = "A"

    insumo = {"simulado": 3, "materia": "bd", "assunto": "Triggers", "rodada": 2,
              "erros": [{"onde": "simulado nº 3, questão 7", "marcou": "B", "questao": Q()}],
              "origens_ja_usadas": ["Reforço (sem banca) · simulado nº 03 · Triggers · rodada 1 · nº 1"]}
    p = gerador.montar_prompt(insumo, "triggers-r2")
    assert "marcou B, gabarito A" in p and "OLD.preco" in p
    assert "scripts/simulado/reforco/s03_triggers_r2.py" in p
    assert "data/estudo/reforco/simulado-03-triggers-r2.json" in p
    assert 'Reforco(simulado=3, nome="triggers-r2")' in p
