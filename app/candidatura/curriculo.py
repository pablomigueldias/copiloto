"""Currículo adaptado a uma vaga — selecionando e reformulando, nunca inventando.

O gerador **não escreve um currículo**. Ele escolhe, entre os fatos do Perfil
Mestre, quais entram e em que ordem, e reescreve cada bullet com a linguagem da
vaga. O documento é montado por código a partir dessa seleção.

A diferença não é sutil: se a saída fosse texto corrido, "inventar uma seção" ou
"acrescentar uma empresa" seria possível. Sendo JSON com o item de origem
nomeado, o pior caso vira um bullet ruim — nunca um fato falso.

**A verificação final é a que vale.** Três camadas:

1. o prompt recebe só o perfil e a vaga;
2. a saída referencia projetos e experiências pelo nome exato do perfil;
3. **toda tecnologia citada é conferida contra a lista branca** — o que não
   estiver no perfil é removido, e o que foi removido vira medida.

Um 4B vai querer acrescentar "Kubernetes" porque combina com o resto do texto.
Em entrevista técnica isso é reprovação, com a cara do Pablo na frente.

## O que veio do gerador do Prospector

Três acertos do repo antigo (`analyzers/curriculo/prompt_builder.py`), mantidos:

- **competências agrupadas** por categoria (Linguagens, Backend, Banco de
  Dados) em vez de uma lista corrida de trinta itens;
- **espelhar o termo exato da vaga** quando o perfil sustenta: se a vaga diz
  "React.js", escrever "React.js" e não "React" — o ATS ranqueia por casamento
  de string, não por sinônimo. Espelhar não é inventar;
- **bullets de realização** por experiência, com verbo no início.

## O que a pesquisa de 2026 acrescentou

Parser de ATS (Workday, Greenhouse, Lever, Ashby, iCIMS) ainda quebra em: duas
colunas, tabela, caixa de texto, cabeçalho/rodapé de página, ícone no lugar de
rótulo e PDF de imagem. E há uma novidade que não existia há três anos:

- **entrada de experiência sem data é motivo de recusa automática** em vários
  sistemas — daí `avisos` apontar experiência sem mês;
- **repetição artificial de palavra-chave agora é punida** (texto branco, seção
  "Palavras-chave"), então o gerador é proibido de criar seção assim.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from app.candidatura.extrator import Requisitos
from app.candidatura.match import Match
from app.candidatura.perfil import Fatos, normalizar, tecnologias_citadas
from app.candidatura.pessoa import primeira_pessoa, tem_terceira_pessoa
from app.fila import exemplos as few_shot
from app.llm import gateway
from app.llm.tipos import LLMErro
from app.utils.logger import get_logger

logger = get_logger()

MAX_BULLETS = 3
MAX_PROJETOS = 3
MAX_GRUPOS_COMPETENCIA = 6

# Mês por extenso ou número: uma entrada de experiência sem isso é recusada
# automaticamente por parte dos ATS de 2026.
_TEM_MES = re.compile(
    r"\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|\d{1,2})[/\s.-]*\d{4}", re.IGNORECASE
)

# Duas chamadas, não uma. O gemma4:e4b recebeu o pedido das quatro estruturas
# de uma vez e respondeu com resumo e competências, parando por conta própria
# (`finish_reason=stop`, 239 tokens) — três vezes seguidas, inclusive no
# reprompt. Não é truncamento: é modelo pequeno tratando instrução de quatro
# partes como quatro pedidos e atendendo os dois primeiros.
#
# É a regra da §3 do plano aplicada aqui: tarefa pontual e bem delimitada. Duas
# chamadas de 15 s que funcionam valem mais que uma de 24 s que cai no fallback.

SCHEMA_TOPO = {
    "type": "object",
    "required": ["resumo", "competencias"],
    "properties": {
        "titulo": {"type": "string"},
        "resumo": {"type": "string"},
        "competencias": {"type": "array"},
    },
}

SCHEMA_BULLETS = {
    "type": "object",
    "required": ["projetos"],
    "properties": {
        "experiencias": {"type": "array"},
        "projetos": {"type": "array"},
    },
}

_CABECALHO = """\
Você adapta o currículo do Pablo para uma vaga. Responda só com JSON.

REGRA ABSOLUTA: use SOMENTE o que está no perfil abaixo. Não acrescente
tecnologia, empresa, número ou resultado que não esteja escrito ali. Se a vaga
pede algo que o perfil não tem, ignore — não invente.

ESPELHE OS TERMOS DA VAGA quando o perfil sustentar: se a vaga escreve
"React.js", escreva "React.js" e não "React"; se ela diz "APIs REST", use
"APIs REST". O filtro ranqueia por casamento exato de palavra. Espelhar o termo
de algo que você tem NÃO é inventar. Nunca crie seção de palavras-chave.

VOZ: quem escreve é o Pablo, sobre o Pablo. PRIMEIRA PESSOA do singular,
sempre — "Desenvolvi", "Implementei", "Reduzi", "Construo", "Tenho". NUNCA
terceira pessoa: "desenvolveu", "implementou", "possui", "o candidato".
Não escreva o pronome "eu"; a conjugação já diz quem é.

PERFIL (a única verdade disponível):
{perfil}

VAGA:
{vaga}
"""

PROMPT_TOPO = _CABECALHO + """
Produza EXATAMENTE este JSON, com as duas chaves:

{{
  "titulo": "<o cargo da vaga, curto, se o perfil sustentar>",
  "resumo": "<2 ou 3 frases, NA PRIMEIRA PESSOA, ligando o que eu já fiz ao que
              esta vaga pede. Comece pelo que eu faço ('Desenvolvo...',
              'Trabalho com...'), não por 'Experiência em' nem 'Possui'.
              Sem escrever o pronome 'eu', sem adjetivo de venda,
              sem frase de efeito>",
  "competencias": [
    {{"categoria": "<rótulo de 1-2 palavras>", "itens": ["<habilidades DO PERFIL>"]}}
  ]
}}

No máximo 6 grupos de competência, os mais pedidos pela vaga primeiro.

JSON:"""

PROMPT_BULLETS = _CABECALHO + """{voz}
Produza EXATAMENTE este JSON, com as duas chaves:

{{
  "experiencias": [
    {{"empresa": "<nome exato do perfil>",
      "bullets": ["<2 ou 3 realizações. Comece com verbo na PRIMEIRA PESSOA do
                   passado: 'Administrei', 'Implementei', 'Reduzi'. Jamais
                   'Administrou', 'Implementou', 'Reduziu'>"]}}
  ],
  "projetos": [
    {{"nome": "<nome exato do perfil>",
      "bullets": ["<2 ou 3 linhas do que EU construí e com quê, também na
                   primeira pessoa: 'Construí', 'Integrei', 'Obtive'>"]}}
  ]
}}

Escreva bullets para TODAS as experiências do perfil e para os 3 projetos mais
relevantes. Se um projeto tem resultado medido no perfil, o número aparece num
bullet — é a informação mais valiosa da página.

Cada bullet diz uma coisa NOVA. Não repita em bullet o que já está na linha de
stack do projeto: "Utilizei FastAPI, SQLAlchemy e PostgreSQL" não é realização,
é a stack escrita duas vezes. Prefira o que o sistema faz, para quem, e o
resultado.

Todos os bullets da MESMA entrada ficam no mesmo tempo verbal — passado.
Misturar "Administrei" com "Mantenho" na mesma experiência é erro de revisão, e
é a primeira coisa que um recrutador nota.

JSON:"""


@dataclass(slots=True)
class Curriculo:
    titulo: str
    resumo: str = ""
    competencias: list[dict] = field(default_factory=list)   # [{categoria, itens}]
    experiencias: list[dict] = field(default_factory=list)
    projetos: list[dict] = field(default_factory=list)
    formacao: list[dict] = field(default_factory=list)
    certificacoes: list[dict] = field(default_factory=list)
    # O que a verificação derrubou. Não é detalhe de log: é a medida de quanto
    # o modelo tentou inventar, e o que decide se o prompt precisa mudar.
    rejeitados: list[str] = field(default_factory=list)
    # Problemas de ATS que só o Pablo resolve (data faltando, projeto sem número).
    avisos: list[str] = field(default_factory=list)

    @property
    def competencias_planas(self) -> list[str]:
        return [i for g in self.competencias for i in g.get("itens", [])]

    def como_json(self) -> dict:
        return asdict(self)


# ── Verificação (a camada que vale) ───────────────────────────────


def verificar(texto: str, fatos: Fatos, *, extras: frozenset[str] = frozenset()) -> str | None:
    """Devolve a primeira tecnologia inventada, ou None se o texto é honesto.

    `extras` libera termos que são verdade mas não vêm do perfil — o nome da
    empresa da vaga, por exemplo, que pode aparecer legitimamente no resumo.
    """
    for termo in sorted(tecnologias_citadas(texto)):
        if termo in extras or fatos.conheco(termo):
            continue
        return termo
    return None


# ── Montagem do prompt ────────────────────────────────────────────


def _perfil_para_prompt(fatos: Fatos, destaques: list[str]) -> str:
    """O perfil, com os projetos mais aderentes primeiro."""
    ordem = {nome: i for i, nome in enumerate(destaques)}
    projetos = sorted(fatos.projetos, key=lambda p: ordem.get(p.get("nome", ""), len(ordem)))

    linhas = [f"Habilidades: {', '.join(h.get('nome', '') for h in fatos.habilidades)}", ""]
    for p in projetos[: MAX_PROJETOS + 2]:
        linhas.append(f"PROJETO {p.get('nome')}")
        linhas.append(f"  o que é: {p.get('descricao', '')}")
        linhas.append(f"  stack: {', '.join(p.get('stack') or [])}")
        if p.get("prova"):
            linhas.append(f"  resultado medido: {p['prova']}")
    for e in fatos.experiencias:
        linhas.append(f"EXPERIÊNCIA {e.get('cargo')} na {e.get('empresa')} ({e.get('periodo')})")
        linhas.append(f"  {e.get('descricao', '')}")
    return "\n".join(linhas)


def _selecionar_certificacoes(fatos: Fatos, requisitos: Requisitos, *, n: int = 6) -> list[dict]:
    """As certificações que tocam a vaga — código puro, sem inferência."""
    pedido = {normalizar(t) for t in requisitos.stack}
    pedido |= {
        p
        for r in requisitos.obrigatorios + requisitos.desejaveis
        for p in normalizar(r).split()
        if len(p) > 3
    }

    def pontos(c: dict) -> int:
        texto = normalizar(f"{c.get('nome', '')} {c.get('tema', '')}")
        return sum(1 for termo in pedido if termo and termo in texto)

    ordenadas = sorted(fatos.certificacoes, key=pontos, reverse=True)
    return [c for c in ordenadas if pontos(c)][:n] or ordenadas[:n]


def _avisos_de_ats(fatos: Fatos, curriculo: Curriculo) -> list[str]:
    """O que um parser de 2026 penaliza e só o Pablo pode consertar."""
    avisos = []
    for e in curriculo.experiencias:
        periodo = str(e.get("periodo") or "")
        if not periodo:
            avisos.append(f"{e.get('empresa')}: sem período — parte dos ATS recusa automaticamente")
        elif not _TEM_MES.search(periodo):
            avisos.append(f"{e.get('empresa')}: período '{periodo}' sem mês (use 'jan/2025 – dez/2025')")
    sem_numero = [p["nome"] for p in curriculo.projetos
                  if not any(any(c.isdigit() for c in b) for b in p.get("bullets", []))]
    if sem_numero:
        avisos.append(f"sem número de resultado: {', '.join(sem_numero)}")
    return avisos


# ── Geração ───────────────────────────────────────────────────────


async def _chamar(prompt: str, schema: dict, etapa: str) -> dict:
    """Uma etapa do currículo. Falhar aqui degrada a seção, não o documento."""
    try:
        r = await gateway.gerar(
            prompt,
            tarefa="redigir",
            agente=f"candidatura.curriculo.{etapa}",
            json_schema=schema,
            temperatura=0.4,
        )
        return r.json or {}
    except LLMErro as e:
        logger.warning(f"Currículo/{etapa} sem LLM ({type(e).__name__}); cai para o perfil")
        return {}


async def gerar(
    *,
    fatos: Fatos,
    requisitos: Requisitos,
    match: Match,
    titulo_vaga: str,
    descricao_vaga: str,
    empresa_vaga: str | None = None,
    usar_few_shot: bool = True,
) -> Curriculo:
    """Gera o currículo adaptado e derruba o que o modelo inventou."""
    voz = ""
    if usar_few_shot:
        achados = await few_shot.exemplos_para("bullet_curriculo", descricao_vaga[:500])
        bloco = few_shot.bloco_few_shot(achados)
        if bloco:
            voz = f"\n{bloco}\n"

    vaga = (
        f"{titulo_vaga}" + (f" — {empresa_vaga}" if empresa_vaga else "") + "\n"
        f"Requisitos: {', '.join(requisitos.obrigatorios) or '—'}\n"
        f"Desejáveis: {', '.join(requisitos.desejaveis) or '—'}\n"
        f"Stack (use estes termos exatos quando o perfil sustentar): "
        f"{', '.join(requisitos.stack) or '—'}\n"
        f"O que a pessoa vai fazer: {requisitos.resumo or '—'}"
    )
    contexto = {"perfil": _perfil_para_prompt(fatos, match.destaques), "vaga": vaga}

    # O nome da empresa da vaga é verdade, só não está no perfil.
    extras = frozenset({normalizar(empresa_vaga)} if empresa_vaga else set())

    curriculo = Curriculo(
        titulo=titulo_vaga,
        formacao=list(fatos.perfil.formacao or []),
        certificacoes=_selecionar_certificacoes(fatos, requisitos),
    )

    topo = await _chamar(PROMPT_TOPO.format(**contexto), SCHEMA_TOPO, "topo")
    bullets = await _chamar(
        PROMPT_BULLETS.format(**contexto, voz=voz), SCHEMA_BULLETS, "bullets"
    )

    curriculo.titulo = str(topo.get("titulo") or titulo_vaga).strip()[:120]
    curriculo.resumo = _resumo_limpo(topo.get("resumo"), fatos, curriculo, extras)
    curriculo.competencias = _competencias_limpas(topo.get("competencias"), fatos, requisitos)
    curriculo.experiencias = _experiencias_limpas(
        bullets.get("experiencias"), fatos, curriculo, extras
    )
    curriculo.projetos = _projetos_limpos(bullets.get("projetos"), fatos, curriculo, extras)
    curriculo.avisos = _avisos_de_ats(fatos, curriculo)

    if curriculo.rejeitados:
        logger.warning(
            f"Anti-alucinação derrubou {len(curriculo.rejeitados)}: "
            f"{', '.join(curriculo.rejeitados[:5])}"
        )
    return curriculo


def _resumo_limpo(bruto, fatos: Fatos, curriculo: Curriculo, extras: frozenset[str]) -> str:
    texto = str(bruto or "").strip()
    if not texto:
        return fatos.perfil.resumo or ""
    inventada = verificar(texto, fatos, extras=extras)
    if inventada:
        # Resumo é o topo da página: com fato falso ali, o documento inteiro
        # fica suspeito. Cai para o resumo do próprio perfil.
        curriculo.rejeitados.append(f"resumo (citou {inventada})")
        return fatos.perfil.resumo or ""

    texto = primeira_pessoa(texto)
    if tem_terceira_pessoa(texto):
        # O resumo é prosa, não bullet: aqui a 3ª pessoa pode estar no meio da
        # frase, onde a conversão não entra. O resumo do perfil já está na voz
        # certa e foi escrito pelo Pablo — é melhor que um remendo.
        curriculo.rejeitados.append("resumo (3ª pessoa)")
        return fatos.perfil.resumo or ""
    return texto


def _agrupar_por_padrao(fatos: Fatos, requisitos: Requisitos) -> list[dict]:
    """Fallback: um grupo com as habilidades mais pedidas primeiro."""
    pedido = {normalizar(t) for t in requisitos.stack}
    ordenadas = sorted(
        (h.get("nome", "") for h in fatos.habilidades),
        key=lambda n: normalizar(n) not in pedido,
    )
    return [{"categoria": "Competências", "itens": list(ordenadas)[:14]}]


def _mesmo_termo(a: str, b: str) -> bool:
    """Um destes dois termos normalizados é o outro escrito por extenso?

    A comparação é **por palavra inteira**, não por substring, e a diferença é
    a que separa um filtro útil de um que apaga palavra-chave:

        "scikit-learn" ⊂ "machine learning (scikit-learn)"  → mesmo termo ✓
        "sql"          ⊂ "sqlalchemy 2.0 async"             → termos DIFERENTES

    Na primeira versão isto era `a in b`, e "SQL" — requisito obrigatório da
    vaga — sumia do currículo por ser prefixo de "SQLAlchemy".
    """
    curto, longo = sorted((a, b), key=len)
    if curto == longo:
        return True
    return bool(re.search(rf"(?<![\w+#.]){re.escape(curto)}(?![\w+#.])", longo))


def _competencias_limpas(bruto, fatos: Fatos, requisitos: Requisitos) -> list[dict]:
    """As competências, sem repetição e sem nome de projeto.

    Três filtros que o `conheco()` sozinho não faz, porque a lista branca da
    anti-alucinação é deliberadamente generosa — ela responde *"isto é verdade?"*,
    e aqui a pergunta é outra: *"isto é uma competência?"*.

    1. **Nome de projeto não é habilidade.** "Churn Prediction" na linha de
       Ciência de Dados faz o recrutador procurar uma tecnologia que não existe.
       O projeto tem seção própria, com bullets.
    2. **Sem repetir entre categorias.** "SQLAlchemy 2.0 async" em *Banco de
       Dados* e em *Backend* não dobra a chance no ATS: parece revisão malfeita.
    3. **Sem repetir dentro do mesmo item.** "Machine Learning (scikit-learn)"
       e "scikit-learn" lado a lado é o mesmo termo escrito duas vezes — o
       filtro derruba o mais curto quando um contém o outro.
    """
    if not isinstance(bruto, list) or not bruto:
        return _agrupar_por_padrao(fatos, requisitos)

    projetos = {normalizar(p.get("nome", "")) for p in fatos.projetos}
    ja_listados: dict[str, str] = {}     # normalizado → como foi escrito
    grupos: list[dict] = []

    for g in bruto:
        if not isinstance(g, dict):
            continue
        itens: list[str] = []
        for item in g.get("itens") or []:
            nome = str(item.get("nome") if isinstance(item, dict) else item or "").strip()
            n = normalizar(nome)
            # Competência é a mais fácil de inventar e a mais lida pelo ATS.
            if not nome or not n or not fatos.conheco(nome) or n in projetos:
                continue
            # Um termo que contém outro já listado (ou está contido nele) é o
            # mesmo termo: fica o mais informativo, que é o mais longo.
            colisao = next(
                (visto for visto in ja_listados if _mesmo_termo(visto, n)), None
            )
            if colisao:
                if len(n) > len(colisao):
                    antigo = ja_listados.pop(colisao)
                    for grupo in grupos:
                        if antigo in grupo["itens"]:
                            grupo["itens"][grupo["itens"].index(antigo)] = nome
                            ja_listados[n] = nome
                            break
                    else:
                        if antigo in itens:
                            itens[itens.index(antigo)] = nome
                            ja_listados[n] = nome
                continue
            ja_listados[n] = nome
            itens.append(nome)

        categoria = str(g.get("categoria") or "").strip()[:40]
        if itens and categoria:
            grupos.append({"categoria": categoria, "itens": itens})

    # Um grupo pode ter ficado vazio depois dos filtros.
    grupos = [g for g in grupos if g["itens"]]
    return grupos[:MAX_GRUPOS_COMPETENCIA] or _agrupar_por_padrao(fatos, requisitos)


def _bullets_limpos(
    bruto, fatos: Fatos, curriculo: Curriculo, extras: frozenset[str], origem: str
) -> list[str]:
    bullets: list[str] = []
    for b in bruto or []:
        texto = str(b).strip(" -•\t")
        if not texto:
            continue
        inventada = verificar(texto, fatos, extras=extras)
        if inventada:
            curriculo.rejeitados.append(f"{origem}: citou {inventada}")
            continue
        # Depois da verificação, não antes: a conversão mexe só no verbo, e
        # trocar o texto antes de conferir os fatos seria conferir outra coisa.
        bullets.append(primeira_pessoa(texto))
    return bullets[:MAX_BULLETS]


def _experiencias_limpas(
    bruto, fatos: Fatos, curriculo: Curriculo, extras: frozenset[str]
) -> list[dict]:
    """Experiência é fato: empresa, cargo e período vêm do perfil, sempre.

    O modelo só escreve os bullets — e é a única parte que pode ser rejeitada.
    """
    por_empresa = {normalizar(e.get("empresa", "")): e for e in fatos.experiencias}
    gerados: dict[str, list[str]] = {}

    for item in bruto if isinstance(bruto, list) else []:
        if not isinstance(item, dict):
            continue
        chave = normalizar(item.get("empresa", ""))
        if chave not in por_empresa:
            curriculo.rejeitados.append(f"experiência inexistente: {item.get('empresa')}")
            continue
        gerados[chave] = _bullets_limpos(
            item.get("bullets"), fatos, curriculo, extras, por_empresa[chave]["empresa"]
        )

    saida = []
    for e in fatos.experiencias:
        bullets = gerados.get(normalizar(e.get("empresa", "")), [])
        saida.append(
            {
                "empresa": e.get("empresa"),
                "cargo": e.get("cargo"),
                "periodo": e.get("periodo"),
                # Sem bullets aprovados, o texto do perfil é melhor que nada.
                "bullets": bullets or ([e["descricao"]] if e.get("descricao") else []),
            }
        )
    return saida


def _projetos_limpos(
    bruto, fatos: Fatos, curriculo: Curriculo, extras: frozenset[str]
) -> list[dict]:
    reais = {normalizar(p.get("nome", "")): p for p in fatos.projetos}
    saida: list[dict] = []

    for item in bruto if isinstance(bruto, list) else []:
        if not isinstance(item, dict):
            continue
        projeto = reais.get(normalizar(item.get("nome", "")))
        if projeto is None:
            # Projeto que não existe no perfil: o pior tipo de invenção.
            curriculo.rejeitados.append(f"projeto inexistente: {item.get('nome')}")
            continue

        bullets = _bullets_limpos(
            item.get("bullets"), fatos, curriculo, extras, projeto["nome"]
        )
        if bullets:
            saida.append(
                {
                    "nome": projeto["nome"],
                    "stack": projeto.get("stack") or [],
                    "link": projeto.get("link"),
                    "bullets": bullets,
                }
            )

    if not saida:
        # Tudo rejeitado: melhor o texto do perfil que página em branco.
        saida = [
            {
                "nome": p.get("nome"),
                "stack": p.get("stack") or [],
                "link": p.get("link"),
                "bullets": [x for x in (p.get("descricao"), p.get("prova")) if x],
            }
            for p in fatos.projetos[:MAX_PROJETOS]
        ]
    return saida[:MAX_PROJETOS]


# ── Saídas ────────────────────────────────────────────────────────


def como_texto(c: Curriculo, fatos: Fatos) -> str:
    """O currículo em texto puro — o que o ATS realmente lê.

    A ordem das seções é a que os parsers esperam em 2026: contato, resumo,
    competências, experiência, projetos, formação, certificações.
    """
    p = fatos.perfil
    contato = p.contato or {}
    linhas = [
        p.nome,
        c.titulo,
        # Sem "https://", como o PDF já faz: o texto da fila é o que eu reviso, e
        # ele tem que ser o mesmo documento que sai impresso. Ver `pdf._montar`.
        " · ".join(
            f"{k}: {re.sub(r'^https?://', '', str(v)).rstrip('/')}"
            for k, v in contato.items()
            if v
        ),
        "",
        "RESUMO",
        c.resumo,
        "",
        "COMPETÊNCIAS",
    ]
    linhas += [f"{g['categoria']}: {' · '.join(g['itens'])}" for g in c.competencias]

    linhas += ["", "EXPERIÊNCIA PROFISSIONAL"]
    for e in c.experiencias:
        linhas.append(f"{e.get('cargo')} · {e.get('empresa')} ({e.get('periodo')})")
        linhas += [f"  - {b}" for b in e.get("bullets", [])]

    linhas += ["", "PROJETOS"]
    for projeto in c.projetos:
        linhas.append(f"{projeto['nome']} — {', '.join(projeto.get('stack') or [])}")
        linhas += [f"  - {b}" for b in projeto["bullets"]]

    linhas += ["", "FORMAÇÃO"]
    linhas += [
        f"{f.get('instituicao')} — {f.get('curso')} ({f.get('periodo')})" for f in c.formacao
    ]
    if c.certificacoes:
        linhas += ["", "CERTIFICAÇÕES"]
        linhas += [
            f"{cert.get('nome')}"
            + (f" — {cert.get('instituicao')}" if cert.get("instituicao") else "")
            + (f" ({cert.get('ano')})" if cert.get("ano") else "")
            for cert in c.certificacoes
        ]
    return "\n".join(linhas)


def como_json_texto(c: Curriculo) -> str:
    return json.dumps(c.como_json(), ensure_ascii=False, indent=2)


# ── O caminho de volta: o que eu editei vira o documento ──────────

_SECAO_TEXTO = re.compile(
    r"^(RESUMO|COMPET[ÊE]NCIAS|EXPERI[ÊE]NCIA PROFISSIONAL|PROJETOS|FORMA[ÇC][ÃA]O|"
    r"CERTIFICA[ÇC][ÕO]ES)\s*$"
)
_BULLET_TEXTO = re.compile(r"^\s{2}-\s+(.+)$")


def de_texto(texto: str, base: Curriculo) -> Curriculo:
    """O texto que eu aprovei na fila → `Curriculo`, sobre a base gerada.

    **Por que existe.** Eu editava o currículo no textarea da fila, aprovava, e
    o PDF continuava saindo do `curriculo_json` original — o texto do modelo, não
    o meu. A correção era gravada e o documento que eu ia mandar não mudava.

    **Por que "sobre a base" e não do zero.** O texto não carrega tudo: `stack`
    e `link` de projeto, e o `cargo`/`periodo` de cada experiência, existem no
    JSON e não aparecem em formato reconstruível. Então só se sobrescreve o que
    o texto realmente diz — resumo, competências e bullets, que é justamente o
    que eu edito — e o resto continua vindo do gerador.

    Formato desconhecido não é erro: se eu reescrever a seção inteira à mão, a
    parte que não deu para ler fica como estava. Perder a formatação é
    reversível; jogar fora o meu texto, não.
    """
    novo = Curriculo(**base.como_json())
    secao: str | None = None
    resumo: list[str] = []
    competencias: list[dict] = []
    # `None` para "esta entrada não é do perfil": bullets órfãos são ignorados
    # em vez de irem parar na experiência errada.
    bullets_exp: dict[str, list[str]] = {}
    bullets_proj: dict[str, list[str]] = {}
    atual: list[str] | None = None

    for linha in (texto or "").splitlines():
        nu = linha.strip()
        if _SECAO_TEXTO.match(nu):
            secao = normalizar(nu)
            atual = None
            continue
        if not nu:
            continue

        m = _BULLET_TEXTO.match(linha)
        if m:
            if atual is not None:
                atual.append(m.group(1).strip())
            continue

        if secao == "resumo":
            resumo.append(nu)
        elif secao == "competencias" and ":" in nu:
            categoria, _, itens = nu.partition(":")
            valores = [i.strip() for i in itens.split("·") if i.strip()]
            if categoria.strip() and valores:
                competencias.append({"categoria": categoria.strip(), "itens": valores})
        elif secao == "experiencia profissional":
            # "Cargo · Empresa (período)" — a empresa é a chave.
            empresa = nu.split("·")[-1].split("(")[0].strip() if "·" in nu else nu
            atual = bullets_exp.setdefault(normalizar(empresa), [])
        elif secao == "projetos":
            nome = nu.split("—")[0].strip()
            atual = bullets_proj.setdefault(normalizar(nome), [])

    if resumo:
        novo.resumo = " ".join(resumo)
    if competencias:
        novo.competencias = competencias
    for e in novo.experiencias:
        achados = bullets_exp.get(normalizar(e.get("empresa", "")))
        if achados:
            e["bullets"] = achados

    reconhecidos = [p for p in novo.projetos if normalizar(p.get("nome", "")) in bullets_proj]
    if reconhecidos:
        # Apagar um projeto do texto é uma decisão minha sobre esta vaga — o
        # gerador escolhe três, e às vezes o terceiro não ajuda naquela
        # candidatura. Só vale quando pelo menos um foi reconhecido: se a seção
        # inteira ficou ilegível, o certo é manter tudo, não zerar.
        novo.projetos = reconhecidos
        for p in novo.projetos:
            achados = bullets_proj.get(normalizar(p.get("nome", "")))
            if achados:
                p["bullets"] = achados
    return novo
