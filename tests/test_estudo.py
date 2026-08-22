"""Agendamento e resposta — a parte que eu não quero descobrir quebrada na prova.

O grosso testa `app.estudo.agendamento`, que é função pura: a data de hoje entra
por parâmetro, então dá para verificar o comportamento de seis meses sem esperar
seis meses. O resto exercita o serviço contra o Postgres de verdade, porque o
que interessa ali é o que fica gravado — data e acerto — e isso é banco.
"""
from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db.models.estudo.agenda import (
    INTERVALO_ACERTO,
    INTERVALO_ADIAR,
    INTERVALO_ERRO,
    INTERVALO_MAX,
    Agenda,
    Tentativa,
)
from app.db.models.estudo.questao import Modulo, Questao, Topico
from app.db.session import get_session
from app.estudo import agendamento, servico

HOJE = date(2026, 8, 21)


# ── A função pura ────────────────────────────────────────────────────────

def test_questao_nova_vence_hoje():
    """Cadastrar e só ver semana que vem é o jeito de parar de cadastrar."""
    e = agendamento.inicial(HOJE)
    assert e.proxima_em == HOJE
    assert e.estado == "nova"


def test_primeiro_acerto_da_sete_dias():
    e = agendamento.proximo_estado(agendamento.inicial(HOJE), acertou=True, hoje=HOJE)
    assert e.intervalo_dias == INTERVALO_ACERTO
    assert e.proxima_em == HOJE + timedelta(days=INTERVALO_ACERTO)
    assert e.total_acertos == 1


def test_erro_devolve_em_dois_dias():
    e = agendamento.proximo_estado(agendamento.inicial(HOJE), acertou=False, hoje=HOJE)
    assert e.intervalo_dias == INTERVALO_ERRO
    assert e.proxima_em == HOJE + timedelta(days=INTERVALO_ERRO)
    assert e.total_erros == 1


def test_intervalo_cresce_a_cada_acerto_seguido():
    e = agendamento.inicial(HOJE)
    intervalos = []
    for _ in range(5):
        e = agendamento.proximo_estado(e, acertou=True, hoje=e.proxima_em)
        intervalos.append(e.intervalo_dias)
    assert intervalos == sorted(intervalos), "o intervalo tem que crescer"
    assert intervalos[0] == INTERVALO_ACERTO
    assert intervalos[-1] <= INTERVALO_MAX


def test_intervalo_tem_teto():
    """Sem teto, seis acertos seguidos sumiriam com a questão por dois anos."""
    e = agendamento.inicial(HOJE)
    for _ in range(20):
        e = agendamento.proximo_estado(e, acertou=True, hoje=e.proxima_em)
    assert e.intervalo_dias == INTERVALO_MAX


def test_errar_zera_a_sequencia_e_nao_recua_um_degrau():
    """Quem errou depois de 35 dias não sabia há 35 dias — sabia há 7."""
    e = agendamento.inicial(HOJE)
    for _ in range(3):
        e = agendamento.proximo_estado(e, acertou=True, hoje=e.proxima_em)
    assert e.intervalo_dias > INTERVALO_ACERTO
    assert e.acertos_seguidos == 3

    e = agendamento.proximo_estado(e, acertou=False, hoje=e.proxima_em)
    assert e.intervalo_dias == INTERVALO_ERRO
    assert e.acertos_seguidos == 0
    assert e.estado == "aprendendo"


def test_tres_acertos_seguidos_dominam():
    e = agendamento.inicial(HOJE)
    for n in range(3):
        e = agendamento.proximo_estado(e, acertou=True, hoje=e.proxima_em)
        esperado = "dominada" if n == 2 else "aprendendo"
        assert e.estado == esperado


def test_adiar_nao_conta_como_acerto():
    """"Está fácil" não é "respondi certo" — a taxa de acerto mede resposta."""
    e = agendamento.proximo_estado(agendamento.inicial(HOJE), acertou=True, hoje=HOJE)
    antes = (e.total_acertos, e.total_erros, e.acertos_seguidos)

    a = agendamento.adiada(e, hoje=HOJE)
    assert (a.total_acertos, a.total_erros, a.acertos_seguidos) == antes
    assert a.estado == "adiada"
    assert a.proxima_em == HOJE + timedelta(days=INTERVALO_ADIAR)


# ── O serviço, contra o banco ────────────────────────────────────────────

async def _semear(*, gabarito: str = "C", formato: str = "certo_errado") -> Questao:
    async with get_session() as s:
        modulo = Modulo(nome="Matemática e raciocínio lógico", trilha="concurso")
        s.add(modulo)
        await s.flush()
        topico = Topico(modulo_id=modulo.id, nome="Lógica proposicional")
        s.add(topico)
        await s.flush()
        await s.commit()
        topico_id = topico.id

    return await servico.criar_questao(
        {
            "topico_id": topico_id,
            "formato": formato,
            "enunciado": "A negação de “se p então q” é “p e não q”.",
            "alternativas": [
                {"letra": letra, "texto": letra} for letra in "ABCDE"
            ]
            if formato != "certo_errado"
            else [],
            "afirmacoes": [],
            "gabarito": gabarito,
            "dificuldade": 2,
        }
    )


async def test_responder_grava_data_e_acerto():
    """O que o histórico precisa guardar, e é dele que sai a próxima data."""
    q = await _semear(gabarito="C")

    r = await servico.responder(q.id, resposta="C")
    assert r["acertou"] is True
    assert r["proxima_em"] == servico.hoje() + timedelta(days=INTERVALO_ACERTO)

    async with get_session() as s:
        t = (await s.scalars(select(Tentativa))).one()
        assert t.acertou is True
        assert t.resposta == "C"
        # O carimbo é `timestamptz` em UTC — comparar `.date()` dele direto com
        # o "hoje" do estudo dá errado das 21h à meia-noite de Brasília. É o
        # fuso que faz a ponte, e este assert existe para não perder isso de novo.
        local = t.respondida_em.astimezone(ZoneInfo(settings.timezone)).date()
        assert local == servico.hoje()


def test_hoje_segue_o_fuso_do_estudante_e_nao_utc():
    """Às 21h de Brasília o UTC já virou. A fila do dia não pode virar junto.

    Com `datetime.now(UTC).date()` a tela dizia "16 voltam hoje" às 20h59 e
    "amanhã" às 21h01, sem eu ter tocado em nada.
    """
    from datetime import UTC, datetime

    local = datetime.now(ZoneInfo(settings.timezone)).date()
    assert servico.hoje() == local
    # E o fuso configurado é mesmo um que difere de UTC parte do dia.
    agora = datetime.now(UTC)
    assert agora.astimezone(ZoneInfo(settings.timezone)).utcoffset().total_seconds() != 0


async def test_resposta_errada_agenda_para_dois_dias():
    q = await _semear(gabarito="C")
    r = await servico.responder(q.id, resposta="E")
    assert r["acertou"] is False
    assert r["proxima_em"] == servico.hoje() + timedelta(days=INTERVALO_ERRO)


async def test_so_a_primeira_tentativa_reagenda():
    """A tela deixa tentar de novo. Acertar na segunda não é acertar.

    Se as duas contassem igual, o intervalo cresceria com base numa memória que
    não existe — a questão sumiria por 35 dias por causa de um chute que deu
    certo na repescagem.
    """
    q = await _semear(gabarito="C")

    primeira = await servico.responder(q.id, resposta="E", tentativa_n=1)
    assert primeira["reagendou"] is True
    agendada = primeira["proxima_em"]

    segunda = await servico.responder(q.id, resposta="C", tentativa_n=2)
    assert segunda["acertou"] is True
    assert segunda["reagendou"] is False
    assert segunda["proxima_em"] == agendada, "a segunda tentativa não pode reagendar"

    # As duas ficam no log, mesmo assim.
    async with get_session() as s:
        assert await s.scalar(select(func.count(Tentativa.id))) == 2


async def test_adiar_nao_registra_tentativa():
    q = await _semear()
    await servico.adiar(q.id)
    async with get_session() as s:
        assert await s.scalar(select(func.count(Tentativa.id))) == 0
        agenda = (await s.scalars(select(Agenda))).one()
        assert agenda.estado == "adiada"


async def test_resposta_invalida_para_o_formato():
    q = await _semear(gabarito="C", formato="certo_errado")
    with pytest.raises(servico.RespostaInvalida):
        await servico.responder(q.id, resposta="B")


async def test_fila_traz_as_erradas_primeiro():
    """Deixar as erradas para o fim da sessão é deixá-las para o cansaço."""
    facil = await _semear(gabarito="C")
    async with get_session() as s:
        topico_id = (await s.scalars(select(Topico))).one().id

    dificil = await servico.criar_questao(
        {
            "topico_id": topico_id,
            "formato": "certo_errado",
            "enunciado": "Contrapositiva preserva o valor lógico.",
            "alternativas": [],
            "afirmacoes": [],
            "gabarito": "C",
            "dificuldade": 2,
        }
    )
    # Erra a segunda e volta as duas para hoje, para a ordem depender do erro.
    await servico.responder(dificil.id, resposta="E")
    async with get_session() as s:
        for a in (await s.scalars(select(Agenda))).all():
            a.proxima_em = servico.hoje()
        await s.commit()

    fila = await servico.fila()
    assert [q.id for q in fila][0] == dificil.id
    assert facil.id in [q.id for q in fila]


async def test_fila_nao_traz_o_que_nao_venceu():
    q = await _semear(gabarito="C")
    await servico.responder(q.id, resposta="C")  # vai para daqui a 7 dias
    assert await servico.fila() == []


async def test_todas_ignora_o_agendamento():
    """Abrir um tópico e não poder responder nada é a tela dizendo não."""
    q = await _semear(gabarito="C")
    await servico.responder(q.id, resposta="C")
    assert await servico.fila() == []
    assert [x.id for x in await servico.fila(todas=True)] == [q.id]


async def test_questao_avulsa_entra_mesmo_fora_da_data():
    q = await _semear(gabarito="C")
    await servico.responder(q.id, resposta="C")
    assert [x.id for x in await servico.fila(questao_id=q.id)] == [q.id]


async def test_responder_fora_da_data_conta_e_reagenda():
    """Treinar adiantado não é ensaio: entra no log e mexe no intervalo."""
    q = await _semear(gabarito="C")
    await servico.responder(q.id, resposta="C")

    r = await servico.responder(q.id, resposta="E")
    assert r["reagendou"] is True
    assert r["proxima_em"] == servico.hoje() + timedelta(days=INTERVALO_ERRO)
    async with get_session() as s:
        assert await s.scalar(select(func.count(Tentativa.id))) == 2


async def test_resumo_conta_o_que_vence_hoje():
    await _semear()
    r = await servico.resumo()
    assert r["total"] == 1
    assert r["hoje"] == 1
    assert r["novas"] == 1
    assert r["respondidas_hoje"] == 0


async def test_atualizar_explicacao_nao_mexe_no_agendamento():
    """O acervo vem dos PDFs sem justificativa; a explicação entra depois."""
    q = await _semear(gabarito="C")
    await servico.responder(q.id, resposta="C")

    async with get_session() as s:
        antes = (await s.scalars(select(Agenda))).one()
        proxima, acertos = antes.proxima_em, antes.total_acertos

    atualizada = await servico.atualizar_questao(
        q.id, {"explicacao": "A negação de p → q é p ∧ ¬q."}
    )
    assert atualizada.explicacao.startswith("A negação")

    async with get_session() as s:
        depois = (await s.scalars(select(Agenda))).one()
        assert (depois.proxima_em, depois.total_acertos) == (proxima, acertos)


# ── Módulos e tópicos ────────────────────────────────────────────────────

async def test_cria_modulo_e_topico():
    m = await servico.criar_modulo(nome="Estatística", trilha="especializacao")
    t = await servico.criar_topico(modulo_id=m.id, nome="Bayes")
    assert t.modulo_id == m.id

    mods = await servico.modulos()
    assert [x["nome"] for x in mods] == ["Estatística"]
    assert mods[0]["trilha"] == "especializacao"
    assert [x["nome"] for x in mods[0]["topicos"]] == ["Bayes"]
    # Módulo novo nasce vazio, e a tela precisa saber disso sem quebrar.
    assert mods[0]["questoes"] == 0
    assert mods[0]["proxima_em"] is None


async def test_modulo_com_nome_repetido_e_recusado():
    await servico.criar_modulo(nome="Estatística")
    with pytest.raises(servico.NomeEmUso):
        # Diferença de caixa é o mesmo módulo — senão a sidebar mostra dois.
        await servico.criar_modulo(nome="estatística")


async def test_topico_repetido_no_mesmo_modulo_e_recusado():
    m = await servico.criar_modulo(nome="Estatística")
    outro = await servico.criar_modulo(nome="Banco de dados")
    await servico.criar_topico(modulo_id=m.id, nome="Bayes")
    with pytest.raises(servico.NomeEmUso):
        await servico.criar_topico(modulo_id=m.id, nome="bayes")
    # O mesmo nome noutro módulo é legítimo: "Índices" existe em BD e em livros.
    assert await servico.criar_topico(modulo_id=outro.id, nome="Bayes")


async def test_trilha_invalida_e_recusada():
    with pytest.raises(servico.RespostaInvalida):
        await servico.criar_modulo(nome="X", trilha="hobby")


async def test_renomear_modulo():
    m = await servico.criar_modulo(nome="Estatistica")
    await servico.atualizar_modulo(m.id, {"nome": "Estatística"})
    assert [x["nome"] for x in await servico.modulos()] == ["Estatística"]


async def test_apagar_modulo_vazio():
    m = await servico.criar_modulo(nome="Descartável")
    assert await servico.apagar_modulo(m.id) == 0
    assert await servico.modulos() == []


async def test_apagar_modulo_com_questoes_e_recusado():
    """Meses de repetição espaçada são a única coisa aqui que não se refaz."""
    await _semear()
    async with get_session() as s:
        modulo_id = (await s.scalars(select(Modulo))).one().id

    with pytest.raises(servico.NaoVazio) as erro:
        await servico.apagar_modulo(modulo_id)
    assert "1 questão" in str(erro.value)

    # Com `forcar`, vai — e a conta volta para a tela poder dizer o que sumiu.
    assert await servico.apagar_modulo(modulo_id, forcar=True) == 1
    async with get_session() as s:
        assert await s.scalar(select(func.count(Questao.id))) == 0
        assert await s.scalar(select(func.count(Tentativa.id))) == 0


async def test_apagar_topico_com_questoes_e_recusado():
    await _semear()
    async with get_session() as s:
        topico_id = (await s.scalars(select(Topico))).one().id
    with pytest.raises(servico.NaoVazio):
        await servico.apagar_topico(topico_id)
    assert await servico.apagar_topico(topico_id, forcar=True) == 1
