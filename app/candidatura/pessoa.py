"""Currículo na voz de quem escreve — primeira pessoa, sempre.

Um currículo em português é escrito por mim, sobre mim. "Desenvolvi a API" é a
forma correta; "Desenvolveu a API" é como um recrutador escreve sobre um
candidato, ou como um sistema fala de um registro. A diferença é imediata para
quem lê e ninguém escreve currículo assim.

O prompt pede primeira pessoa e **isso não basta**: um 4B lê "verbo no passado"
e devolve terceira pessoa, que é a forma mais frequente no corpus dele. O prompt
pede, o código garante — a mesma divisão da anti-alucinação em `curriculo.py`.

## Por que dá para converter com regex

Só porque o formato é restrito. Bullet de currículo **começa com o verbo** — é
o que o prompt exige e o que a convenção manda. Isso reduz o problema de
"conjugar português" para "olhar a primeira palavra", que é decidível:

    -ar → administrou → administrei        (ou → ei)
    -er → desenvolveu → desenvolvi         (eu → i)
    -ir → garantiu   → garanti             (iu → i)

Os irregulares que aparecem em currículo cabem numa lista de vinte entradas
(`fez/fiz`, `obteve/obtive`, `pôs/pus`). O resto da frase não é tocado.

O único risco real é a palavra que **termina** como verbo sem ser verbo — "meu",
"museu", "troféu" — e o gatilho é a lista de exceções. Palavras que já estão na
primeira pessoa ("sou", "estou", "vou") entram na mesma lista: convertê-las
seria estragar o que já estava certo.

Verbo coordenado ("Integrei o CRM **e implementou** o portal") é convertido
também, mas só depois que o verbo da frente foi — sem esse gatilho, qualquer
palavra depois de " e " viraria candidata.
"""
from __future__ import annotations

import re

# Verbos que não seguem regra. Chave e valor em minúsculo; a capitalização
# original é reaplicada na saída.
IRREGULARES = {
    "fez": "fiz",
    "foi": "fui",
    "teve": "tive",
    "obteve": "obtive",
    "manteve": "mantive",
    "conteve": "contive",
    "reteve": "retive",
    "deteve": "detive",
    "esteve": "estive",
    "pôde": "pude",
    "pôs": "pus",
    "propôs": "propus",
    "compôs": "compus",
    "dispôs": "dispus",
    "veio": "vim",
    "deu": "dei",
    "leu": "li",
    "viu": "vi",
    "creu": "cri",
    # Presente do indicativo — aparece no resumo, não nos bullets.
    "possui": "possuo",
    "tem": "tenho",
    "atua": "atuo",
    "trabalha": "trabalho",
    "desenvolve": "desenvolvo",
    "constrói": "construo",
    "constroi": "construo",
    "utiliza": "utilizo",
    "integra": "integro",
    "domina": "domino",
    "conhece": "conheço",
    "sabe": "sei",
    "faz": "faço",
    "traz": "trago",
    "é": "sou",
    "está": "estou",
}

# `busca`, `apoio`, `foco` e afins ficam de fora de propósito: em bullet de
# currículo são substantivo muito mais vezes que verbo ("Busca híbrida
# implementada com RRF"), e converter estragaria a frase.

# Termina como verbo de 3ª pessoa mas não é — ou já está na 1ª pessoa, que é
# pior ainda de converter.
EXCECOES = frozenset({
    # já na primeira pessoa
    "sou", "estou", "vou", "dou", "vejo", "sei", "tenho", "faço",
    # substantivos e pronomes
    "meu", "seu", "teu", "museu", "troféu", "trofeu", "chapéu", "europeu",
    "ateu", "réu", "judeu", "hebreu", "escarcéu", "liceu",
    # conjunção e advérbio
    "ou", "eu",
})

# Sem acento no fim ("construiu" → "construí"): quando a raiz termina em vogal,
# o `i` da primeira pessoa é tônico e leva acento. "garantiu" → "garanti".
_VOGAIS = "aeiouáéíóúâêôãõ"

_SUFIXOS = (("ou", "ei"), ("eu", "i"), ("iu", "i"))

# Um verbo coordenado vem depois de " e ", " e, " ou "; ". A vírgula sozinha não
# entra: "Reduzi o tempo, aumentou a cobertura" quase nunca acontece, e ", "
# separa lista de coisas muito mais vezes do que separa verbo.
_COORDENACAO = re.compile(r"(\s+e\s+|;\s+|\s+e,\s+)([A-Za-zÀ-ÿ]{5,})")

_PALAVRA_INICIAL = re.compile(r"^(\W*)([A-Za-zÀ-ÿ]+)")

# Marcas de 3ª pessoa que sobreviveriam à conversão porque não estão no começo
# da frase — se alguma sobrar, o texto não é confiável e o chamador decide.
_TERCEIRA_PESSOA = re.compile(
    r"\b(ele|o candidato|o pablo|o profissional|possui|atua como|"
    r"tem experiência|sua experiência|seu perfil)\b",
    re.IGNORECASE,
)


def _mesma_capitalizacao(original: str, novo: str) -> str:
    if original.isupper():
        return novo.upper()
    if original[:1].isupper():
        return novo[:1].upper() + novo[1:]
    return novo


def converter_verbo(palavra: str) -> str | None:
    """`Desenvolveu` → `Desenvolvi`. `None` quando não é verbo conversível."""
    nu = palavra.lower()
    if nu in EXCECOES:
        return None

    if nu in IRREGULARES:
        return _mesma_capitalizacao(palavra, IRREGULARES[nu])

    # Curto demais para ser verbo de currículo, e é onde moram "meu"/"seu".
    if len(nu) < 5:
        return None

    for sufixo, troca in _SUFIXOS:
        if not nu.endswith(sufixo):
            continue
        raiz = nu[: -len(sufixo)]
        if sufixo == "iu" and raiz and raiz[-1] in _VOGAIS:
            troca = "í"          # construiu → construí, contribuiu → contribuí
        return _mesma_capitalizacao(palavra, raiz + troca)
    return None


def primeira_pessoa(texto: str) -> str:
    """O texto com os verbos de 3ª pessoa na 1ª. Devolve igual se não há o que mudar.

    Converte o verbo que abre cada frase e os verbos coordenados que vêm
    depois — e só esses. Nada no meio de uma frase é reescrito às cegas.
    """
    if not texto or not texto.strip():
        return texto

    saida = []
    # Frase é a unidade: um bullet pode ter duas, e a segunda também começa
    # com verbo ("Implementei o gateway. Reduziu a latência em 40%.").
    for frase in re.split(r"(?<=[.!?])\s+", texto):
        m = _PALAVRA_INICIAL.match(frase)
        if not m:
            saida.append(frase)
            continue

        convertido = converter_verbo(m.group(2))
        if convertido is None:
            saida.append(frase)
            continue

        frase = f"{m.group(1)}{convertido}{frase[m.end():]}"
        # Só agora, com o verbo da frente confirmado, os coordenados entram.
        frase = _COORDENACAO.sub(
            lambda c: c.group(1) + (converter_verbo(c.group(2)) or c.group(2)), frase
        )
        saida.append(frase)

    return " ".join(saida)


def tem_terceira_pessoa(texto: str) -> bool:
    """Sobrou marca de 3ª pessoa que a conversão não alcança?

    Serve para o resumo, que é prosa e não bullet: ali a frase pode começar com
    substantivo ("Experiência em...") e esconder um "possui" no meio.
    """
    return bool(_TERCEIRA_PESSOA.search(texto or ""))
