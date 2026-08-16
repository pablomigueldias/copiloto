"""Cortar texto em pedaços que ainda fazem sentido sozinhos.

É a decisão mais barata e mais determinante da fase: nenhuma busca, por melhor
que seja o embedder, encontra o que o chunking picou errado. Um trecho que
começa no meio de uma frase e termina no meio de outra tem embedding de coisa
nenhuma.

Regra: **markdown já vem estruturado por quem escreveu**. Cortar a cada N
caracteres joga essa informação fora de graça. Aqui a quebra é por heading,
guardando a trilha (`Título > Seção > Subseção`), e só dentro de uma seção
grande demais é que se recorre a parágrafo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ~1.200 caracteres ≈ 300 tokens: cabe folgado nos 8k de contexto mesmo com 5
# chunks no prompt, e é grande o bastante para uma seção inteira de nota.
TETO_CHARS = 1200
# Abaixo disso o chunk é ruído: "## Instalação\n\nVeja o README." nunca é a
# resposta certa e ainda rouba posição no ranking.
MINIMO_CHARS = 200

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_CERCA = re.compile(r"^\s*```")


@dataclass(slots=True)
class Chunk:
    conteudo: str
    titulo: str | None = None
    ordem: int = 0
    metadados: dict = field(default_factory=dict)


@dataclass(slots=True)
class _Secao:
    trilha: list[str]
    linhas: list[str] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n".join(self.linhas).strip()

    @property
    def titulo(self) -> str | None:
        return " > ".join(self.trilha) if self.trilha else None


def _secoes(texto: str) -> list[_Secao]:
    """Quebra por heading, mantendo a trilha de títulos pais.

    Bloco de código é atravessado sem interpretar: `# comentário` dentro de
    ```bash não é heading, e tratá-lo como tal parte o exemplo ao meio.
    """
    atual = _Secao(trilha=[])
    saida = [atual]
    pilha: list[tuple[int, str]] = []
    dentro_de_cerca = False

    for linha in texto.splitlines():
        if _CERCA.match(linha):
            dentro_de_cerca = not dentro_de_cerca
            atual.linhas.append(linha)
            continue

        m = None if dentro_de_cerca else _HEADING.match(linha)
        if m:
            nivel = len(m.group(1))
            titulo = m.group(2).strip()
            while pilha and pilha[-1][0] >= nivel:
                pilha.pop()
            pilha.append((nivel, titulo))
            atual = _Secao(trilha=[t for _, t in pilha])
            saida.append(atual)
        else:
            atual.linhas.append(linha)

    return [s for s in saida if s.texto]


def _emitir(blocos: list[str], atual: list[str], minimo: int) -> None:
    """Fecha um bloco — grudando no anterior se ele sair curto demais.

    Sem isto, um `---` ou uma linha solta depois de um parágrafo gigante vira
    chunk próprio: paga um embedding, ocupa uma vaga no ranking e nunca é a
    resposta de nada. Apareceu na primeira varredura real, com o separador de
    seção de uma nota.
    """
    bloco = "\n\n".join(atual)
    if blocos and len(bloco) < minimo:
        blocos[-1] = f"{blocos[-1]}\n\n{bloco}"
    else:
        blocos.append(bloco)


def _quebrar_longo(texto: str, teto: int, minimo: int = MINIMO_CHARS) -> list[str]:
    """Seção maior que o teto: quebra por parágrafo, sem partir bloco de código.

    A sobreposição é de um parágrafo: o custo é baixo e evita que a resposta
    fique exatamente na emenda entre dois chunks.
    """
    blocos: list[str] = []
    atual: list[str] = []
    tamanho = 0

    for paragrafo in re.split(r"\n\s*\n", texto):
        p = paragrafo.strip()
        if not p:
            continue
        if tamanho + len(p) > teto and atual:
            _emitir(blocos, atual, minimo)
            # Sobreposição: o último parágrafo do bloco anterior abre o próximo.
            atual = [atual[-1]] if len(atual) > 1 else []
            tamanho = sum(len(x) for x in atual)
        atual.append(p)
        tamanho += len(p)

    if atual:
        _emitir(blocos, atual, minimo)

    # Um parágrafo único maior que o teto (tabela grande, bloco de código
    # longo) fica inteiro de propósito: partir no meio destrói mais do que o
    # tamanho custa.
    return blocos or [texto]


def chunkar(
    texto: str,
    *,
    titulo_base: str | None = None,
    teto: int = TETO_CHARS,
    minimo: int = MINIMO_CHARS,
    metadados: dict | None = None,
) -> list[Chunk]:
    """Texto markdown → lista de chunks prontos para embedar."""
    texto = (texto or "").strip()
    if not texto:
        return []

    pendente: _Secao | None = None
    partes: list[tuple[str | None, str]] = []

    for secao in _secoes(texto):
        conteudo = secao.texto
        # Seções curtas seguidas viram uma só: a soma tem contexto, cada uma
        # sozinha não tem.
        if pendente is not None:
            conteudo = f"{pendente.texto}\n\n{conteudo}"
            secao = _Secao(trilha=pendente.trilha or secao.trilha, linhas=conteudo.splitlines())
            pendente = None

        if len(conteudo) < minimo:
            pendente = secao
            continue

        if len(conteudo) <= teto:
            partes.append((secao.titulo, conteudo))
        else:
            partes.extend(
                (secao.titulo, bloco) for bloco in _quebrar_longo(conteudo, teto, minimo)
            )

    if pendente is not None:
        # A sobra final gruda no último chunk, ou vira chunk se for a única.
        if partes:
            titulo, ultimo = partes[-1]
            partes[-1] = (titulo, f"{ultimo}\n\n{pendente.texto}")
        else:
            partes.append((pendente.titulo, pendente.texto))

    base = metadados or {}
    saida: list[Chunk] = []
    for i, (titulo, conteudo) in enumerate(partes):
        completo = " > ".join(x for x in (titulo_base, titulo) if x)
        saida.append(
            Chunk(conteudo=conteudo, titulo=completo or None, ordem=i, metadados=dict(base))
        )
    return saida
