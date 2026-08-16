"""Busca no índice: metade vetor, metade palavra, fundidas por posição.

Embedding é bom em ideia e ruim em nome. Perguntado por `pgvector`, `arq` ou
`RRF`, o bge-m3 devolve trechos que *falam sobre banco vetorial* e erra o trecho
que cita a biblioteca — porque a sigla quase não tem sinal semântico. O full-text
do Postgres acerta exatamente esses, e erra tudo que foi dito com outras
palavras. Um cobre o buraco do outro; nenhum dos dois cobre sozinho.

A fusão é **RRF** (*reciprocal rank fusion*):

    score = Σ  1 / (60 + posição naquela lista)

Não é média de notas de propósito: distância de cosseno (0..2, menor é melhor) e
`ts_rank_cd` (escala aberta, maior é melhor) não são comparáveis nem depois de
normalizar — a normalização depende do conjunto devolvido, então a mesma
distância vira nota diferente conforme a consulta. Posição, sim, soma: aparecer
em terceiro nas duas listas vale mais que ser primeiro em uma e ausente na
outra, que é justamente o comportamento que se quer.

O 60 é a constante do artigo original (Cormack et al., 2009). Ela achata a
diferença entre as primeiras posições: o primeiro colocado não domina a fusão
sozinho, e é isso que dá à segunda lista o poder de resgatar um resultado.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Select, func, select

from app.db.models.conhecimento import ConhecimentoChunk
from app.db.session import get_session
from app.llm import gateway
from app.utils.logger import get_logger

logger = get_logger()

# Constante do RRF. Ver docstring do módulo.
K_RRF = 60
# Quantos cada metade traz antes da fusão. Vinte é o suficiente para a outra
# lista ter o que resgatar sem pagar por um SELECT largo.
CANDIDATOS = 20
LIMITE = 5


@dataclass(slots=True)
class Trecho:
    """Um chunk devolvido pela busca, com de onde veio e por quê.

    `fonte_ref` e `titulo` não são enfeite: sem citar a origem, a resposta da F3
    é indistinguível de alucinação.
    """

    id: UUID
    fonte_tipo: str
    fonte_ref: str
    ordem: int
    titulo: str | None
    conteudo: str
    metadados: dict = field(default_factory=dict)
    score: float = 0.0
    posicao_vetorial: int | None = None
    posicao_lexical: int | None = None
    # Distância de cosseno até a pergunta (0 = idêntico). `None` quando o chunk
    # veio só do full-text. É a **única** medida de confiança que a busca
    # produz: o `score` do RRF é função da posição, então um resultado ruim que
    # ficou em primeiro numa lista empata com um ótimo que ficou em primeiro na
    # outra. Medido neste índice: pergunta com resposta 0,27–0,48; sem resposta
    # 0,48–0,75.
    distancia: float | None = None

    @property
    def origem(self) -> str:
        if self.posicao_vetorial is not None and self.posicao_lexical is not None:
            return "ambas"
        return "vetorial" if self.posicao_vetorial is not None else "lexical"

    def __str__(self) -> str:
        return f"{self.titulo or self.fonte_ref} ({self.origem}, {self.score:.4f})"


def _filtrar(
    stmt: Select,
    fonte_tipo: str | Sequence[str] | None,
    tags: Sequence[str] | None,
) -> Select:
    """Filtros que valem para as duas metades — aplicados antes do LIMIT.

    Filtrar depois da fusão devolveria menos resultados que o pedido sempre que
    a consulta cruzasse fontes.
    """
    if fonte_tipo:
        tipos = [fonte_tipo] if isinstance(fonte_tipo, str) else list(fonte_tipo)
        stmt = stmt.where(ConhecimentoChunk.fonte_tipo.in_(tipos))
    for tag in tags or ():
        # `metadados -> 'tags'` é array JSONB; jsonb_exists é o `?` do Postgres
        # escrito por extenso, para não colidir com o placeholder do driver.
        stmt = stmt.where(func.jsonb_exists(ConhecimentoChunk.metadados["tags"], tag.lower()))
    return stmt


async def _embedar_consulta(q: str) -> list[float] | None:
    """Vetor da pergunta — ou None, e a busca segue só com a metade lexical.

    Ollama fora do ar degrada a busca; não deveria derrubá-la. O full-text é do
    próprio Postgres e continua respondendo.
    """
    try:
        return (await gateway.embedar([q]))[0]
    except Exception as e:  # noqa: BLE001 — indisponibilidade não é erro de busca
        logger.warning(f"Sem embedding para a consulta ({type(e).__name__}: {e}); só lexical")
        return None


def _stmt_vetorial(vetor: list[float], n: int) -> Select:
    # A distância vem junto do chunk: ordenar por ela e depois jogá-la fora
    # (como a F2 fazia) descarta a única medida de confiança da busca.
    distancia = ConhecimentoChunk.embedding.cosine_distance(vetor)
    return (
        select(ConhecimentoChunk, distancia.label("distancia"))
        .where(ConhecimentoChunk.embedding.is_not(None))
        .order_by(distancia)
        .limit(n)
    )


def _stmt_lexical(q: str, n: int) -> Select:
    # `plainto_tsquery` trata a pergunta como texto do usuário: ignora pontuação
    # e liga os termos com AND, sem exigir sintaxe de busca de ninguém.
    consulta = func.plainto_tsquery("portuguese", q)
    return (
        select(ConhecimentoChunk)
        .where(ConhecimentoChunk.tsv.bool_op("@@")(consulta))
        # ts_rank_cd (e não ts_rank) porque leva em conta a *proximidade* entre
        # os termos: num chunk de 1.200 caracteres, dois termos na mesma frase
        # valem mais que os mesmos dois nas pontas opostas.
        .order_by(func.ts_rank_cd(ConhecimentoChunk.tsv, consulta).desc())
        .limit(n)
    )


def _fundir(
    vetorial: Iterable[tuple[ConhecimentoChunk, float] | ConhecimentoChunk],
    lexical: Iterable[ConhecimentoChunk],
) -> list[Trecho]:
    """RRF: soma 1/(K + posição) das listas em que o chunk apareceu."""
    achados: dict[UUID, Trecho] = {}

    def registrar(itens: Iterable, *, lista: str) -> None:
        for posicao, item in enumerate(itens, start=1):
            c, distancia = item if isinstance(item, tuple) else (item, None)
            t = achados.get(c.id)
            if t is None:
                t = achados[c.id] = Trecho(
                    id=c.id,
                    fonte_tipo=c.fonte_tipo,
                    fonte_ref=c.fonte_ref,
                    ordem=c.ordem,
                    titulo=c.titulo,
                    conteudo=c.conteudo,
                    metadados=c.metadados or {},
                )
            if distancia is not None:
                t.distancia = float(distancia)
            t.score += 1 / (K_RRF + posicao)
            setattr(t, f"posicao_{lista}", posicao)

    registrar(vetorial, lista="vetorial")
    registrar(lexical, lista="lexical")

    # Desempate por posição vetorial: com uma lista só, RRF empata quem empatou
    # de posição, e o resultado viraria ordem de chegada do banco.
    return sorted(achados.values(), key=lambda t: (-t.score, t.posicao_vetorial or 99, t.fonte_ref))


async def buscar(
    q: str,
    *,
    limite: int = LIMITE,
    candidatos: int = CANDIDATOS,
    fonte_tipo: str | Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
) -> list[Trecho]:
    """Busca híbrida no conhecimento indexado.

    Devolve no máximo `limite` trechos, ordenados por RRF, cada um sabendo de
    qual metade veio.
    """
    q = (q or "").strip()
    if not q:
        return []

    vetor = await _embedar_consulta(q)

    async with get_session() as session:
        vetorial: list[tuple[ConhecimentoChunk, float]] = []
        if vetor is not None:
            stmt = _filtrar(_stmt_vetorial(vetor, candidatos), fonte_tipo, tags)
            vetorial = [(c, d) for c, d in (await session.execute(stmt)).all()]

        stmt = _filtrar(_stmt_lexical(q, candidatos), fonte_tipo, tags)
        lexical = list((await session.scalars(stmt)).all())

    trechos = _fundir(vetorial, lexical)[:limite]
    logger.info(
        f"busca {q!r}: {len(vetorial)} vetoriais + {len(lexical)} lexicais "
        f"→ {len(trechos)} trechos"
    )
    return trechos
