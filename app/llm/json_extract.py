"""Extração robusta de JSON de respostas de LLM.

Portado do repo antigo (`analyzers/_json_extract.py`), onde já rodava em
produção. Aqui vale mais do que lá: modelo local de 4B erra a sintaxe do JSON
com frequência muito maior que uma API grande — cerca markdown sobrando, uma
frase antes do objeto, saída cortada no limite de tokens.

Ordem: limpar o texto → parse direto → reparar truncamento → desistir. Quem
desiste é o gateway, que reprompta com o erro em mãos.
"""
from __future__ import annotations

import json
import re

from app.utils.logger import get_logger

logger = get_logger()


def _limpar_texto(texto: str) -> str:
    """Tira cercas markdown e recorta o JSON do topo. Suporta objeto `{...}` E
    array `[...]` (o modelo às vezes devolve o array direto, sem o wrapper que o
    prompt pediu)."""
    t = texto.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    t = t.strip()
    abre_obj, abre_arr = t.find("{"), t.find("[")
    # Se um array abre ANTES de qualquer objeto, é um array no topo → recorta [..].
    if abre_arr != -1 and (abre_obj == -1 or abre_arr < abre_obj):
        inicio, fim = abre_arr, t.rfind("]")
    else:
        inicio, fim = abre_obj, t.rfind("}")
    if inicio != -1 and fim != -1 and fim > inicio:
        t = t[inicio : fim + 1]
    return t.strip()


# Escapes que o JSON entende. Qualquer outra barra invertida dentro de uma
# string é do modelo escrevendo LaTeX, não sintaxe.
_ESCAPES_VALIDOS = set('"\\/bfnrtu')

# O caso difícil: `\r`, `\n`, `\t`, `\f` e `\b` **são** escapes válidos, então
# `\rightarrow` faz o parse passar de primeira e entrega um retorno de carro no
# meio da palavra. Não dá para decidir pelo caractere; decide-se pelo nome do
# comando. Se o que vem depois da barra é um comando LaTeX conhecido, era LaTeX.
_COMANDOS_LATEX = (
    "neg|land|lor|lnot|leftrightarrow|rightarrow|leftarrow|Leftrightarrow|"
    "Rightarrow|longrightarrow|to|forall|exists|nexists|in|notin|ni|cup|cap|"
    "subset|supset|subseteq|supseteq|emptyset|equiv|therefore|because|oplus|"
    # As formas grandes vieram de uma nota real: o modelo escreveu `\bigvee` para
    # "ou", e como `bigvee` não estava aqui, o `\b` caiu na regra do escape
    # válido — a nota ficou com um **caractere de backspace** dentro de um
    # destaque, e o resto do comando ("igvee") virou texto.
    "bigvee|bigwedge|bigcup|bigcap|"
    "otimes|vee|wedge|times|div|pm|leq|geq|neq|approx|sim|infty|cdot|ldots|"
    "dots|frac|sqrt|sum|prod|int|alpha|beta|gamma|delta|theta|lambda|mu|pi|"
    "sigma|phi|omega|Delta|Sigma|Omega|mathbb|mathrm|text|begin|end|quad|qquad"
)
_LATEX_NA_STRING = re.compile(rf"\\({_COMANDOS_LATEX})(?![a-zA-Z])")


def _preservar_barra_invertida(texto: str) -> str:
    r"""`\rightarrow` vira `\\rightarrow` — o LaTeX sobrevive ao parser.

    Modelo escrevendo lógica escreve `$p \rightarrow q$`, e o JSON lê `\r` como
    retorno de carro: chega `ightarrow` do outro lado. Três dos seis conectivos
    são piores que isso — `\land`, `\lor` e `\leftrightarrow` **invalidam o JSON
    inteiro**, derrubando o fichamento completo.

    Uma nota de estudo com isso está pior que errada: ela ensina que o
    bicondicional tem o mesmo símbolo do condicional, porque os dois viraram a
    mesma sequência quebrada.

    Só mexe **dentro de string**: fora dela a barra invertida não é legítima em
    JSON nenhum, e reescrever ali esconderia sintaxe realmente quebrada.
    """
    saida: list[str] = []
    dentro_string = False
    i = 0
    while i < len(texto):
        ch = texto[i]
        if ch == '"' and not (saida and saida[-1] == "\\" and dentro_string):
            dentro_string = not dentro_string
            saida.append(ch)
            i += 1
            continue
        if ch == "\\" and dentro_string:
            # Comando LaTeX ganha da regra do escape: `\rightarrow` é seta, não
            # retorno de carro seguido de "ightarrow".
            if _LATEX_NA_STRING.match(texto, i):
                saida.append("\\\\")
                i += 1
                continue
            seguinte = texto[i + 1] if i + 1 < len(texto) else ""
            if seguinte in _ESCAPES_VALIDOS:
                saida.append(ch)
                saida.append(seguinte)
                i += 2
                continue
            saida.append("\\\\")     # barra do modelo: vira barra literal
            i += 1
            continue
        saida.append(ch)
        i += 1
    return "".join(saida)


def _reparar_json_truncado(texto: str) -> str | None:
    """Fecha um JSON cortado no meio (limite de tokens da LLM)."""
    t = texto.rstrip()
    if not t:
        return None

    pilha: list[str] = []
    dentro_string = False
    escape = False

    for ch in t:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            dentro_string = not dentro_string
            continue
        if dentro_string:
            continue
        if ch in "{[":
            pilha.append(ch)
        elif ch == "}" and pilha and pilha[-1] == "{":
            pilha.pop()
        elif ch == "]" and pilha and pilha[-1] == "[":
            pilha.pop()

    if dentro_string:
        t += '"'
    t = re.sub(r",\s*$", "", t)
    for abre in reversed(pilha):
        t += "}" if abre == "{" else "]"

    try:
        json.loads(t)
        return t
    except json.JSONDecodeError:
        return None


def extrair_json(texto_cru: str) -> dict | list | None:
    """Converte o texto cru da LLM num dict (ou list), ou None se não der.

    Tenta: parse direto do texto limpo → reparo de truncamento → desiste.
    Suporta objeto `{...}` e array `[...]` no topo (parsers tratam ambos).
    """
    if not texto_cru or not texto_cru.strip():
        logger.warning("LLM retornou texto vazio")
        return None

    limpo = _limpar_texto(texto_cru)

    # Antes de qualquer parse: `\rightarrow` é JSON **válido** e entrega um
    # retorno de carro no meio da palavra. Deixar o parse acontecer primeiro
    # significaria aceitar a corrupção calado.
    limpo = _preservar_barra_invertida(limpo)

    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        pass

    reparado = _reparar_json_truncado(limpo)
    if reparado is not None:
        try:
            logger.info("JSON truncado reparado com sucesso")
            return json.loads(reparado)
        except json.JSONDecodeError:
            pass

    logger.error(
        "Não foi possível extrair JSON válido ({} chars). Conteúdo cru: {!r}",
        len(texto_cru),
        texto_cru[:800],
    )
    return None
