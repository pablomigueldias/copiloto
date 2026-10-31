"""O simulado da prova do Avança SP e o ciclo de reforço que ele comanda.

    simulado (60, nota do edital) → diagnóstico por assunto → reforço de 5 por
    assunto errado (75% para passar) → simulado seguinte, com os assuntos
    errados de volta

O que decide cada passo:

**A montagem** (`montar`, função pura — o sorteio entra por parâmetro e o teste
fixa a semente). Cada matéria tem as vagas do edital. Até 30% delas vão para
os assuntos que eu errei nos simulados anteriores, um por assunto, do mais
recente para o mais antigo. O resto é dividido entre os grupos pelo peso da
banca (`assuntos.py`), pelo método do maior resto; o grupo que ficou fora do
último simulado ganha meio ponto no desempate, e é isso que faz o assunto raro
aparecer de vez em quando em vez de nunca. Dentro do grupo, a questão nunca
usada vem antes de tudo — repetida infla a nota —, e entre as inéditas, o
assunto que ainda não está no caderno e o menos visto.

**A nota** é a do edital (item 12.3): P = 100/Q × TA, habilitado com P ≥ 50
(item 12.6). A discursiva não entra — ela só é corrigida para quem passa na
objetiva, e é a objetiva que este simulado mede.

**O reforço** fica fora do estoque. As 5 questões de cada assunto são escritas
depois do simulado, sob medida para o erro, e chegam por
`scripts/simulado/importar_reforco.py`. Até lá o reforço fica
`aguardando_questoes`, e a tela diz isso em vez de inventar questão.
"""
from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.config import BASE_DIR
from app.db.models.estudo.questao import Questao
from app.db.models.estudo.simulado import (
    APROVACAO_REFORCO,
    QUESTOES_POR_REFORCO,
    Reforco,
    ReforcoItem,
    Simulado,
    SimuladoItem,
)
from app.db.session import get_session
from app.estudo import assuntos as cat
from app.estudo.servico import EstudoErro, _em_estudo
from app.utils.logger import get_logger

logger = get_logger()

# Fração das vagas de cada matéria reservada aos assuntos errados antes. Mais
# que isso e o simulado vira reforço disfarçado, e deixa de medir a prova.
FRACAO_REVISAO = 0.3
# Quantos simulados para trás um erro continua puxando o assunto de volta.
JANELA_ERROS = 3
NOTA_MINIMA = 50  # edital, item 12.6


class SimuladoBloqueado(EstudoErro):
    """Há reforço pendente: o ciclo manda fechá-lo antes da próxima prova."""


class SimuladoNaoEncontrado(EstudoErro):
    pass


class ReforcoNaoEncontrado(EstudoErro):
    pass


class EstadoInvalido(EstudoErro):
    """Ação que o estado atual não permite (responder simulado finalizado...)."""


# ── A montagem, pura ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Candidata:
    id: uuid.UUID
    assunto: str
    # Questões do mesmo texto de apoio ficam juntas no caderno.
    texto: str | None = None


@dataclass
class Historico:
    """O que os simulados anteriores dizem para a montagem do próximo."""

    # Quantas vezes cada questão já caiu em simulado.
    uso: Counter = field(default_factory=Counter)
    # Quantas vezes cada assunto já caiu — o menos visto vai primeiro.
    vistos: Counter = field(default_factory=Counter)
    # Assuntos errados, do simulado mais recente para o mais antigo, sem repetir.
    errados: list[str] = field(default_factory=list)
    # Grupos (por nome) que apareceram no último simulado.
    grupos_ultimo: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Escolha:
    questao_id: uuid.UUID
    materia: str
    assunto: str
    revisao: bool


def _cotas(grupos: Sequence[cat.Grupo], vagas: int, disponivel: dict[str, int],
           ausentes: set[str], rng: random.Random) -> dict[str, int]:
    """Divide `vagas` entre os grupos pelo peso, sem passar do que cada um tem.

    Maior resto, com desempate a favor de quem ficou de fora da última prova.
    Um grupo que esgota devolve a sobra para os outros na volta seguinte.
    """
    cota = {g.nome: 0 for g in grupos}
    restantes = vagas
    while restantes > 0:
        abertos = [g for g in grupos if disponivel.get(g.nome, 0) > cota[g.nome]]
        if not abertos:
            break
        total = sum(g.peso for g in abertos)
        exato = {g.nome: restantes * g.peso / total for g in abertos}
        dados = 0
        for g in abertos:
            n = min(int(exato[g.nome]), disponivel[g.nome] - cota[g.nome])
            cota[g.nome] += n
            dados += n
        restantes -= dados
        if restantes <= 0:
            break
        ordem = sorted(
            (g for g in abertos if disponivel[g.nome] > cota[g.nome]),
            key=lambda g: -(exato[g.nome] - int(exato[g.nome])
                            + (0.5 if g.nome in ausentes else 0) + rng.random() * 0.01),
        )
        for g in ordem[:restantes]:
            cota[g.nome] += 1
            restantes -= 1
    return cota


class _Caderno:
    """As escolhas de uma matéria, com o critério de qual questão vem primeiro."""

    def __init__(self, cands: list[Candidata], hist: Historico, rng: random.Random):
        # O sorteio só desempata; quem manda é o critério de `pega`.
        self.cands = sorted(cands, key=lambda c: rng.random())
        self.hist = hist
        self.pegas: list[tuple[Candidata, bool]] = []
        self.usadas: set[uuid.UUID] = set()
        self.no_caderno: Counter = Counter()

    def pega(self, filtro, *, revisao: bool = False) -> Candidata | None:
        melhor = None
        for c in self.cands:
            if c.id in self.usadas or not filtro(c):
                continue
            # Questão inédita antes de tudo: repetida infla a nota. Depois,
            # assunto que ainda não está no caderno, e o menos visto.
            chave = (self.hist.uso[c.id], self.no_caderno[c.assunto],
                     self.hist.vistos[c.assunto])
            if melhor is None or chave < melhor[0]:
                melhor = (chave, c)
        if melhor is None:
            return None
        c = melhor[1]
        self.usadas.add(c.id)
        self.no_caderno[c.assunto] += 1
        self.pegas.append((c, revisao))
        return c


def _montar_materia(materia: cat.Materia, cands: list[Candidata], hist: Historico,
                    rng: random.Random) -> list[Escolha]:
    cad = _Caderno(cands, hist, rng)

    # 1. Os assuntos errados voltam — um de cada, até 30% das vagas.
    teto = math.ceil(materia.questoes * FRACAO_REVISAO)
    for assunto in hist.errados:
        if len(cad.pegas) >= teto:
            break
        if cat.ONDE.get(assunto, (None,))[0] is materia:
            cad.pega(lambda c, a=assunto: c.assunto == a, revisao=True)

    # 2. O resto, pelo peso da banca.
    grupo_de = {c.id: cat.ONDE[c.assunto][1].nome for c in cands}
    disponivel = Counter(grupo_de[c.id] for c in cands if c.id not in cad.usadas)
    ausentes = {g.nome for g in materia.grupos} - hist.grupos_ultimo
    cotas = _cotas(materia.grupos, materia.questoes - len(cad.pegas), disponivel,
                   ausentes, rng)
    for nome, n in cotas.items():
        for _ in range(n):
            cad.pega(lambda c, g=nome: grupo_de[c.id] == g)

    # Embaralha (a revisão não pode vir sempre no começo, senão o lugar
    # entrega o assunto) e junta as questões do mesmo texto de apoio na
    # posição da primeira delas — ler o texto duas vezes é tempo de prova.
    pegas = cad.pegas
    rng.shuffle(pegas)
    posicao: dict[object, int] = {}
    chave = []
    for i, (c, _) in enumerate(pegas):
        k = c.texto if c.texto else ("solta", i)
        posicao.setdefault(k, i)
        chave.append((posicao[k], i))
    return [
        Escolha(pegas[i][0].id, materia.chave, pegas[i][0].assunto, pegas[i][1])
        for i in sorted(range(len(pegas)), key=chave.__getitem__)
    ]


def montar(pool: dict[str, list[Candidata]], hist: Historico,
           rng: random.Random) -> list[Escolha]:
    """O caderno: matéria a matéria, na ordem e nas quantidades do edital."""
    caderno: list[Escolha] = []
    for materia in cat.MATERIAS:
        caderno.extend(_montar_materia(materia, pool.get(materia.chave, []), hist, rng))
    return caderno


# ── Leitura do banco ─────────────────────────────────────────────────────

async def _pool(session) -> dict[str, list[Candidata]]:
    """O estoque: questão etiquetada, de cinco alternativas, em estudo."""
    linhas = (await session.execute(
        select(Questao.id, Questao.assunto, Questao.texto_base)
        .where(Questao.assunto.is_not(None), Questao.formato != "certo_errado",
               _em_estudo())
    )).all()
    pool: dict[str, list[Candidata]] = defaultdict(list)
    for qid, assunto, texto in linhas:
        onde = cat.ONDE.get(assunto)
        if onde is None:  # rótulo que saiu do catálogo: fica fora, sem quebrar
            continue
        pool[onde[0].chave].append(Candidata(qid, assunto, texto))
    return pool


async def _historico(session) -> Historico:
    h = Historico()
    for qid, assunto in (await session.execute(
        select(SimuladoItem.questao_id, SimuladoItem.assunto)
    )).all():
        h.uso[qid] += 1
        h.vistos[assunto] += 1

    ultimos = (await session.scalars(
        select(Simulado).where(Simulado.estado == "finalizado")
        .order_by(Simulado.numero.desc()).limit(JANELA_ERROS)
    )).all()
    for i, s in enumerate(ultimos):
        erros = Counter(it.assunto for it in s.itens if not it.acertou)
        # Do mais errado para o menos, dentro de cada simulado.
        for assunto, _ in erros.most_common():
            if assunto not in h.errados:
                h.errados.append(assunto)
        if i == 0:
            h.grupos_ultimo = {
                cat.ONDE[it.assunto][1].nome for it in s.itens if it.assunto in cat.ONDE
            }
    return h


async def _pendentes(session) -> list[Reforco]:
    return list((await session.scalars(
        select(Reforco).where(Reforco.estado.in_(("aguardando_questoes", "pronto")))
        .order_by(Reforco.criado_em, Reforco.materia, Reforco.assunto)
    )).all())


# ── O que a tela pede ────────────────────────────────────────────────────

def _resumo_simulado(s: Simulado) -> dict:
    respondidas = sum(1 for it in s.itens if it.resposta)
    return {
        "id": str(s.id),
        "numero": s.numero,
        "estado": s.estado,
        "iniciado_em": s.iniciado_em,
        "finalizado_em": s.finalizado_em,
        "total": len(s.itens),
        "respondidas": respondidas,
        "acertos": s.acertos,
        "nota": float(s.nota) if s.nota is not None else None,
        "habilitado": (float(s.nota) >= NOTA_MINIMA) if s.nota is not None else None,
    }


# Um 'gerando' mais velho que isto, ou cujo processo já não existe, morreu sem
# avisar (máquina desligada, processo morto) — a tela mostra como erro, para o
# botão voltar a aparecer em vez de girar para sempre.
GERACAO_PRAZO = timedelta(minutes=40)


def _vivo(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _geracao(r: Reforco) -> tuple[str | None, str | None]:
    if r.geracao_estado != "gerando":
        return r.geracao_estado, r.geracao_erro
    velho = r.geracao_em is not None and datetime.now(UTC) - r.geracao_em > GERACAO_PRAZO
    if velho or (r.geracao_pid and not _vivo(r.geracao_pid)):
        return "erro", "A geração foi interrompida antes de terminar. Tente de novo."
    return "gerando", None


def _resumo_reforco(r: Reforco) -> dict:
    respondidas = sum(1 for it in r.itens if it.resposta)
    geracao, erro = _geracao(r)
    materia = cat.POR_CHAVE[r.materia]
    onde = cat.ONDE.get(r.assunto)
    return {
        "id": str(r.id),
        "simulado_id": str(r.simulado_id),
        "materia": r.materia,
        "materia_nome": materia.nome,
        "grupo": onde[1].nome if onde else None,
        "assunto": r.assunto,
        "rodada": r.rodada,
        "estado": r.estado,
        "erros_no_simulado": r.erros_no_simulado,
        "total": len(r.itens),
        "respondidas": respondidas,
        "acertos": r.acertos,
        "minimo": math.ceil(QUESTOES_POR_REFORCO * APROVACAO_REFORCO),
        "geracao": geracao,
        "geracao_em": r.geracao_em,
        "geracao_erro": erro,
    }


async def estado() -> dict:
    """Tudo que a página de entrada precisa: onde estou no ciclo."""
    async with get_session() as s:
        andamento = await s.scalar(select(Simulado).where(Simulado.estado == "em_andamento"))
        pendentes = await _pendentes(s)
        historico = (await s.scalars(
            select(Simulado).where(Simulado.estado == "finalizado")
            .order_by(Simulado.numero.desc())
        )).all()
        pool = await _pool(s)
        reforcos_feitos = (await s.scalars(
            select(Reforco).where(Reforco.estado.in_(("aprovado", "reprovado")))
            .order_by(Reforco.concluido_em.desc()).limit(30)
        )).all()
    estoque = {m.chave: len(pool.get(m.chave, [])) for m in cat.MATERIAS}
    return {
        "liberado": andamento is None and not pendentes,
        "em_andamento": _resumo_simulado(andamento) if andamento else None,
        "reforcos_pendentes": [_resumo_reforco(r) for r in pendentes],
        "reforcos_concluidos": [_resumo_reforco(r) for r in reforcos_feitos],
        "historico": [_resumo_simulado(x) for x in historico],
        "materias": [
            {"chave": m.chave, "nome": m.nome, "questoes": m.questoes,
             "estoque": estoque[m.chave]}
            for m in cat.MATERIAS
        ],
        "nota_minima": NOTA_MINIMA,
    }


async def iniciar(*, semente: int | None = None) -> Simulado:
    """Monta e grava o próximo simulado. Devolve o em andamento, se houver."""
    async with get_session() as s:
        andamento = await s.scalar(select(Simulado).where(Simulado.estado == "em_andamento"))
        if andamento is not None:
            return andamento
        pendentes = await _pendentes(s)
        if pendentes:
            nomes = ", ".join(sorted({r.assunto for r in pendentes}))
            raise SimuladoBloqueado(
                f"{len(pendentes)} reforço(s) pendente(s) antes do próximo simulado: {nomes}"
            )
        caderno = montar(await _pool(s), await _historico(s), random.Random(semente))
        if not caderno:
            raise EstudoErro("O estoque está vazio: nenhuma questão tem assunto etiquetado.")
        numero = (await s.scalar(select(func.max(Simulado.numero)))) or 0
        sim = Simulado(numero=numero + 1, estado="em_andamento")
        s.add(sim)
        await s.flush()
        for i, e in enumerate(caderno, 1):
            s.add(SimuladoItem(simulado_id=sim.id, questao_id=e.questao_id, ordem=i,
                               materia=e.materia, assunto=e.assunto, revisao=e.revisao))
        await s.commit()
        logger.info(f"simulado nº {sim.numero} montado: {len(caderno)} questões")
        return await s.get(Simulado, sim.id, populate_existing=True)


async def _carregar(session, simulado_id: uuid.UUID) -> Simulado:
    sim = await session.get(Simulado, simulado_id)
    if sim is None:
        raise SimuladoNaoEncontrado(str(simulado_id))
    return sim


async def _questoes(session, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, Questao]:
    qs = (await session.scalars(select(Questao).where(Questao.id.in_(ids)))).unique().all()
    return {q.id: q for q in qs}


def _questao_json(q: Questao, *, com_gabarito: bool) -> dict:
    return {
        "id": str(q.id),
        "formato": q.formato,
        "comando": q.comando,
        "enunciado": q.enunciado,
        "texto_base": q.texto_base,
        "texto_base_fonte": q.texto_base_fonte,
        "codigo": q.codigo,
        "linguagem": q.linguagem,
        "alternativas": q.alternativas or [],
        "afirmacoes": q.afirmacoes or [],
        "imagem": q.imagem,
        "imagem_alt": q.imagem_alt,
        "banca": q.banca.nome if q.banca else None,
        "origem": q.origem,
        # Durante a prova, nem gabarito nem explicação viajam: a diferença
        # entre "eu sabia" e "eu vi" é a nota.
        "gabarito": q.gabarito if com_gabarito else None,
        "explicacao": q.explicacao if com_gabarito else None,
    }


async def obter(simulado_id: uuid.UUID) -> dict:
    async with get_session() as s:
        sim = await _carregar(s, simulado_id)
        qs = await _questoes(s, [it.questao_id for it in sim.itens])
    fim = sim.estado == "finalizado"
    return {
        **_resumo_simulado(sim),
        "itens": [
            {
                "ordem": it.ordem,
                "materia": it.materia,
                "materia_nome": cat.POR_CHAVE[it.materia].nome,
                # O assunto só aparece depois: dizer "Triggers" no topo da
                # questão é meia resposta.
                "assunto": it.assunto if fim else None,
                "revisao": it.revisao if fim else None,
                "resposta": it.resposta,
                "acertou": it.acertou,
                "questao": _questao_json(qs[it.questao_id], com_gabarito=fim),
            }
            for it in sim.itens
        ],
    }


async def marcar(simulado_id: uuid.UUID, ordem: int, resposta: str | None) -> dict:
    """Grava (ou apaga, com `None`) a alternativa marcada. Sem correção."""
    async with get_session() as s:
        sim = await _carregar(s, simulado_id)
        if sim.estado != "em_andamento":
            raise EstadoInvalido("O simulado já foi entregue.")
        item = next((it for it in sim.itens if it.ordem == ordem), None)
        if item is None:
            raise EstadoInvalido(f"O simulado não tem a questão {ordem}.")
        if resposta is not None:
            q = await s.get(Questao, item.questao_id)
            letras = {a["letra"] for a in (q.alternativas or [])}
            if resposta not in letras:
                raise EstadoInvalido(f"'{resposta}' não é alternativa desta questão.")
        item.resposta = resposta
        item.respondida_em = datetime.now(UTC) if resposta else None
        await s.commit()
        respondidas = sum(1 for it in sim.itens if it.resposta)
    return {"ordem": ordem, "resposta": resposta, "respondidas": respondidas}


async def finalizar(simulado_id: uuid.UUID) -> dict:
    """Entrega a prova: corrige, dá a nota e abre um reforço por assunto errado."""
    async with get_session() as s:
        sim = await _carregar(s, simulado_id)
        if sim.estado != "em_andamento":
            raise EstadoInvalido("O simulado já foi entregue.")
        qs = await _questoes(s, [it.questao_id for it in sim.itens])
        erros: Counter = Counter()
        materia_de: dict[str, str] = {}
        for it in sim.itens:
            # Em branco é erro: na folha de respostas, não marcar não pontua.
            it.acertou = it.resposta is not None and it.resposta == qs[it.questao_id].gabarito
            if not it.acertou:
                erros[it.assunto] += 1
                materia_de[it.assunto] = it.materia
        acertos = sum(1 for it in sim.itens if it.acertou)
        sim.acertos = acertos
        sim.total = len(sim.itens)
        sim.nota = round(100 / sim.total * acertos, 2) if sim.total else 0
        sim.estado = "finalizado"
        sim.finalizado_em = datetime.now(UTC)
        for assunto, n in erros.items():
            s.add(Reforco(simulado_id=sim.id, materia=materia_de[assunto], assunto=assunto,
                          rodada=1, estado="aguardando_questoes", erros_no_simulado=n))
        await s.commit()
    return await resultado(simulado_id)


async def resultado(simulado_id: uuid.UUID) -> dict:
    """A correção: nota do edital, matéria a matéria, e o erro com nome."""
    dados = await obter(simulado_id)
    if dados["estado"] != "finalizado":
        raise EstadoInvalido("O simulado ainda não foi entregue.")
    async with get_session() as s:
        reforcos = (await s.scalars(
            select(Reforco).where(Reforco.simulado_id == simulado_id)
            .order_by(Reforco.materia, Reforco.assunto, Reforco.rodada)
        )).all()

    por_materia = []
    for m in cat.MATERIAS:
        itens = [it for it in dados["itens"] if it["materia"] == m.chave]
        if not itens:
            continue
        assuntos: dict[str, dict] = {}
        for it in itens:
            a = assuntos.setdefault(it["assunto"], {
                "assunto": it["assunto"],
                "grupo": cat.ONDE[it["assunto"]][1].nome if it["assunto"] in cat.ONDE else None,
                "total": 0, "erros": 0,
            })
            a["total"] += 1
            a["erros"] += 0 if it["acertou"] else 1
        acertos = sum(1 for it in itens if it["acertou"])
        por_materia.append({
            "chave": m.chave,
            "nome": m.nome,
            "acertos": acertos,
            "total": len(itens),
            "percentual": round(100 * acertos / len(itens), 1),
            "assuntos_errados": sorted(
                (a for a in assuntos.values() if a["erros"]),
                key=lambda a: (-a["erros"], a["assunto"]),
            ),
        })
    return {
        **{k: v for k, v in dados.items() if k != "itens"},
        "nota_minima": NOTA_MINIMA,
        "por_materia": por_materia,
        "erros": [it for it in dados["itens"] if not it["acertou"]],
        "reforcos": [_resumo_reforco(r) for r in reforcos],
    }


# ── O reforço ────────────────────────────────────────────────────────────

async def _carregar_reforco(session, reforco_id: uuid.UUID) -> Reforco:
    r = await session.get(Reforco, reforco_id)
    if r is None:
        raise ReforcoNaoEncontrado(str(reforco_id))
    return r


async def obter_reforco(reforco_id: uuid.UUID) -> dict:
    async with get_session() as s:
        r = await _carregar_reforco(s, reforco_id)
        qs = await _questoes(s, [it.questao_id for it in r.itens])
    return {
        **_resumo_reforco(r),
        "itens": [
            {
                "ordem": it.ordem,
                "resposta": it.resposta,
                "acertou": it.acertou,
                # Aqui a correção é imediata: a respondida já mostra o porquê.
                "questao": _questao_json(qs[it.questao_id], com_gabarito=it.resposta is not None),
            }
            for it in r.itens
        ],
    }


async def responder_reforco(reforco_id: uuid.UUID, ordem: int, resposta: str) -> dict:
    """Corrige na hora. Na última das 5, fecha o reforço: passa ou abre outra rodada."""
    async with get_session() as s:
        r = await _carregar_reforco(s, reforco_id)
        if r.estado != "pronto":
            raise EstadoInvalido(
                "Este reforço ainda não tem questões." if r.estado == "aguardando_questoes"
                else "Este reforço já foi concluído."
            )
        item = next((it for it in r.itens if it.ordem == ordem), None)
        if item is None:
            raise EstadoInvalido(f"O reforço não tem a questão {ordem}.")
        if item.resposta is not None:
            raise EstadoInvalido("Esta questão do reforço já foi respondida.")
        q = await s.get(Questao, item.questao_id)
        if resposta not in {a["letra"] for a in (q.alternativas or [])}:
            raise EstadoInvalido(f"'{resposta}' não é alternativa desta questão.")
        item.resposta = resposta
        item.acertou = resposta == q.gabarito
        item.respondida_em = datetime.now(UTC)

        proxima = None
        if all(it.resposta is not None for it in r.itens):
            r.acertos = sum(1 for it in r.itens if it.acertou)
            r.total = len(r.itens)
            r.concluido_em = datetime.now(UTC)
            r.estado = "aprovado" if r.acertos / r.total >= APROVACAO_REFORCO else "reprovado"
            if r.estado == "reprovado":
                proxima = Reforco(simulado_id=r.simulado_id, materia=r.materia,
                                  assunto=r.assunto, rodada=r.rodada + 1,
                                  estado="aguardando_questoes",
                                  erros_no_simulado=r.erros_no_simulado)
                s.add(proxima)
        await s.commit()
        out = {
            "ordem": ordem,
            "acertou": item.acertou,
            "gabarito": q.gabarito,
            "explicacao": q.explicacao,
            "reforco": _resumo_reforco(r),
        }
    return out


async def vincular_reforco(reforco_id: uuid.UUID, questao_ids: Sequence[uuid.UUID]) -> Reforco:
    """Põe as questões escritas no reforço e o deixa pronto para responder."""
    async with get_session() as s:
        r = await _carregar_reforco(s, reforco_id)
        if r.estado != "aguardando_questoes":
            raise EstadoInvalido(f"O reforço de '{r.assunto}' está {r.estado}.")
        for i, qid in enumerate(questao_ids, 1):
            s.add(ReforcoItem(reforco_id=r.id, questao_id=qid, ordem=i))
        r.estado = "pronto"
        await s.commit()
        return r


# ── A geração pelo botão ─────────────────────────────────────────────────

GERADOR = BASE_DIR / "scripts" / "simulado" / "gerar_reforco.py"


def _disparar_processo(ids: list[str]) -> int:
    """Sobe o gerador desligado da API: ele leva minutos, a requisição não espera.

    `start_new_session` tira o processo do grupo do uvicorn — reiniciar a API
    no meio não mata a escrita das questões.
    """
    LOG = BASE_DIR / "logs" / "reforco"
    LOG.mkdir(parents=True, exist_ok=True)
    with (LOG / "disparos.log").open("a", encoding="utf-8") as saida:
        proc = subprocess.Popen(
            [sys.executable, str(GERADOR), *ids], cwd=BASE_DIR,
            stdin=subprocess.DEVNULL, stdout=saida, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


async def gerar(reforco_ids: Sequence[uuid.UUID]) -> list[dict]:
    """Marca como 'gerando' e dispara. Recusa o que não espera questões ou já gera."""
    async with get_session() as s:
        alvos = []
        for rid in reforco_ids:
            r = await _carregar_reforco(s, rid)
            if r.estado != "aguardando_questoes":
                raise EstadoInvalido(f"O reforço de '{r.assunto}' já tem questões.")
            if _geracao(r)[0] == "gerando":
                continue  # clique duplo: o processo que já roda basta
            alvos.append(r)
        if not alvos:
            return []
        agora = datetime.now(UTC)
        for r in alvos:
            r.geracao_estado, r.geracao_em, r.geracao_erro = "gerando", agora, None
        await s.commit()
        pid = _disparar_processo([str(r.id) for r in alvos])
        for r in alvos:
            r.geracao_pid = pid
        await s.commit()
        logger.info(f"reforço: geração disparada para {len(alvos)} assunto(s), pid {pid}")
        return [_resumo_reforco(r) for r in alvos]


async def gerar_pendentes() -> list[dict]:
    """O 'Gerar todos': todo reforço esperando questões que não está sendo gerado."""
    async with get_session() as s:
        ids = [r.id for r in (await s.scalars(
            select(Reforco).where(Reforco.estado == "aguardando_questoes"))).all()
            if _geracao(r)[0] != "gerando"]
    return await gerar(ids) if ids else []


async def para_escrever() -> list[dict]:
    """Os reforços sem questão, com o erro que os gerou — o insumo de quem escreve.

    Na rodada 1 o insumo é a questão errada no simulado; da 2 em diante entram
    também as erradas da rodada anterior, porque é ali que está o que o
    reforço anterior não resolveu.
    """
    async with get_session() as s:
        pendentes = (await s.scalars(
            select(Reforco).where(Reforco.estado == "aguardando_questoes")
            .order_by(Reforco.materia, Reforco.assunto)
        )).all()
        saida = []
        for r in pendentes:
            sim = await s.get(Simulado, r.simulado_id)
            errados = [it for it in sim.itens if it.assunto == r.assunto and not it.acertou]
            anteriores = (await s.scalars(
                select(Reforco).where(Reforco.simulado_id == r.simulado_id,
                                      Reforco.assunto == r.assunto,
                                      Reforco.rodada < r.rodada)
            )).all()
            # (rodada, item) e não `item.reforco`: a relação reversa carregaria
            # preguiçosa, e preguiça em sessão assíncrona é exceção.
            errados_reforco = [(a.rodada, it) for a in anteriores for it in a.itens
                               if not it.acertou]
            ids = [it.questao_id for it in errados] + [it.questao_id for _, it in errados_reforco]
            qs = await _questoes(s, ids)
            ja_usadas = [q.origem for a in anteriores for it in a.itens
                         if (q := await s.get(Questao, it.questao_id)) is not None]
            saida.append({
                "reforco_id": str(r.id),
                "simulado": sim.numero,
                "materia": r.materia,
                "assunto": r.assunto,
                "rodada": r.rodada,
                "erros": [
                    {"onde": f"simulado nº {sim.numero}, questão {it.ordem}",
                     "marcou": it.resposta, "questao": qs[it.questao_id]}
                    for it in errados
                ] + [
                    {"onde": f"reforço rodada {rodada}", "marcou": it.resposta,
                     "questao": qs[it.questao_id]}
                    for rodada, it in errados_reforco
                ],
                "origens_ja_usadas": ja_usadas,
            })
    return saida
