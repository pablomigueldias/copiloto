"""A especificação de voz, e o verificador dela.

`prompts/voz.md` é o texto que vai no prompt; este módulo é a parte que o
código consegue **conferir sozinho**. Sem isso, "seguiu a voz?" seria opinião —
e opinião não escolhe modelo, não vira teste e não entra em fila de aprovação.

Não substitui o julgamento do Pablo sobre o texto estar bom. Pega o que é
objetivo: tamanho, frase proibida, dois pedidos, emoji, negrito de vendedor.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SPEC = RAIZ / "prompts" / "voz.md"

MAX_PALAVRAS = 120

# Cada entrada saiu de texto realmente produzido pelo sistema antigo (propostas
# via Gemini, incluindo as perdidas). É o vocabulário a não reproduzir.
FRASES_PROIBIDAS: tuple[tuple[str, str], ...] = (
    (r"espero que (você )?esteja bem", "abertura de robô"),
    (r"li com aten[çc][ãa]o", "abertura de robô"),
    (r"meu nome [ée] \w+ e", "começa falando de si"),
    (r"gostaria de (me )?(apresentar|oferecer)", "abertura de vendedor"),
    (r"venho por meio (deste|desta)", "formalidade de cartório"),
    (r"se alinha perfeitamente", "enchimento de vendedor"),
    (r"encaixe direto", "enchimento de vendedor"),
    (r"hist[óo]rico comprovado", "enchimento de vendedor"),
    (r"solu[çc][ãa]o (completa|robusta|inovadora)", "adjetivo de venda"),
    (r"\b(revolucion[áa]ri[oa]|poderos[oa]|de ponta|inovador[a]?)\b", "adjetivo de venda"),
    (r"n[ãa]o apenas .{1,40} mas tamb[ée]m", "construção de brochura"),
    (r"otimizar a efici[êe]ncia", "consultês"),
    (r"fico [àa] disposi[çc][ãa]o", "fechamento covarde"),
    (r"aguardo (seu )?retorno", "fechamento covarde"),
    (r"atenciosamente", "fechamento de circular"),
)

_EMOJI = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]", re.UNICODE
)
_NEGRITO = re.compile(r"\*\*.+?\*\*")


def texto_da_spec() -> str:
    """O conteúdo que vai no prompt. Sem fallback silencioso: se o arquivo
    sumiu, é bug de deploy, não caso a tratar."""
    return SPEC.read_text().strip()


def checar(texto: str, *, max_palavras: int = MAX_PALAVRAS) -> list[str]:
    """Devolve as violações encontradas. Lista vazia = passou."""
    problemas: list[str] = []
    limpo = texto.strip()

    palavras = len(limpo.split())
    if palavras > max_palavras:
        problemas.append(f"{palavras} palavras (máximo {max_palavras})")

    baixo = limpo.lower()
    for padrao, rotulo in FRASES_PROIBIDAS:
        achado = re.search(padrao, baixo)
        if achado:
            problemas.append(f"{rotulo}: {achado.group(0)!r}")

    # Dois pedidos na mesma mensagem é o erro mais comum e o mais caro: dilui a
    # ação e derruba resposta.
    if limpo.count("?") > 1:
        problemas.append(f"{limpo.count('?')} perguntas (a regra é um pedido só)")

    if _EMOJI.search(limpo):
        problemas.append("tem emoji")

    if _NEGRITO.search(limpo):
        problemas.append("negrito de grifo de venda")

    return problemas
