"""Conversas-tipo dos atendentes — o conjunto de teste antes do bot.

Duas perguntas: o conjunto está inteiro (100+, todos os nichos, toda variação
aponta para uma base que existe) e **a resposta de referência cumpre as regras
que ela mesma ensina**. Uma referência que diz "garanto" ou passa preço de
dentista treinaria o bot no erro. As mesmas funções vão rodar sobre as
respostas do bot quando ele existir.
"""
from __future__ import annotations

from collections import Counter

import pytest

from app.comercial.conversas import (
    Atendente,
    Conversa,
    Nicho,
    Regra,
    carregar,
    dado_pessoal,
    violacoes,
)
from app.comercial.funil import Etapa, Temperatura, temperatura

CONVERSAS = carregar()
POR_ID = {c.id: c for c in CONVERSAS}

# As 42 do 1.2.7-conversas-tipo.md: 10 por nicho do produto e 12 do bot próprio.
BASES = (
    [f"C{i:02d}" for i in range(1, 11)]
    + [f"A{i:02d}" for i in range(1, 11)]
    + [f"I{i:02d}" for i in range(1, 11)]
    + [f"P{i:02d}" for i in range(1, 13)]
)
PERFIS = {"C-1", "C-2", "C-3", "A-1", "A-2", "I-1", "I-2", "I-3"}


# ── O conjunto está inteiro ──────────────────────────────────────────────

def test_pelo_menos_cem_conversas():
    assert len(CONVERSAS) >= 100


def test_ids_unicos():
    repetidos = [i for i, n in Counter(c.id for c in CONVERSAS).items() if n > 1]
    assert not repetidos


def test_todas_as_bases_do_documento_estao_no_conjunto():
    """O .md e o JSON não podem divergir: as 42 bases existem aqui."""
    faltando = [b for b in BASES if b not in POR_ID]
    assert not faltando
    assert all(not POR_ID[b].sintetica for b in BASES)


def test_variacao_aponta_para_base_do_mesmo_atendente():
    for c in CONVERSAS:
        if not c.sintetica:
            continue
        base = POR_ID.get(c.variacao_de)
        assert base is not None, f"{c.id}: base {c.variacao_de} não existe"
        assert not base.sintetica, f"{c.id}: variação de variação"
        assert c.id.startswith(base.id + "-v"), c.id
        assert c.atendente is base.atendente, c.id


def test_cada_atendente_e_nicho_tem_volume():
    """Nenhum nicho fica com meia dúzia de casos enquanto outro tem trinta."""
    produto = Counter(c.nicho for c in CONVERSAS if c.atendente is Atendente.CLIENTE)
    for nicho in Nicho:
        assert produto[nicho] >= 20, nicho
    assert sum(c.atendente is Atendente.PROPRIO for c in CONVERSAS) >= 20


def test_toda_base_tem_ao_menos_uma_variacao():
    variadas = {c.variacao_de for c in CONVERSAS if c.sintetica}
    assert not [b for b in BASES if b not in variadas]


def test_perfil_existe_no_1_2_7():
    assert not [c.id for c in CONVERSAS if c.perfil and c.perfil not in PERFIS]


def test_caso_de_desvio_e_insistencia_existem():
    """Robustez: tentar tirar o atendente da regra precisa estar testado."""
    tipos = Counter(c.tipo_variacao for c in CONVERSAS if c.sintetica)
    assert tipos["desvio"] >= 8
    assert tipos["insistencia"] >= 4


# ── A referência cumpre as regras ────────────────────────────────────────

@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda c: c.id)
def test_referencia_nao_quebra_regra(conversa: Conversa):
    assert violacoes(conversa) == []


@pytest.mark.parametrize("conversa", CONVERSAS, ids=lambda c: c.id)
def test_sem_dado_pessoal(conversa: Conversa):
    """Nome inventado passa; CPF, telefone e e-mail só como `{placeholder}`."""
    assert dado_pessoal(conversa) == []


def test_dentista_nunca_pode_falar_preco():
    dentistas = [c for c in CONVERSAS if c.config.get("profissao") == "dentista"]
    assert dentistas
    assert all(Regra.FALAR_PRECO in c.regras() for c in dentistas)


def test_escritorio_nunca_usa_vocabulario_de_consumo():
    escritorios = [c for c in CONVERSAS if c.nicho is Nicho.ADVOCACIA]
    assert all(Regra.VOCABULARIO_CONSUMO in c.regras() for c in escritorios)


# ── As regras pegam o erro (senão o teste acima não prova nada) ──────────

def test_violacoes_pega_promessa_em_resposta_do_bot():
    c = POR_ID["A05"]
    erros = violacoes(c, ["Com certeza vai dar certo, garanto!"])
    assert any("prometer" in e for e in erros)


def test_violacoes_pega_preco_de_dentista():
    erros = violacoes(POR_ID["C05"], ["O clareamento custa R$ 800."])
    assert any("falar_preco" in e for e in erros)


def test_violacoes_pega_vocabulario_de_consumo_com_escritorio():
    erros = violacoes(POR_ID["P02"], ["Seu lead vai entrar no funil."])
    assert any("vocabulario_consumo" in e for e in erros)


def test_violacoes_pega_mensagem_longa():
    erros = violacoes(POR_ID["C01"], ["a\nb\nc\nd"])
    assert any("4 linhas" in e for e in erros)


def test_violacoes_pega_bot_fingindo_ser_o_pablo():
    erros = violacoes(POR_ID["P11"], ["Não, aqui é o Pablo mesmo."])
    assert any("fingir_humano" in e for e in erros)


def test_dado_pessoal_pega_cpf_telefone_email():
    c = POR_ID["P03-v02"].model_copy(deep=True)
    c.turnos[0].texto = "meu cpf 123.456.789-09, tel (11) 98765-4321, a@b.com"
    assert len(dado_pessoal(c)) == 3


# ── Bot próprio: funil do 06 ──────────────────────────────────────────────

PROPRIAS = [c for c in CONVERSAS if c.atendente is Atendente.PROPRIO]


def test_bot_proprio_tem_entre_100_e_200_casos():
    """A régua para lapidar o prompt: pequena demais não pega regressão."""
    assert 100 <= len(PROPRIAS) <= 200


def test_bot_proprio_termina_num_estagio_do_06():
    etapas = {e.value for e in Etapa}
    fora = [c.id for c in PROPRIAS if c.esperado.estado_final not in etapas]
    assert not fora


def test_bot_proprio_cobre_o_funil_inteiro():
    """Cada estágio do 06 tem casos; nenhum fica só no papel."""
    cobertos = Counter(c.esperado.estado_final for c in PROPRIAS)
    for etapa in Etapa:
        assert cobertos[etapa.value] >= 1, etapa


@pytest.mark.parametrize(
    "conversa", [c for c in PROPRIAS if c.esperado.temperatura], ids=lambda c: c.id
)
def test_temperatura_esperada_bate_com_a_regra(conversa: Conversa):
    """A temperatura é código (06 §2): o caso diz os dados e o resultado."""
    calculada = temperatura(conversa.esperado.dados, conversa.esperado.quer_agendar)
    assert calculada.value == conversa.esperado.temperatura


def test_temperatura_tem_as_tres_faixas_nos_casos():
    faixas = {c.esperado.temperatura for c in PROPRIAS if c.esperado.temperatura}
    assert faixas == {t.value for t in Temperatura}


def test_regra_de_temperatura_nos_limites():
    base = {"nicho": "clinica", "dor": "x", "decisor": "eu", "urgencia": "agora"}
    assert temperatura({**base, "mensagens_dia": 30}) is Temperatura.QUENTE
    assert temperatura({**base, "mensagens_dia": 29}) is Temperatura.MORNO
    assert temperatura({**base, "mensagens_dia": 99, "urgencia": "pesquisando"}) is Temperatura.MORNO
    assert temperatura({"decisor": "eu"}) is Temperatura.FRIO
    assert temperatura({}, quer_agendar=True) is Temperatura.QUENTE
