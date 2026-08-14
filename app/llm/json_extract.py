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
