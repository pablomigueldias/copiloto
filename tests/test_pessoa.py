"""A voz do currículo: primeira pessoa, garantida por código.

O prompt pede e o modelo às vezes obedece. Estes testes cobrem o "às vezes" —
inclusive o caso que mais importa, que é **não estragar** o que já estava certo.
"""
from __future__ import annotations

import pytest

from app.candidatura.pessoa import (
    converter_verbo,
    primeira_pessoa,
    tem_terceira_pessoa,
)


@pytest.mark.parametrize(
    ("terceira", "primeira"),
    [
        # -ar → ou/ei
        ("Administrou", "Administrei"),
        ("Orquestrou", "Orquestrei"),
        ("Implementou", "Implementei"),
        ("Automatizou", "Automatizei"),
        ("Criou", "Criei"),
        ("Atuou", "Atuei"),
        ("Migrou", "Migrei"),
        # -er → eu/i
        ("Desenvolveu", "Desenvolvi"),
        ("Escreveu", "Escrevi"),
        ("Resolveu", "Resolvi"),
        # -ir → iu/i
        ("Garantiu", "Garanti"),
        ("Reduziu", "Reduzi"),
        # raiz terminada em vogal leva acento
        ("Construiu", "Construí"),
        ("Contribuiu", "Contribuí"),
        # irregulares
        ("Obteve", "Obtive"),
        ("Manteve", "Mantive"),
        ("Fez", "Fiz"),
        ("Foi", "Fui"),
        ("Propôs", "Propus"),
        # presente, que aparece no resumo
        ("Possui", "Possuo"),
        ("Constrói", "Construo"),
    ],
)
def test_converte_verbo(terceira: str, primeira: str) -> None:
    assert converter_verbo(terceira) == primeira


@pytest.mark.parametrize(
    "palavra",
    [
        "Sou", "Estou", "Vou", "Tenho",      # já na primeira pessoa
        "Meu", "Seu", "Museu", "Troféu",     # terminam como verbo sem ser
        "Busca", "Python", "FastAPI",        # substantivo e nome próprio
    ],
)
def test_nao_mexe_no_que_nao_e_verbo_de_terceira(palavra: str) -> None:
    assert converter_verbo(palavra) is None


def test_bullet_inteiro() -> None:
    entrada = "Desenvolveu assistente local-first que indexa notas em pgvector."
    esperado = "Desenvolvi assistente local-first que indexa notas em pgvector."
    assert primeira_pessoa(entrada) == esperado


def test_verbo_coordenado_tambem_vira() -> None:
    entrada = "Integrou LLMs (Gemini/Groq) e implementou autenticação completa."
    saida = primeira_pessoa(entrada)
    assert saida == "Integrei LLMs (Gemini/Groq) e implementei autenticação completa."


def test_duas_frases_no_mesmo_bullet() -> None:
    entrada = "Implementou o gateway de LLM. Reduziu a latência em 40%."
    assert primeira_pessoa(entrada) == "Implementei o gateway de LLM. Reduzi a latência em 40%."


def test_coordenado_so_muda_se_o_da_frente_mudou() -> None:
    """Sem verbo de 3ª na frente, ' e <palavra>' não é candidato a nada.

    É o gatilho que impede "Python e Ollama" de virar experimento de conjugação.
    """
    entrada = "Stack de Python e Ollama rodando em Docker."
    assert primeira_pessoa(entrada) == entrada


def test_bullet_que_ja_esta_certo_passa_intacto() -> None:
    entrada = "Reduzi de 3h para 20min o fechamento mensal."
    assert primeira_pessoa(entrada) == entrada


def test_bullet_nominal_passa_intacto() -> None:
    """Descrição do perfil é nominal ('Administração do ecossistema Zoho')."""
    entrada = "Administração do ecossistema Zoho One, garantindo a integração."
    assert primeira_pessoa(entrada) == entrada


def test_marcador_solto_de_terceira_pessoa() -> None:
    assert tem_terceira_pessoa("Experiência em Python, possui domínio de SQL.")
    assert tem_terceira_pessoa("O candidato desenvolveu APIs.")
    assert not tem_terceira_pessoa("Desenvolvo APIs em Python e FastAPI.")


def test_texto_vazio_nao_quebra() -> None:
    assert primeira_pessoa("") == ""
    assert primeira_pessoa("   ") == "   "
