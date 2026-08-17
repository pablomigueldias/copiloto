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


# ── LaTeX que o modelo escreve dentro do JSON ─────────────────────


def test_comando_latex_sobrevive_ao_parser():
    """`\\rightarrow` e JSON **valido**: `\\r` e retorno de carro, entao o parse
    passa de primeira e entrega `ightarrow` no meio da palavra. Uma nota de
    estudo com isso ensina que o bicondicional tem o simbolo do condicional."""
    assert extrair_json(r'{"d": "$p \rightarrow q$"}') == {"d": r"$p \rightarrow q$"}
    assert extrair_json(r'{"d": "\neg P"}') == {"d": r"\neg P"}
    assert extrair_json(r'{"d": "\forall x"}') == {"d": r"\forall x"}


def test_comando_latex_que_invalidava_o_json_inteiro():
    """`\\land`, `\\lor` e `\\leftrightarrow` nao sao escapes validos: derrubavam
    o fichamento completo, nao so um campo."""
    assert extrair_json(r'{"d": "P \land Q \lor R"}') == {"d": r"P \land Q \lor R"}
    assert extrair_json(r'{"d": "p \leftrightarrow q"}') == {"d": r"p \leftrightarrow q"}


def test_escape_legitimo_continua_funcionando():
    """A quebra de linha de verdade nao pode virar barra literal — o texto do
    curriculo tem `\\n` de propósito."""
    assert extrair_json('{"d": "linha1\\nlinha2"}') == {"d": "linha1\nlinha2"}
    assert extrair_json('{"d": "col1\\tcol2"}') == {"d": "col1\tcol2"}
    assert extrair_json('{"d": "ele disse \\"oi\\""}') == {"d": 'ele disse "oi"'}
    assert extrair_json('{"caminho": "C:\\\\Users"}') == {"caminho": "C:\\Users"}
