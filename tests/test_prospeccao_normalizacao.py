"""Normalização — o que faz o mesmo telefone da Receita e do CNES virar uma linha só.

Os casos ruins são os que importam: a fonte manda DDD separado, "+55", zero de
operadora, e-mail em caixa alta, site com barra. Todos os valores são inventados.
"""
from __future__ import annotations

import pytest

from app.comercial.prospeccao import normalizacao as n
from app.db.models.comercial.prospeccao import TipoCanal


@pytest.mark.parametrize(
    ("bruto", "ddd", "esperado", "tipo"),
    [
        ("(11) 3333-4444", None, "+551133334444", TipoCanal.TELEFONE),
        ("11 98765-4321", None, "+5511987654321", TipoCanal.CELULAR),
        ("+55 (11) 98765 4321", None, "+5511987654321", TipoCanal.CELULAR),
        ("011 3333 4444", None, "+551133334444", TipoCanal.TELEFONE),
        ("33334444", "11", "+551133334444", TipoCanal.TELEFONE),
        ("987654321", "011", "+5511987654321", TipoCanal.CELULAR),
    ],
)
def test_telefone_vira_e164(bruto, ddd, esperado, tipo):
    t = n.telefone(bruto, ddd)
    assert (t.valor, t.tipo, t.valido) == (esperado, tipo, True)
    assert t.original == bruto


@pytest.mark.parametrize("bruto", ["33334444", "123", "(01) 3333-4444", "11 7333-4444", "0800 123 4567"])
def test_telefone_ruim_entra_invalido_e_nao_some(bruto):
    """Sem DDD, curto demais, DDD com zero, fixo começando em 7, 0800."""
    t = n.telefone(bruto)
    assert t is not None and not t.valido
    assert not t.valor.startswith("+")


def test_telefone_vazio_nao_vira_canal():
    assert n.telefone("") is None
    assert n.telefone("   ") is None


def test_email_minusculo_e_validado():
    e = n.email("  Contato@Clinica-Exemplo.COM.br ")
    assert (e.valor, e.valido) == ("contato@clinica-exemplo.com.br", True)
    assert n.email("mailto:a@b.com").valor == "a@b.com"
    assert not n.email("contato arroba clinica").valido
    assert n.email("") is None


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        ("www.Exemplo.com.br/", "https://www.exemplo.com.br"),
        ("HTTP://exemplo.com.br/Contato/", "https://exemplo.com.br/Contato"),
        ("https://exemplo.com.br", "https://exemplo.com.br"),
    ],
)
def test_site_sem_barra_final(bruto, esperado):
    s = n.site(bruto)
    assert (s.valor, s.valido) == (esperado, True)


def test_site_sem_dominio_e_invalido():
    assert not n.site("clinicaexemplo").valido


@pytest.mark.parametrize(
    ("seis", "sete"), [("355030", "3550308"), ("330455", "3304557"), ("310620", "3106200")]
)
def test_municipio_ganha_digito_do_ibge(seis, sete):
    """São Paulo, Rio e BH: os códigos de 7 dígitos oficiais."""
    assert n.municipio_ibge(seis) == sete
    assert n.municipio_ibge(sete) == sete
    assert n.municipio_ibge("123") is None


def test_cep():
    assert n.cep("01310-100") == "01310100"
    assert n.cep("0131") is None


def test_cpf_no_fim_do_nome_sai():
    """1.2.6 §3: 5.631 empresários individuais num arquivo só tinham isto."""
    assert n.sem_cpf_no_nome("MARIA EXEMPLO 52998224725") == "MARIA EXEMPLO"


def test_numero_que_nao_e_cpf_fica():
    assert n.sem_cpf_no_nome("IMOVEIS EXEMPLO 12345678901") == "IMOVEIS EXEMPLO 12345678901"
    assert n.sem_cpf_no_nome("CLINICA EXEMPLO LTDA") == "CLINICA EXEMPLO LTDA"


def test_hash_nao_guarda_o_valor():
    h = n.hash_valor("+551133334444")
    assert len(h) == 64 and "3333" not in h
    assert h == n.hash_valor("+551133334444")
