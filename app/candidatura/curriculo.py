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

- **competências agrupadas** por categoria em vez de uma lista corrida de
  trinta itens — só que a categoria virou tabela (`ats.TAXONOMIA`): o modelo
  escolhe QUAIS habilidades entram, o código decide ONDE cada uma mora;
- **espelhar o termo exato da vaga** quando o perfil sustenta: se a vaga diz
  "React.js", escrever "React.js" e não "React" — o ATS ranqueia por casamento
  de string, não por sinônimo. Espelhar não é inventar;
- **bullets de realização** por experiência, com verbo no início.

## O que a pesquisa de 2026 acrescentou

Parser de ATS (Workday, Greenhouse, Lever, Ashby, iCIMS) ainda quebra em: duas
colunas, tabela, caixa de texto, cabeçalho/rodapé de página, ícone no lugar de
rótulo e PDF de imagem. E há uma novidade que não existia há três anos:

- **entrada de experiência sem data é motivo de recusa automática** em vários
  sistemas — daí `avisos` apontar experiência sem mês, e `ats.periodo()`
  normalizar toda data para um formato só;
- **repetição artificial de palavra-chave agora é punida** (texto branco, seção
  "Palavras-chave"), então o gerador é proibido de criar seção assim — e a
  sigla é escrita por extenso UMA vez, não em todo bullet;
- **o título tem que espelhar o do anúncio**, letra por letra: "Desenvolvedor
  de IA" e "Engenheiro de IA" são a mesma vaga para mim e strings diferentes
  para o filtro. Por isso o modelo não escreve mais o título.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from app.candidatura import ats
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
# Sete e não seis: as seis categorias canônicas de `ats.py` mais o balde
# `Ferramentas`, que existe justamente para não empurrar item para a
# categoria errada. Se a taxonomia cobre tudo, o balde nem aparece.
MAX_GRUPOS_COMPETENCIA = 7
# Oito itens por categoria. Os itens já vêm ordenados com o que a vaga pediu na
# frente, então o corte tira só o que não casa — e uma linha de doze termos
# dilui os quatro que importam: numa vaga de dados, "WordPress, WHM, cPanel" na
# PRIMEIRA linha de competências fala sobre outro profissional.
MAX_ITENS_CATEGORIA = 8

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
  "resumo": "<2 ou 3 frases, NA PRIMEIRA PESSOA, ligando o que eu já fiz ao que
              esta vaga pede. Comece pelo que eu faço ('Desenvolvo...',
              'Trabalho com...'), não por 'Experiência em' nem 'Possui'.
              Sem escrever o pronome 'eu', sem adjetivo de venda,
              sem frase de efeito>",
  "competencias": [
    {{"categoria": "<uma das categorias da lista abaixo>",
      "itens": ["<habilidades DO PERFIL>"]}}
  ]
}}

O RESUMO É LIDO COLADO NO TÍTULO DO ANÚNCIO, que aparece impresso logo acima
dele. Duas consequências:

1. A primeira frase tem que responder àquele título. Se o anúncio diz
   "Engenheiro de Dados - IA/ML", abrir com "Desenvolvedor com foco em Python e
   FastAPI" faz as duas linhas discordarem na hora — o recrutador lê as duas
   juntas. Não copie o título como rótulo; escreva o que eu faço que É aquilo.
2. Os NOMES PRÓPRIOS de tecnologia que a vaga pede e o perfil sustenta
   (AWS Bedrock, AWS Step Functions, pgvector…) vão no resumo. São os termos
   mais raros do documento e esta é a posição de maior peso da página; deixá-los
   só lá embaixo é jogar fora o lugar onde eles valem mais.

CATEGORIAS PERMITIDAS, exatamente com estes nomes e nenhum outro:
IA e Machine Learning; Dados e Pipelines; Linguagens; Frameworks e Arquitetura;
DevOps e Infraestrutura; Testes, Qualidade e Processo; Ferramentas.

Um rótulo que mistura categorias ("Agentes e Aplicações" com Next.js, Docker e
Playwright dentro) faz a triagem por skills classificar os três errado. Ponha
primeiro os grupos que a vaga mais pede.

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
relevantes. Em cada projeto, o PRIMEIRO bullet é o que mais toca o que a vaga
pede — se o projeto faz ingestão e indexação de documentos e a vaga fala de
pipelines de dados, é isso que abre, não a arquitetura interna. Escreva os 3
bullets; parar em 2 é jogar fora uma linha que já está paga. Se um projeto tem resultado medido no perfil, o número aparece num
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


# As palavras que aparecem dentro das expansões de sigla que o PRÓPRIO código
# escreve (`ats.SIGLAS`: RAG → "Retrieval-Augmented Generation").
#
# Sem isto a anti-alucinação rejeitava o texto por citar "Generation" — uma
# palavra que o `_expandir_siglas` insere sozinho duas linhas depois. O efeito
# era caro e invisível: o resumo do modelo era descartado inteiro e o currículo
# caía para o `resumo` estático do perfil, que fala de "Python e FastAPI"
# enquanto o título do anúncio diz "Engenheiro de Dados". Levei um dia para
# perceber que o resumo fraco não era escolha do modelo, era queda.
_PALAVRAS_DE_EXPANSAO: frozenset[str] = frozenset(
    palavra
    for expansao in ats.SIGLAS.values()
    for palavra in normalizar(expansao).split()
    if len(palavra) > 1
)


def verificar(texto: str, fatos: Fatos, *, extras: frozenset[str] = frozenset()) -> str | None:
    """Devolve a primeira tecnologia inventada, ou None se o texto é honesto.

    `extras` libera termos que são verdade mas não vêm do perfil — o nome da
    empresa da vaga, por exemplo, que pode aparecer legitimamente no resumo.
    """
    for termo in sorted(tecnologias_citadas(texto)):
        if termo in extras or fatos.conheco(termo):
            continue
        # Escrever a sigla por extenso não é inventar: é a mesma coisa que o
        # `expansor()` faz, e por regra do próprio ATS (§2.2).
        if all(p in _PALAVRAS_DE_EXPANSAO for p in normalizar(termo).split()):
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


# Palavras que toda vaga usa e que não dizem nada sobre o assunto dela.
#
# Elas vêm dos requisitos escritos em prosa ("Garantir observabilidade, testes e
# qualidade de código") e, contadas como se fossem termo técnico, elegem
# certificação por acaso: "Do Figma ao código" entrou por **código**, e
# "Coaching para Alta Performance em TI" por **alta** e **performance** — numa
# vaga de engenharia de dados.
#
# O efeito era pior que uma lista ruim: quase toda certificação empatava em 1
# ponto, e o desempate era a ordem em que elas saíam do banco. Reimportar o
# perfil trocava as certificações do currículo sem ninguém mexer em nada.
#
# Duas famílias, e as duas apareceram numa vaga real:
#
# - **funcional**: "Infraestrutura como código" traz `como`, que elegeu
#   "DIO Agent: Nunca Mais Estude". O filtro de `len > 3` não pega essas —
#   `como`, `mais`, `para` e `entre` têm quatro ou mais letras.
# - **de processo**: "Garantir observabilidade, testes e qualidade de código"
#   traz `garantir`, `qualidade` e `codigo`.
_PALAVRAS_DE_PROCESSO = frozenset({
    # funcionais do português (o `len > 3` não alcança)
    "ainda", "alem", "algumas", "alguns", "apenas", "aquele", "assim",
    "atraves", "cada", "como", "conforme", "deve", "devera", "entre", "essa",
    "esse", "esta", "este", "isso", "junto", "mais", "menos", "mesmo", "muito",
    "onde", "outra", "outro", "para", "pela", "pelo", "pouco", "porque",
    "qualquer", "quando", "seja", "sendo", "seus", "sobre", "suas", "tambem",
    "todas", "todos",
    # genéricas de anúncio de vaga
    "anos", "area", "areas", "forma", "meses", "nivel", "requisito",
    "requisitos", "responsabilidades", "vaga",
    "alta", "ambiente", "apoiar", "atuar", "capacidade", "cliente", "codigo",
    "conhecimento", "construir", "criar", "desenvolver", "dominio", "equipe",
    "executar", "experiencia", "ferramentas", "garantir", "habilidade",
    "implementar", "integrar", "manter", "negocio", "orquestrar", "participar",
    "performance", "processos", "projeto", "projetos", "qualidade", "realizar",
    "sistema", "sistemas", "solucao", "solucoes", "tecnologias", "time",
    "trabalhar", "vivencia",
})


def _selecionar_certificacoes(fatos: Fatos, requisitos: Requisitos, *, n: int = 6) -> list[dict]:
    """As certificações que tocam o ASSUNTO da vaga — código puro, sem inferência."""
    pedido = {normalizar(t) for t in requisitos.stack}
    pedido |= {
        p
        for r in requisitos.obrigatorios + requisitos.desejaveis
        for p in normalizar(r).split()
        if len(p) > 3 and p not in _PALAVRAS_DE_PROCESSO
    }
    pedido.discard("")

    # Nome próprio de tecnologia que a vaga cita. Vale mais que palavra de
    # assunto: "Bedrock" só aparece se o curso for daquilo.
    forte = {t for t in (normalizar(x) for x in requisitos.stack) if t}

    def pontos(c: dict) -> tuple[int, int]:
        """(termos da stack que casaram, termos de assunto que casaram).

        A descrição entra junto: "Fundamentos de SOC" não casa com "segurança"
        pelo nome, mas a descrição dele fala de monitoramento. O nome do curso
        raramente usa a palavra que a vaga usa.

        Por palavra inteira, e não substring: "rds" não pode casar dentro de
        "wordsmith", nem "s3" dentro de "css3".
        """
        texto = normalizar(
            f"{c.get('nome', '')} {c.get('tema', '')} {c.get('descricao', '')}"
        )
        casaram = {termo for termo in pedido if ats.contem_termo(termo, texto)}
        return (len(casaram & forte), len(casaram))

    def entra(c: dict) -> bool:
        """Um termo genérico sozinho não é evidência de relevância.

        Foi assim que "Do Figma ao código" entrou numa vaga de dados: casou em
        **design**, porque a vaga dizia "Design de plataformas SaaS". Um acerto
        de palavra solta é o mesmo sorteio de antes, com outra roupa.

        Passa quem casa um nome próprio de tecnologia da vaga (aí não há
        coincidência) ou pelo menos dois termos de assunto (aí não é acaso).
        """
        stack_casada, total = pontos(c)
        return stack_casada >= 1 or total >= 2

    # Ordenar pelo nome no empate: sem isso a lista sai na ordem do banco, e
    # reimportar o perfil troca as certificações do currículo.
    def forca(c: dict) -> int:
        """Nome próprio pesa o dobro de palavra de assunto, e não infinito.

        Ordenar por "casou stack? então na frente" fazia um acerto isolado —
        "Python 3 - Mundo 1" casando `python` — passar à frente de um curso que
        casava dois termos do assunto da vaga.
        """
        stack_casada, total = pontos(c)
        return 2 * stack_casada + total

    ordenadas = sorted(
        fatos.certificacoes, key=lambda c: (-forca(c), normalizar(c.get("nome", "")))
    )
    relevantes = [c for c in ordenadas if entra(c)]
    # Sem nenhuma relevante, vale mostrar as que existem — currículo sem seção
    # de certificação nenhuma perde uma seção inteira. Com alguma, **só** as
    # relevantes: seis certificações diluídas pesam menos que três que casam.
    return (relevantes or ordenadas)[:n]


def _fora_do_resumo(curriculo: Curriculo, requisitos: Requisitos, *, n: int = 3) -> list[str]:
    """Termos que a vaga pede, que eu tenho, e que o RESUMO não menciona.

    O resumo é a posição de maior peso do documento e a única que o recrutador
    lê inteira. Um termo raro — "AWS Bedrock", "AWS Step Functions" — listado só
    na seção de competências está no documento, mas fora do lugar onde ele
    decide alguma coisa.

    Isto é conferência, não conserto: **texto é do modelo e varia a cada
    geração**, e reescrever prosa em código produziria frase de robô. O que o
    código pode garantir é que a perda não aconteça em silêncio — que é o mesmo
    critério do filtro de ruído da transcrição.

    Só nome próprio entra na conta (`_PARECE_NOME_PROPRIO`): cobrar "backend" ou
    "APIs" no resumo é cobrar prosa, e aí o aviso vira ruído.
    """
    pedido = _pedido_pela_vaga(requisitos)
    resumo = normalizar(curriculo.resumo or "")
    faltando = [
        i
        for i in curriculo.competencias_planas
        if _casa_com_a_vaga(i, pedido)
        and _PARECE_NOME_PROPRIO.search(i)
        and not ats.contem_termo(normalizar(i), resumo)
    ]
    return faltando[:n]


# Nome próprio de tecnologia: tem maiúscula no meio, dígito ou símbolo. "AWS
# Bedrock" e "pgvector" entram; "backend de alta performance" não.
_PARECE_NOME_PROPRIO = re.compile(r"[A-Z0-9+#.]")


def _tem_numero(bullets: list[str]) -> bool:
    return any(any(c.isdigit() for c in b) for b in bullets or [])


def _avisos_de_ats(
    fatos: Fatos, curriculo: Curriculo, requisitos: Requisitos | None = None
) -> list[str]:
    """O que um parser de 2026 penaliza e só o Pablo pode consertar."""
    avisos = []

    # Campo faltando derruba o score direto, e localização é filtro ativo: parte
    # dos ATS elimina por cidade antes de qualquer leitura do conteúdo.
    contato = fatos.perfil.contato or {}
    faltando = [c for c in ("telefone", "localizacao", "email") if not contato.get(c)]
    if faltando:
        avisos.append(
            f"contato sem {', '.join(faltando)} — campo faltando é score perdido "
            "(edite `contato` em data/perfil_mestre.json)"
        )

    for e in curriculo.experiencias:
        periodo = str(e.get("periodo") or "")
        if not periodo:
            avisos.append(f"{e.get('empresa')}: sem período — parte dos ATS recusa automaticamente")
        elif not _TEM_MES.search(periodo):
            avisos.append(f"{e.get('empresa')}: período '{periodo}' sem mês (use '01/2025 – 12/2025')")

    # A seção que mais pesa é a de experiência, e é a que costuma ficar sem
    # número — o contrário do que se espera. Bullet quantificado vira dado
    # comparável entre candidatos; bullet genérico vira texto.
    for e in curriculo.experiencias:
        if not _tem_numero(e.get("bullets") or []):
            avisos.append(
                f"{e.get('empresa')}: nenhum bullet com número — é a seção que mais pesa"
            )

    sem_numero = [p["nome"] for p in curriculo.projetos if not _tem_numero(p.get("bullets"))]
    if sem_numero:
        avisos.append(f"sem número de resultado: {', '.join(sem_numero)}")
    if requisitos is not None and (fora := _fora_do_resumo(curriculo, requisitos)):
        avisos.append(
            "termo que a vaga pede e o resumo não usa: "
            + ", ".join(fora)
            + " — está só nas competências, que é a metade fria da página"
        )

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
        # O título é o do anúncio, letra por letra — não o que o modelo acha
        # que o cargo é. "Desenvolvedor de IA" e "Engenheiro de IA" são a mesma
        # vaga para mim e strings diferentes para o filtro, e quem decide qual
        # das duas ranqueia é quem escreveu o anúncio.
        titulo=str(titulo_vaga or "").strip()[:120],
        formacao=[_com_periodo(f) for f in fatos.perfil.formacao or []],
        certificacoes=_selecionar_certificacoes(fatos, requisitos),
    )

    topo = await _chamar(PROMPT_TOPO.format(**contexto), SCHEMA_TOPO, "topo")
    bullets = await _chamar(
        PROMPT_BULLETS.format(**contexto, voz=voz), SCHEMA_BULLETS, "bullets"
    )

    curriculo.resumo = _resumo_limpo(topo.get("resumo"), fatos, curriculo, extras)
    curriculo.competencias = _competencias_limpas(topo.get("competencias"), fatos, requisitos)
    curriculo.experiencias = _experiencias_limpas(
        bullets.get("experiencias"), fatos, curriculo, extras
    )
    curriculo.projetos = _projetos_limpos(bullets.get("projetos"), fatos, curriculo, extras)
    # Depois dos bullets, e não junto das competências: a regra da categoria
    # órfã só é segura se souber o que o resto do documento já diz, e o resto
    # do documento só existe agora.
    curriculo.competencias = _sem_categoria_orfa(
        curriculo.competencias,
        _pedido_pela_vaga(requisitos),
        _texto_de_apoio(curriculo),
    )
    curriculo.avisos = _avisos_de_ats(fatos, curriculo, requisitos)
    _expandir_siglas(curriculo)

    if curriculo.rejeitados:
        logger.warning(
            f"Anti-alucinação derrubou {len(curriculo.rejeitados)}: "
            f"{', '.join(curriculo.rejeitados[:5])}"
        )
    return curriculo


def _com_periodo(entrada: dict) -> dict:
    """A mesma entrada com a data no formato único: `MM/AAAA – MM/AAAA`.

    O ATS calcula tempo de casa e procura lacunas; "abr/2025" numa entrada e
    "08/2024" na outra faz ele errar a conta ou desistir da entrada.
    """
    saida = dict(entrada)
    if saida.get("periodo"):
        saida["periodo"] = ats.periodo(saida["periodo"])
    return saida


def _expandir_siglas(curriculo: Curriculo) -> None:
    """Escreve o extenso de cada sigla na primeira vez que ela aparece.

    Na ORDEM EM QUE O DOCUMENTO É IMPRESSO — resumo, experiência, projetos. Um
    ATS não semântico procura a string "Retrieval-Augmented Generation" e não
    acha "RAG"; um semântico casa os dois. Escrever as duas formas atende os
    dois, e o custo é uma linha mais longa no resumo.

    Uma vez cada, e no topo: repetir o extenso em todo bullet é exatamente o
    padrão de repetição que os sistemas de 2026 marcam como manipulação.

    **Competência fica de fora.** Ali o item não é prosa, é um termo — e
    "Ollama / LLM (Large Language Model) local" parte o termo no meio,
    destruindo o casamento exato que é a razão de a seção existir. O extenso
    entra no resumo, que o parser lê do mesmo jeito.
    """
    expandir = ats.expansor()
    curriculo.resumo = expandir(curriculo.resumo)
    for entrada in curriculo.experiencias + curriculo.projetos:
        entrada["bullets"] = [expandir(b) for b in entrada.get("bullets") or []]


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


def _pedido_pela_vaga(requisitos: Requisitos) -> set[str]:
    termos = {normalizar(t) for t in requisitos.stack}
    termos |= {normalizar(r) for r in requisitos.obrigatorios + requisitos.desejaveis}
    return {t for t in termos if t and t not in ("",)}


def _casa_com_a_vaga(nome: str, pedido: set[str]) -> bool:
    n = normalizar(nome)
    return any(_mesmo_termo(n, p) for p in pedido)


def _agrupar_por_taxonomia(nomes: list[str], requisitos: Requisitos) -> list[dict]:
    """Os itens escolhidos, distribuídos nas categorias canônicas de `ats.py`.

    **Quem escolhe é o modelo; onde cada um mora é tabela.** O modelo leu a
    vaga e sabe o que importa ali — mas o rótulo que ele inventa mistura
    categorias ("Agentes e Aplicações" com Next.js, Docker e Playwright
    dentro), e a triagem por skills lê o rótulo como declaração sobre o item.

    Dentro do grupo e entre os grupos, o que a vaga pediu vem primeiro:
    palavra-chave no começo da lista pesa mais que a mesma palavra enterrada no
    fim de trinta itens.
    """
    pedido = _pedido_pela_vaga(requisitos)
    grupos: dict[str, list[str]] = {}
    # `separar_pares` antes de categorizar: "React / Next.js" é um item só para
    # o casador de skills do ATS e são duas tecnologias para a triagem. Depois
    # de separadas, cada uma ainda é classificada pelo próprio nome — e as duas
    # podem cair em categorias diferentes, que é o certo.
    for nome in ats.separar_pares(nomes):
        grupos.setdefault(ats.categoria_de(nome), []).append(nome)

    ordem_canonica = {c: i for i, c in enumerate(ats.CATEGORIAS)}
    for itens in grupos.values():
        itens.sort(key=lambda i: not _casa_com_a_vaga(i, pedido))

    # A ordem das categorias é a canônica de `ats.CATEGORIAS`, que é
    # posicionamento — ver o comentário lá. Ordenar por número de itens que
    # casam parecia relevância e era sorteio: na vaga da Accenture uma
    # categoria ganhava a primeira linha por UM item, com todas as outras em
    # zero. A relevância continua mandando dentro da linha, logo acima.
    ordenados = sorted(grupos, key=lambda c: ordem_canonica.get(c, len(ordem_canonica)))
    saida = [
        {"categoria": c, "itens": grupos[c][:MAX_ITENS_CATEGORIA]} for c in ordenados
    ][:MAX_GRUPOS_COMPETENCIA]
    return saida


def _texto_de_apoio(c: Curriculo) -> str:
    """Tudo que o currículo diz FORA da seção de competências.

    É contra isto que a categoria órfã é conferida: se o termo já está num
    bullet, tirá-lo da lista de competências não custa a palavra-chave.
    """
    partes = [c.resumo]
    for entrada in (*c.experiencias, *c.projetos):
        partes += entrada.get("bullets") or []
        partes += [entrada.get("empresa", ""), entrada.get("nome", "")]
        partes += entrada.get("stack") or []
    return " ".join(str(p) for p in partes if p)


def _sem_categoria_orfa(grupos: list[dict], pedido: set[str], resto_do_texto: str) -> list[dict]:
    """Tira a categoria de um item só que não interessa à vaga — se o termo já
    aparece em outro lugar do currículo.

    `Ferramentas: Zoho One` é uma linha inteira, com rótulo e tudo, para um
    termo que a vaga não pediu. Um cabeçalho de categoria com um item só chama
    atenção para o que tem menos a ver com a vaga, e ocupa uma das poucas linhas
    da seção mais lida.

    **A condição do "já aparece em outro lugar" é o que torna isto seguro.**
    "Zoho One" está no bullet da Sechat ("Administrei o Zoho One de uma operação
    de 16 funcionários"), então tirá-lo daqui não some com a palavra-chave do
    documento — só com a linha fraca. Se o termo não estivesse em mais lugar
    nenhum, perder a palavra-chave seria pior que a linha feia, e a categoria
    fica.
    """
    saida = []
    for g in grupos:
        itens = g.get("itens") or []
        orfa = (
            len(itens) == 1
            and not _casa_com_a_vaga(itens[0], pedido)
            and _mencionado(itens[0], resto_do_texto)
        )
        if not orfa:
            saida.append(g)
    return saida


def _mencionado(termo: str, texto: str) -> bool:
    """O termo aparece neste texto, por palavra inteira?"""
    n = normalizar(termo)
    return bool(n) and bool(re.search(rf"(?<![\w+#]){re.escape(n)}(?![\w+#])", normalizar(texto)))


def _agrupar_por_padrao(fatos: Fatos, requisitos: Requisitos) -> list[dict]:
    """Fallback sem modelo: todas as habilidades do perfil, na mesma taxonomia."""
    nomes = [h.get("nome", "") for h in fatos.habilidades if h.get("nome")]
    return _agrupar_por_taxonomia(nomes, requisitos) or [
        {"categoria": "Competências", "itens": nomes[:14]}
    ]


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


def _itens_aprovados(bruto, fatos: Fatos) -> list[str]:
    """As habilidades que o modelo escolheu, sem repetição e sem nome de projeto.

    Três filtros que o `conheco()` sozinho não faz, porque a lista branca da
    anti-alucinação é deliberadamente generosa — ela responde *"isto é verdade?"*,
    e aqui a pergunta é outra: *"isto é uma competência?"*.

    1. **Nome de projeto não é habilidade.** "Churn Prediction" na linha de
       Ciência de Dados faz o recrutador procurar uma tecnologia que não existe.
       O projeto tem seção própria, com bullets.
    2. **Sem repetir.** O mesmo termo em dois grupos não dobra a chance no ATS:
       parece revisão malfeita. Como a categoria passou a ser decidida por
       código, a lista sai plana daqui e a repetição morre na origem.
    3. **Sem o mesmo termo escrito de dois jeitos.** "Machine Learning
       (scikit-learn)" e "scikit-learn" lado a lado é o mesmo termo duas vezes —
       fica o mais informativo, que é o mais longo.
    """
    projetos = {normalizar(p.get("nome", "")) for p in fatos.projetos}
    escolhidos: dict[str, str] = {}      # normalizado → como foi escrito

    for g in bruto:
        if not isinstance(g, dict):
            continue
        for item in g.get("itens") or []:
            nome = str(item.get("nome") if isinstance(item, dict) else item or "").strip()
            n = normalizar(nome)
            # Competência é a mais fácil de inventar e a mais lida pelo ATS.
            if not nome or not n or not fatos.conheco(nome) or n in projetos:
                continue
            colisao = next((visto for visto in escolhidos if _mesmo_termo(visto, n)), None)
            if colisao:
                if len(n) > len(colisao):
                    # Troca preservando a posição: a ordem é a relevância que o
                    # modelo leu na vaga, e reordenar aqui a jogaria fora.
                    escolhidos = {
                        (n if k == colisao else k): (nome if k == colisao else v)
                        for k, v in escolhidos.items()
                    }
                continue
            escolhidos[n] = nome

    return list(escolhidos.values())


def _competencias_limpas(bruto, fatos: Fatos, requisitos: Requisitos) -> list[dict]:
    """A seção de competências: itens do modelo, categorias do código."""
    if not isinstance(bruto, list) or not bruto:
        return _agrupar_por_padrao(fatos, requisitos)

    nomes = _itens_aprovados(bruto, fatos)
    return _agrupar_por_taxonomia(nomes, requisitos) or _agrupar_por_padrao(fatos, requisitos)


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


def _bullets_do_perfil(descricao: str | None) -> list[str]:
    """A descrição do perfil virando bullets — quando o modelo não entregou nada.

    Uma frase por bullet, e cada uma passa pela conversão de voz. Antes o
    fallback era a descrição INTEIRA num bullet só: um parágrafo de quatro
    linhas com um marcador na frente, que o recrutador pula e o parser conta
    como uma realização única — na seção que mais pesa.
    """
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", str(descricao or "")) if f.strip()]
    return [primeira_pessoa(f) for f in frases][:MAX_BULLETS]


def _empresa_conhecida(escrita: str, por_empresa: dict[str, dict]) -> str | None:
    """A chave do perfil que esta empresa escrita pelo modelo designa.

    Casamento exato primeiro; depois, o nome do perfil **contido** no que o
    modelo escreveu. O segundo caminho existe porque o modelo junta cargo e
    empresa quando o nome da empresa não parece nome de empresa: com a entrada
    "Desenvolvedor — Projetos de IA e Automação | Autônomo", ele devolveu
    `empresa: "Projetos de IA e Automação na Autônomo"`, e a experiência inteira
    era rejeitada por não bater string com string.

    Rejeitar aqui não protege de invenção — empresa, cargo e período vêm do
    perfil de qualquer jeito, algumas linhas abaixo. O único efeito era perder
    os bullets e cair para o texto cru da descrição.
    """
    n = normalizar(escrita)
    if not n:
        return None
    if n in por_empresa:
        return n
    return next(
        (chave for chave in por_empresa if chave and ats.contem_termo(chave, n)),
        None,
    )


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
        chave = _empresa_conhecida(item.get("empresa", ""), por_empresa)
        if chave is None:
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
                "periodo": ats.periodo(e.get("periodo")),
                # Sem bullets aprovados, o texto do perfil é melhor que nada.
                "bullets": bullets or _bullets_do_perfil(e.get("descricao")),
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
                # A prova é a linha com número — entra sempre, e o que sobra de
                # espaço fica para a descrição, uma frase por bullet.
                "bullets": (
                    _bullets_do_perfil(p.get("descricao"))[: MAX_BULLETS - 1]
                    + ([p["prova"]] if p.get("prova") else [])
                ),
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
        ats.SEP_CAMPO.join(
            f"{rotulo}: {re.sub(r'^https?://', '', v).rstrip('/')}"
            for rotulo, v in ats.contato_ordenado(contato)
        ),
        "",
        "RESUMO",
        c.resumo,
        "",
        "COMPETÊNCIAS",
    ]
    linhas += [
        f"{g['categoria']}: {ats.SEP_LISTA.join(g['itens'])}" for g in c.competencias
    ]

    linhas += ["", "EXPERIÊNCIA PROFISSIONAL"]
    for e in c.experiencias:
        linhas.append(
            f"{e.get('cargo')}{ats.SEP_CAMPO}{e.get('empresa')} ({e.get('periodo')})"
        )
        linhas += [f"  - {b}" for b in e.get("bullets", [])]

    linhas += ["", "PROJETOS"]
    for projeto in c.projetos:
        linhas.append(
            f"{projeto['nome']}{ats.SEP_CAMPO}"
            f"{ats.SEP_LISTA.join(projeto.get('stack') or [])}"
        )
        linhas += [f"  - {b}" for b in projeto["bullets"]]

    linhas += ["", "FORMAÇÃO"]
    linhas += [
        f"{f.get('instituicao')}{ats.SEP_CAMPO}{f.get('curso')} ({f.get('periodo')})"
        for f in c.formacao
    ]
    if c.certificacoes:
        linhas += ["", "CERTIFICAÇÕES"]
        linhas += [
            f"{cert.get('nome')}"
            + (f"{ats.SEP_CAMPO}{cert.get('instituicao')}" if cert.get("instituicao") else "")
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

# O `·` continua aqui de propósito: currículo gravado antes da troca de
# separador tem que voltar a ser lido. Ler o formato antigo é de graça;
# perder o texto que eu editei, não.
_CAMPOS_TEXTO = re.compile(r"\s*[|·—]\s*")
_ITENS_TEXTO = re.compile(r"\s*[,·]\s*")


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
            valores = [i.strip() for i in _ITENS_TEXTO.split(itens) if i.strip()]
            if categoria.strip() and valores:
                competencias.append({"categoria": categoria.strip(), "itens": valores})
        elif secao == "experiencia profissional":
            # "Cargo | Empresa (período)" — a empresa é a chave.
            campos = _CAMPOS_TEXTO.split(nu)
            empresa = campos[-1].split("(")[0].strip() if len(campos) > 1 else nu
            atual = bullets_exp.setdefault(normalizar(empresa), [])
        elif secao == "projetos":
            nome = _CAMPOS_TEXTO.split(nu)[0].strip()
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
