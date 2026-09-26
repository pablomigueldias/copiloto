"""Do `docs/PENDENCIAS.md` para o quadro — uma vez, e sem duplicar se rodar de novo.

A seção "Do Pablo — por tópico" é uma lista de cartões neste formato:

    #### 1. E-mail e domínio
    - [ ] **Título** — o que fazer · quando · onde

O que vier entre o título e o primeiro "·" é a descrição; os dois últimos
pedaços são o gatilho e o arquivo. Cartão sem descrição (só título · quando ·
onde) também vale.

**Idempotente pelo título:** um cartão que já existe no quadro não é tocado,
nem para atualizar. Depois da importação, o quadro é quem manda — reimportar
não pode desfazer o que eu arrastei ou editei na tela.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from app.pendencias import servico

SECAO = re.compile(r"^###\s+Do Pablo\b.*$", re.MULTILINE)
_TOPICO = re.compile(r"^####\s+(?:\d+\.\s+)?(.+?)\s*$")
_CARTAO = re.compile(r"^-\s+\[( |x|X)\]\s+\*\*(.+?)\*\*\s*(.*)$")
_DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")


@dataclass
class Cartao:
    titulo: str
    topico: str
    descricao: str | None
    quando: str | None
    onde: str | None
    prazo: date | None
    feito: bool


def prazo_de(quando: str | None, hoje: date) -> date | None:
    """O primeiro "dd/mm" do gatilho, no ano que deixa a data mais perto de hoje.

    "03/10" escrito em setembro é deste ano; "15/01" escrito em setembro é do
    próximo. Sem data no texto ("antes do 1º contrato"), sem prazo.
    """
    m = _DATA.search(quando or "")
    if not m:
        return None
    dia, mes = int(m[1]), int(m[2])
    anos = [int(m[3])] if m[3] else [hoje.year, hoje.year + 1]
    for ano in anos:
        try:
            d = date(ano, mes, dia)
        except ValueError:
            return None
        if m[3] or d >= hoje - timedelta(days=90):
            return d
    return None


def ler(texto: str, *, hoje: date) -> list[Cartao]:
    """Os cartões da seção "Do Pablo", na ordem do arquivo."""
    inicio = SECAO.search(texto)
    if not inicio:
        return []
    cartoes: list[Cartao] = []
    topico: str | None = None
    for linha in texto[inicio.end():].splitlines():
        if linha.startswith("### "):  # a próxima seção do mesmo nível encerra
            break
        if m := _TOPICO.match(linha):
            topico = m[1]
            continue
        m = _CARTAO.match(linha.strip())
        if not m or topico is None:
            continue
        resto = m[3].lstrip("—–· ").strip()
        partes = [p.strip() for p in resto.split(" · ")] if resto else []
        onde = partes.pop() if len(partes) >= 2 else None
        quando = partes.pop() if partes else None
        descricao = " · ".join(partes) or None
        cartoes.append(
            Cartao(
                titulo=m[2].strip(),
                topico=topico,
                descricao=descricao,
                quando=quando,
                onde=onde,
                prazo=prazo_de(quando, hoje),
                feito=m[1].lower() == "x",
            )
        )
    return cartoes


async def importar(texto: str, *, hoje: date) -> tuple[int, int]:
    """Cria os cartões que ainda não existem. Devolve (criados, já existiam)."""
    existentes = {p.titulo for p in await servico.listar()}
    criados = 0
    for c in ler(texto, hoje=hoje):
        if c.titulo in existentes:
            continue
        await servico.criar(
            titulo=c.titulo,
            topico=c.topico,
            descricao=c.descricao,
            quando=c.quando,
            prazo=c.prazo,
            onde=c.onde,
            coluna="feito" if c.feito else "a_fazer",
        )
        existentes.add(c.titulo)
        criados += 1
    return criados, len(existentes) - criados
