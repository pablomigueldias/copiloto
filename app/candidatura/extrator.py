"""Descrição de vaga → requisitos estruturados.

Tarefa de **entender**, não de gerar: rota `extrair` (phi4-mini, temperatura
baixa, JSON com schema). O gateway da F1 já cuida do retry com reprompt, que
aqui não é luxo — descrição de vaga vem com bullet, emoji, tabela e três idiomas
misturados, e é onde modelo pequeno mais erra JSON.

O que se extrai é o que o match precisa comparar. Nada de "cultura da empresa"
ou "benefícios": informação que não entra em decisão é token gasto.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.llm import gateway
from app.utils.logger import get_logger

logger = get_logger()

# Descrição gigante é raridade e o contexto é 8k. Cortar no fim perde pouco:
# requisito costuma vir antes de "sobre nós" e "benefícios".
MAX_CHARS = 6000

SCHEMA = {
    "type": "object",
    "required": ["obrigatorios", "desejaveis", "stack", "resumo"],
    "properties": {
        "obrigatorios": {"type": "array"},
        "desejaveis": {"type": "array"},
        "stack": {"type": "array"},
        "senioridade": {"type": "string"},
        "modelo": {"type": "string"},
        "resumo": {"type": "string"},
    },
}

PROMPT = """\
Extraia os requisitos desta vaga. Responda só com JSON.

Regras:
- "obrigatorios": o que a vaga exige. Um item por requisito, curto (2-6 palavras).
- "desejaveis": o que é diferencial, plus, "será um diferencial".
- "stack": só nomes de tecnologia, ferramenta ou linguagem citados (Python, AWS,
  Docker). Sem frase, sem verbo.
- "senioridade": junior | pleno | senior | estagio | nao_informado.
- "modelo": remoto | hibrido | presencial | nao_informado.
- "resumo": uma frase dizendo o que a pessoa vai fazer no dia a dia.
- Não invente requisito que não está no texto. Se a vaga não diz, deixe a lista vazia.

VAGA:
{descricao}

JSON:"""


@dataclass(slots=True)
class Requisitos:
    obrigatorios: list[str] = field(default_factory=list)
    desejaveis: list[str] = field(default_factory=list)
    stack: list[str] = field(default_factory=list)
    senioridade: str | None = None
    modelo: str | None = None
    resumo: str | None = None

    def como_json(self) -> dict:
        return {
            "obrigatorios": self.obrigatorios,
            "desejaveis": self.desejaveis,
            "stack": self.stack,
            "senioridade": self.senioridade,
            "modelo": self.modelo,
            "resumo": self.resumo,
        }


def _lista_de_textos(bruto) -> list[str]:
    """Normaliza o que o modelo devolveu para uma lista de strings limpas.

    Modelo pequeno responde `["Python"]`, `[{"nome": "Python"}]` e
    `"Python, SQL"` para o mesmo pedido — as três formas, no mesmo dia.
    """
    if isinstance(bruto, str):
        bruto = [p.strip() for p in bruto.split(",")]
    if not isinstance(bruto, list):
        return []

    saida: list[str] = []
    for item in bruto:
        if isinstance(item, dict):
            item = item.get("nome") or item.get("requisito") or item.get("texto") or ""
        texto = str(item).strip(" -•\t").strip()
        if texto and texto.lower() not in {x.lower() for x in saida}:
            saida.append(texto[:120])
    return saida


async def extrair(descricao: str, *, alvo_ref: str | None = None) -> Requisitos:
    """Chama o modelo de extração e devolve requisitos já normalizados."""
    descricao = (descricao or "").strip()[:MAX_CHARS]
    if not descricao:
        return Requisitos()

    r = await gateway.gerar(
        PROMPT.format(descricao=descricao),
        tarefa="extrair",
        agente="candidatura.extrator",
        json_schema=SCHEMA,
        alvo_ref=alvo_ref,
    )
    d = r.json or {}

    req = Requisitos(
        obrigatorios=_lista_de_textos(d.get("obrigatorios")),
        desejaveis=_lista_de_textos(d.get("desejaveis")),
        stack=_lista_de_textos(d.get("stack")),
        senioridade=(d.get("senioridade") or None),
        modelo=(d.get("modelo") or None),
        resumo=(d.get("resumo") or None),
    )
    logger.info(
        f"Requisitos: {len(req.obrigatorios)} obrigatórios, "
        f"{len(req.desejaveis)} desejáveis, {len(req.stack)} tecnologias"
    )
    return req
