"""O que o modelo local devolve quando devia devolver JSON.

Cada caso aqui é uma saída real do tipo que um 4B produz — o original foi
portado sem teste nenhum, e é justamente o módulo que segura o retry do
gateway.
"""
from app.llm.json_extract import extrair_json


def test_json_limpo():
    assert extrair_json('{"a": 1}') == {"a": 1}


def test_cerca_markdown():
    assert extrair_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extrair_json("```\n{\"a\": 1}\n```") == {"a": 1}


def test_conversa_em_volta():
    cru = 'Claro! Segue o JSON pedido:\n{"nome": "Pablo"}\nEspero ter ajudado.'
    assert extrair_json(cru) == {"nome": "Pablo"}


def test_array_no_topo():
    assert extrair_json('Aqui está:\n[{"a": 1}, {"a": 2}]') == [{"a": 1}, {"a": 2}]


def test_objeto_ganha_do_array_quando_vem_antes():
    assert extrair_json('{"itens": [1, 2]}') == {"itens": [1, 2]}


def test_truncado_no_meio_de_objeto():
    # Limite de tokens cortou a saída: faltam as chaves de fechamento.
    cru = '{"requisitos": ["python", "fastapi"], "senioridade": "pleno"'
    assert extrair_json(cru) == {
        "requisitos": ["python", "fastapi"],
        "senioridade": "pleno",
    }


def test_truncado_dentro_de_string():
    cru = '{"resumo": "vaga de backend com foco em'
    assert extrair_json(cru) == {"resumo": "vaga de backend com foco em"}


def test_truncado_com_virgula_pendurada():
    cru = '{"a": 1, "b": 2,'
    assert extrair_json(cru) == {"a": 1, "b": 2}


def test_aspas_escapadas_nao_confundem_o_reparo():
    cru = '{"frase": "ele disse \\"oi\\" e saiu"'
    assert extrair_json(cru) == {"frase": 'ele disse "oi" e saiu'}


def test_vazio_e_lixo_retornam_none():
    assert extrair_json("") is None
    assert extrair_json("   ") is None
    assert extrair_json("desculpe, não posso ajudar com isso") is None
