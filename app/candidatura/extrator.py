"""Descrição de vaga → requisitos estruturados.

Tarefa de **entender**, não de gerar: rota `extrair` (phi4-mini, temperatura
baixa, JSON com schema). O gateway da F1 já cuida do retry com reprompt, que
aqui não é luxo — descrição de vaga vem com bullet, emoji, tabela e três idiomas
misturados, e é onde modelo pequeno mais erra JSON.

O que se extrai é o que o match precisa comparar. Nada de "cultura da empresa"
ou "benefícios": informação que não entra em decisão é token gasto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.candidatura.perfil import normalizar
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
- Benefício NÃO é requisito. Plano de saúde, vale refeição, vale transporte,
  seguro de vida, previdência privada, Gympass, PPR/PLR, auxílio creche,
  licença maternidade, desconto em farmácia, day off e salário dizem o que a
  EMPRESA oferece. Requisito é o que a PESSOA precisa ter. Ignore a seção de
  benefícios inteira, mesmo quando ela vier em formato de lista de requisitos.
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


# ── Benefício não é requisito ─────────────────────────────────────
#
# O prompt pede; o código garante — a mesma divisão de trabalho da
# anti-alucinação. Num anúncio brasileiro a seção de benefícios vem em lista de
# bullets, com a mesma cara da seção de requisitos, e modelo pequeno copia a
# forma. Na vaga "Engenheiro de Dados - IA/ML" da Accenture os 12 `desejaveis`
# eram benefícios, nenhum diferencial técnico.
#
# Custa caro de dois jeitos: `_score` pesa desejáveis em 25% e a cobertura deles
# é sempre 0/12 (ninguém "tem" Gympass) — 33/100 medido, 42/100 sem eles, com o
# corte do veredito em 45; e o painel manda estudar Gympass junto com Terraform.
#
# A lista é longa e literal de propósito. O sinal é fechado — o catálogo de
# benefícios do mercado brasileiro é curto e estável —, e termo genérico como
# "seguro" ou "idiomas" sozinho derrubaria requisito honesto ("segurança da
# informação", "inglês avançado"). Falso positivo aqui apaga exigência real da
# vaga, que é pior que deixar passar um Gympass.
BENEFICIOS = (
    # saúde
    "assistencia medica", "assistencia odontologica", "assistencia farmaceutica",
    "assistencia funeral", "auxilio funeral", "plano de saude", "plano medico",
    "plano odontologico", "plano dental", "convenio medico", "convenio odontologico",
    "seguro saude", "seguro de saude", "seguro de vida", "telemedicina",
    "apoio psicologico", "suporte psicologico", "desconto em farmacia",
    "desconto em medicamentos", "convenio farmacia",
    # alimentação e deslocamento
    "vale refeicao", "vale alimentacao", "vale transporte", "vale cultura",
    "vale combustivel", "cesta basica", "auxilio refeicao", "auxilio alimentacao",
    "auxilio transporte", "auxilio combustivel", "restaurante no local",
    # dinheiro
    "previdencia privada", "participacao nos lucros", "participacao nos resultados",
    "opcao de compra de acoes", "stock options", "acoes da empresa", "ppr", "plr",
    "bonus", "bonificacao", "gratificacao", "premiacao", "salario", "remuneracao",
    "pretensao salarial", "faixa salarial", "decimo terceiro", "13o salario",
    # tempo e família
    "licenca maternidade", "licenca paternidade", "licenca parental",
    "auxilio creche", "creche", "day off", "folga de aniversario",
    "ferias remuneradas", "horario flexivel",
    # estudo e bem-estar
    "escola de idiomas", "curso de idiomas", "aulas de idiomas", "bolsa de estudos",
    "auxilio educacao", "incentivo educacional", "universidade corporativa",
    "auxilio academia", "gympass", "totalpass", "wellhub", "bem estar",
    # estrutura e marcas de carteira de benefícios
    "auxilio home office", "clube de vantagens", "beneficio flexivel",
    "beneficios flexiveis", "cartao beneficio", "plano de carreira", "alelo",
    "sodexo", "swile", "ticket restaurante", "flash beneficios", "vr beneficios",
    # o próprio cabeçalho, quando ele vem como item
    "beneficios", "beneficio", "o que oferecemos", "nossos beneficios",
)

_E_BENEFICIO = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in BENEFICIOS) + r")\b"
)


def _achatar(texto: str) -> str:
    """`normalizar()` mais hífen e barra virando espaço.

    "vale-refeição" e "vale refeição" são o mesmo benefício escrito de dois
    jeitos, e `normalizar()` preserva `-` e `/` porque tecnologia precisa deles
    ("ci/cd", "next-auth"). Aqui não precisam.
    """
    return re.sub(r"\s+", " ", re.sub(r"[-/]", " ", normalizar(texto))).strip()


def _sem_beneficios(itens: list[str]) -> tuple[list[str], list[str]]:
    """Separa (requisitos, benefícios descartados)."""
    fica, sai = [], []
    for item in itens:
        (sai if _E_BENEFICIO.search(_achatar(item)) else fica).append(item)
    return fica, sai


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

    # `stack` fica de fora do filtro: ali só entram nomes de tecnologia, e uma
    # empresa de benefícios pode ser o próprio empregador.
    obrigatorios, fora_obr = _sem_beneficios(_lista_de_textos(d.get("obrigatorios")))
    desejaveis, fora_des = _sem_beneficios(_lista_de_textos(d.get("desejaveis")))

    req = Requisitos(
        obrigatorios=obrigatorios,
        desejaveis=desejaveis,
        stack=_lista_de_textos(d.get("stack")),
        senioridade=(d.get("senioridade") or None),
        modelo=(d.get("modelo") or None),
        resumo=(d.get("resumo") or None),
    )
    descartados = fora_obr + fora_des
    if descartados:
        logger.info(
            f"Benefício descartado ({len(descartados)}): {', '.join(descartados[:8])}"
        )
    logger.info(
        f"Requisitos: {len(req.obrigatorios)} obrigatórios, "
        f"{len(req.desejaveis)} desejáveis, {len(req.stack)} tecnologias"
    )
    return req
