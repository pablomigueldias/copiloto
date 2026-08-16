"""Vaga × Perfil Mestre: o que eu tenho, o que falta, quanto bate.

O teste da §3 do plano — *isso é regra ou julgamento?* — aplicado item a item:

| Pergunta | Quem responde |
|---|---|
| "Python" está no perfil? | **código** (comparação normalizada, com sinônimos) |
| "3+ anos com Python" está coberto? | **código** — contém "python" |
| "vivência com arquitetura de dados" está coberto? | **LLM** — é julgamento sobre linguagem |

O código resolve a maioria e é de graça. O que sobra vai numa **única** chamada
de LLM, classificando tudo de uma vez — não uma chamada por requisito.

Quando o LLM não responde (Ollama fora, JSON inválido), o item vira **falta**.
Conservador de propósito: alegar competência que não dá para provar é o erro
caro; deixar de alegar uma que eu tenho é só um currículo mais modesto.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from app.candidatura.extrator import Requisitos
from app.candidatura.perfil import Fatos, normalizar
from app.llm import gateway
from app.llm.tipos import LLMErro
from app.utils.logger import get_logger

logger = get_logger()

# Obrigatório é o que reprova; desejável é o que desempata.
PESO_OBRIGATORIO = 0.75
PESO_DESEJAVEL = 0.25

SCHEMA = {
    "type": "object",
    "required": ["cobertos"],
    "properties": {"cobertos": {"type": "array"}},
}

PROMPT = """\
Abaixo está o que uma pessoa sabe fazer, e uma lista de requisitos de vaga.
Diga quais requisitos o perfil cobre. Responda só com JSON.

O QUE A PESSOA TEM:
{perfil}

REQUISITOS A AVALIAR:
{requisitos}

Regras:
- "cobertos": lista com o texto EXATO dos requisitos que o perfil cobre.
- Cobre = o perfil tem a competência, mesmo com outro nome.
- NÃO cobre = precisa de ferramenta, área ou tempo de experiência que não
  aparece no perfil. Na dúvida, não cubra.
- Não invente requisito que não está na lista.

JSON:"""


@dataclass(slots=True)
class Item:
    requisito: str
    tenho: bool
    como: str | None = None      # 'perfil' | 'llm'
    evidencia: str | None = None  # o item do perfil que sustenta


@dataclass(slots=True)
class Match:
    score: int = 0
    obrigatorios: list[Item] = field(default_factory=list)
    desejaveis: list[Item] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    destaques: list[str] = field(default_factory=list)  # projetos mais aderentes

    @property
    def veredito(self) -> str:
        if self.score >= 70:
            return "forte"
        if self.score >= 45:
            return "vale tentar"
        return "fraco"

    def como_json(self) -> dict:
        return {
            "score": self.score,
            "veredito": self.veredito,
            "obrigatorios": [asdict(i) for i in self.obrigatorios],
            "desejaveis": [asdict(i) for i in self.desejaveis],
            "gaps": self.gaps,
            "destaques": self.destaques,
        }


def _evidencia(fatos: Fatos, requisito: str) -> str | None:
    """Qual item do perfil sustenta este requisito — para eu poder conferir."""
    n = normalizar(requisito)
    palavras = {p for p in n.split() if len(p) > 2}
    for h in fatos.habilidades:
        alvo = normalizar(h.get("nome", ""))
        if alvo and (alvo in n or alvo in palavras):
            return f"habilidade: {h.get('nome')}"
    for p in fatos.projetos:
        for t in p.get("stack") or []:
            if normalizar(t) in n:
                return f"projeto {p.get('nome')} ({t})"
    for c in fatos.certificacoes:
        if normalizar(c.get("nome", "")) in n:
            return f"certificação: {c.get('nome')}"
    return None


def _resumo_do_perfil(fatos: Fatos) -> str:
    """O perfil comprimido para caber no prompt sem virar 4 mil tokens."""
    hab = ", ".join(h.get("nome", "") for h in fatos.habilidades)
    proj = "; ".join(
        f"{p.get('nome')} ({', '.join((p.get('stack') or [])[:6])})" for p in fatos.projetos
    )
    exp = "; ".join(f"{e.get('cargo')} na {e.get('empresa')}" for e in fatos.experiencias)
    cert = ", ".join(c.get("nome", "") for c in fatos.certificacoes[:15])
    return (
        f"Habilidades: {hab}\nProjetos: {proj}\nExperiência: {exp}\nCertificações: {cert}"
    )


async def _classificar_restantes(fatos: Fatos, pendentes: list[str]) -> set[str]:
    """Uma chamada só para tudo que o código não resolveu."""
    if not pendentes:
        return set()

    try:
        r = await gateway.gerar(
            PROMPT.format(
                perfil=_resumo_do_perfil(fatos),
                requisitos=json.dumps(pendentes, ensure_ascii=False, indent=1),
            ),
            tarefa="classificar",
            agente="candidatura.match",
            json_schema=SCHEMA,
        )
    except LLMErro as e:
        # Sem julgamento disponível, tudo vira gap: modéstia custa menos que
        # alegar o que não dá para provar numa entrevista técnica.
        logger.warning(f"Match sem LLM ({type(e).__name__}); pendentes viram gap")
        return set()

    cobertos = (r.json or {}).get("cobertos") or []
    validos = {normalizar(c) for c in cobertos if isinstance(c, str)}
    # O modelo às vezes devolve requisito que não estava na lista.
    return {p for p in pendentes if normalizar(p) in validos}


async def calcular(requisitos: Requisitos, fatos: Fatos) -> Match:
    """Cruza os requisitos com o perfil e devolve score, evidências e gaps."""
    todos = [(r, True) for r in requisitos.obrigatorios] + [
        (r, False) for r in requisitos.desejaveis
    ]
    # A stack citada na vaga também é requisito, mesmo sem estar nas listas.
    ja_ditos = {normalizar(r) for r, _ in todos}
    todos += [(t, True) for t in requisitos.stack if normalizar(t) not in ja_ditos]

    itens: list[tuple[Item, bool]] = []
    pendentes: list[str] = []
    for requisito, obrigatorio in todos:
        if fatos.conheco(requisito):
            itens.append(
                (
                    Item(
                        requisito=requisito,
                        tenho=True,
                        como="perfil",
                        evidencia=_evidencia(fatos, requisito),
                    ),
                    obrigatorio,
                )
            )
        else:
            pendentes.append(requisito)

    cobertos = await _classificar_restantes(fatos, pendentes)
    for requisito in pendentes:
        obrigatorio = next(o for r, o in todos if r == requisito)
        itens.append(
            (Item(requisito=requisito, tenho=requisito in cobertos, como="llm"), obrigatorio)
        )

    match = Match(
        obrigatorios=[i for i, o in itens if o],
        desejaveis=[i for i, o in itens if not o],
        gaps=[i.requisito for i, _ in itens if not i.tenho],
    )
    match.score = _score(match)
    match.destaques = _destaques(fatos, requisitos)
    logger.info(f"Match {match.score}/100 ({match.veredito}) · {len(match.gaps)} gaps")
    return match


def _score(match: Match) -> int:
    def taxa(itens: list[Item]) -> float | None:
        return sum(i.tenho for i in itens) / len(itens) if itens else None

    obr, des = taxa(match.obrigatorios), taxa(match.desejaveis)
    if obr is None and des is None:
        return 0
    if des is None:
        return round(obr * 100)
    if obr is None:
        return round(des * 100)
    return round((obr * PESO_OBRIGATORIO + des * PESO_DESEJAVEL) * 100)


def _destaques(fatos: Fatos, requisitos: Requisitos) -> list[str]:
    """Os projetos que mais tocam a stack da vaga — o que o currículo põe no topo."""
    pedido = {normalizar(t) for t in requisitos.stack}
    pedido |= {p for r in requisitos.obrigatorios for p in normalizar(r).split()}

    pontuados = []
    for projeto in fatos.projetos:
        stack = {normalizar(t) for t in projeto.get("stack") or []}
        acertos = len(stack & pedido)
        if acertos:
            pontuados.append((acertos, projeto.get("nome", "")))
    return [nome for _, nome in sorted(pontuados, reverse=True)]
