"""As cinco camadas — a régua que diz se o post já serve a quem vai ler.

O blog tem quatro leitores e eles chegam ao mesmo texto por motivos diferentes
(`docs/fase-blog.md` §2). Um post bom atende os quatro em camadas, na ordem em
que eles desistem de ler:

    abertura    entusiasta   uma cena concreta, não "neste post vou falar"
    resultado   cliente      número com unidade: o antes e o depois
    como        técnico      código, fórmula, estrutura
    prova       recrutador   link, repo, de onde o conhecimento veio
    fechamento  todos        um pedido só

**Todo sinal aqui é mecânico.** "O post é interessante?" não vira sinal, por
mais que seja a pergunta mais importante — checklist que depende de eu julgar
honestamente às 23h é checklist que fica verde sem motivo, e aí ele mente sobre
o post e sobre todos os outros. O que se mede é o que dá para contar: palavras
do primeiro parágrafo, números com unidade, blocos de código, links.

O texto analisado é sempre a **prosa**: código e fórmula saem antes de contar.
Um bloco de código com vinte números não é evidência de resultado nenhum.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

PUBLICOS = ("entusiasta", "cliente", "tecnico", "recrutador", "todos")

# Abertura de quem está aquecendo o motor em vez de começar. Sai da voz.md
# ("a primeira frase menciona algo concreto"), aplicada a post em vez de e-mail.
META_FRASES = (
    "neste post",
    "neste artigo",
    "hoje vou",
    "vou falar",
    "vamos falar",
    "vamos entender",
    "vamos ver",
    "antes de mais nada",
    "como todos sabem",
    "você já deve ter ouvido",
    "no mundo de hoje",
    "com o avanço da",
)

# O pilar do dono de negócio (passo 8.1 do motor comercial) muda duas réguas:
# o "como" deixa de ser código e passa a ser o que ele faz sozinho, e a prosa
# não pode ter jargão sem explicação (`prompts/voz-post-negocio.md`).
PILAR_NEGOCIO = "automacao-negocio"

# Palavra de quem constrói, na frente de quem compra. Explicada logo depois, entre
# parênteses, ela passa: "API oficial da Meta (o jeito que a Meta autoriza...)".
JARGAO = (
    "lead",
    "leads",
    "funil",
    "conversão",
    "churn",
    "chatbot",
    "bot",
    "llm",
    "modelo de linguagem",
    "ia generativa",
    "rag",
    "embedding",
    "prompt",
    "token",
    "tokens",
    "api",
    "webhook",
    "backend",
    "deploy",
    "pipeline",
    "dashboard",
    "stack",
    "saas",
    "onboarding",
)
_JARGAO = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in sorted(JARGAO, key=len, reverse=True)) + r")\b"
    r"(?!\w)(?P<explicada>(?:\s+[\w-]+){0,3}\s*\()?",
    re.IGNORECASE,
)
PASSOS_MIN = 3
_PASSO = re.compile(r"^\s*\d+[.)]\s+\S", re.MULTILINE)
_BLOCO_TEXTO = re.compile(r"^```text\b", re.MULTILINE)

ABERTURA_MAX_PALAVRAS = 60
MIN_NUMEROS = 2
MIN_SUBTITULOS = 2
MIN_TAGS = 2

# Número que carrega unidade. "60 vezes mais barato" e "0,2 s" contam; "3" solto
# não, porque numeral sem unidade é quase sempre enumeração ("3 motivos").
_NUMERO_COM_UNIDADE = re.compile(
    r"(?:R\$\s*\d|\b\d+(?:[.,]\d+)?\s*"
    r"(?:%|×|x\b|ms\b|s\b|min\b|h\b|GB\b|MB\b|KB\b|tok/s|"
    r"reais\b|vezes\b|dias?\b|semanas?\b|mes(?:es)?\b|anos?\b|"
    r"linhas?\b|testes?\b|posts?\b|perguntas?\b|chamadas?\b|tokens?\b))",
    re.IGNORECASE,
)
_FRACAO = re.compile(r"\b\d+\s*/\s*\d+\b")            # "12/12" na avaliação
_DE_PARA = re.compile(r"\bde\s+\d[^.]{0,40}?\bpara\s+\d", re.IGNORECASE)

_FENCE = re.compile(r"^```", re.MULTILINE)
_BLOCO_CODIGO = re.compile(r"```.*?```", re.DOTALL)
_CODIGO_INLINE = re.compile(r"`[^`\n]+`")
_FORMULA_BLOCO = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_COMENTARIO_MDX = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
_LINK_MD = re.compile(r"\[[^\]]*\]\((https?://[^)]+)\)")
_LINK_HTML = re.compile(r'href="(https?://[^"]+)"')
# Para o fechamento, link interno conta: "[me chama](/contato)" é a chamada mais
# importante do blog, e ela nunca é http. Para a camada `prova`, não conta — lá
# o que vale é a fonte de fora, que é o que o leitor pode conferir.
_LINK_QUALQUER = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_CTA = re.compile(r"<CTA\b")


@dataclass
class Sinal:
    ok: bool
    texto: str
    # O que fazer quando está vermelho. Sinal que só diz "faltou" obriga a
    # lembrar a regra; a regra mora aqui, não na minha cabeça.
    dica: str | None = None


@dataclass
class Camada:
    id: str
    rotulo: str
    publico: str
    pergunta: str
    sinais: list[Sinal] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.sinais)


def prosa(corpo: str) -> str:
    """O texto sem código, fórmula nem comentário — o que o leitor lê como frase."""
    limpo = _COMENTARIO_MDX.sub("", corpo)
    limpo = _BLOCO_CODIGO.sub("", limpo)
    limpo = _FORMULA_BLOCO.sub("", limpo)
    return _CODIGO_INLINE.sub("", limpo)


def paragrafos(corpo: str) -> list[str]:
    """Os blocos de prosa, na ordem. Título, lista e citação não entram."""
    blocos: list[str] = []
    for bruto in prosa(corpo).split("\n\n"):
        bloco = bruto.strip()
        if not bloco or bloco.startswith(("#", ">", "-", "*", "|", "import ", "export ")):
            continue
        blocos.append(bloco)
    return blocos


def abertura_bloco(corpo: str) -> str:
    """O parágrafo de abertura: o que vem **antes do primeiro subtítulo**.

    Não é "o primeiro parágrafo que existir". Post que abre com `## Contexto`
    joga o leitor dentro de uma seção antes de lhe dar um motivo para ficar —
    e, se a busca continuasse depois do título, o primeiro parágrafo da primeira
    seção passaria por abertura e a camada ficaria verde num post sem abertura
    nenhuma.
    """
    for bruto in prosa(corpo).split("\n\n"):
        bloco = bruto.strip()
        if not bloco or bloco.startswith(("import ", "export ")):
            continue
        if bloco.startswith("#"):
            return ""
        if bloco.startswith((">", "-", "*", "|")):
            continue
        return bloco
    return ""


def palavras(texto: str) -> int:
    return len([p for p in re.split(r"\s+", prosa(texto).strip()) if p])


def minutos_de_leitura(corpo: str) -> int:
    """Mesma conta do blog: 200 palavras por minuto, mínimo de 1."""
    return max(1, round(palavras(corpo) / 200))


def _numeros(texto: str) -> int:
    p = prosa(texto)
    return (
        len(_NUMERO_COM_UNIDADE.findall(p))
        + len(_FRACAO.findall(p))
        + len(_DE_PARA.findall(p))
    )


def _links(texto: str) -> list[str]:
    p = prosa(texto)
    return _LINK_MD.findall(p) + _LINK_HTML.findall(p)


def jargao(corpo: str) -> list[str]:
    """As palavras de `JARGAO` na prosa, sem explicação entre parênteses logo depois.

    "Logo depois" é até três palavras: "API oficial da Meta (…)" explica a API.
    Sem repetição, na ordem em que aparecem.
    """
    achadas: list[str] = []
    for m in _JARGAO.finditer(prosa(corpo)):
        termo = m.group(1).lower()
        if not m.group("explicada") and termo not in achadas:
            achadas.append(termo)
    return achadas


def analisar(
    *,
    corpo: str,
    descricao: str | None = None,
    tags: list[str] | None = None,
    origem: list[dict] | None = None,
    pilar: str | None = None,
) -> list[Camada]:
    """As cinco camadas do post, cada uma com os sinais que a sustentam.

    No pilar do dono de negócio, o "como" mede passo a passo ou texto pronto em
    vez de código, e o "resultado" ganha o sinal de jargão.
    """
    negocio = pilar == PILAR_NEGOCIO
    tags = tags or []
    origem = origem or []
    blocos = paragrafos(corpo)
    primeiro = abertura_bloco(corpo)
    ultimo = blocos[-1] if blocos else ""
    links = _links(corpo)

    # ── entusiasta: ele decide no primeiro parágrafo ──────────────────
    n_abertura = len(primeiro.split()) if primeiro else 0
    meta = next((m for m in META_FRASES if primeiro.lower().lstrip("*_# ").startswith(m)), None)
    abertura = Camada(
        id="abertura",
        rotulo="Abertura concreta",
        publico="entusiasta",
        pergunta="Dá vontade de ler o segundo parágrafo?",
        sinais=[
            Sinal(
                ok=bool(primeiro),
                texto="tem parágrafo de abertura" if primeiro else "o post começa num subtítulo",
                dica="escreva o primeiro parágrafo antes de qualquer `##`",
            ),
            Sinal(
                ok=bool(primeiro) and n_abertura <= ABERTURA_MAX_PALAVRAS,
                texto=f"primeiro parágrafo com {n_abertura} palavras (máx. {ABERTURA_MAX_PALAVRAS})",
                dica="corte até caber: a abertura é uma cena, não o resumo do post",
            ),
            Sinal(
                ok=meta is None,
                texto="não começa com meta-frase" if meta is None else f"começa com {meta!r}",
                dica='comece pelo fato ("Perguntei ao assistente X e ele respondeu Y"), não pelo aviso do que você vai fazer',
            ),
        ],
    )

    # ── cliente: ele quer o antes e o depois ──────────────────────────
    n_num = _numeros(corpo)
    d = len((descricao or "").strip())
    resultado = Camada(
        id="resultado",
        rotulo="Problema e resultado",
        publico="cliente",
        pergunta="Isso resolveu o quê, e quanto?",
        sinais=[
            Sinal(
                ok=n_num >= MIN_NUMEROS,
                texto=f"{n_num} número(s) com unidade na prosa (mín. {MIN_NUMEROS})",
                dica='troque o adjetivo pelo número: "de 3 min para 75 s" no lugar de "bem mais rápido"',
            ),
            Sinal(
                ok=50 <= d <= 160,
                texto=f"descrição com {d} caracteres (50 a 160)",
                dica="é o texto do card, da busca e do compartilhamento — escreva o resultado, não o tema",
            ),
        ],
    )
    if negocio:
        termos = jargao(corpo)
        resultado.sinais.append(
            Sinal(
                ok=not termos,
                texto="sem jargão" if not termos else f"jargão: {', '.join(termos)}",
                dica='troque pela palavra do dono ("paciente novo", e não "lead") ou explique entre parênteses na primeira vez',
            )
        )

    # ── técnico: ele quer conseguir repetir ───────────────────────────
    # (no pilar de negócio, quem repete é o dono: passo a passo ou texto pronto)
    n_subtitulos = len(re.findall(r"^##\s+\S", corpo, re.MULTILINE))
    subtitulos = Sinal(
        ok=n_subtitulos >= MIN_SUBTITULOS,
        texto=f"{n_subtitulos} subtítulo(s) ## (mín. {MIN_SUBTITULOS})",
        dica="quem lê na diagonal lê os subtítulos; sem eles o post é um bloco",
    )
    if negocio:
        n_passos = len(_PASSO.findall(_BLOCO_CODIGO.sub("", corpo)))
        tem_texto = bool(_BLOCO_TEXTO.search(corpo))
        como = Camada(
            id="como",
            rotulo="Como fazer",
            publico="cliente",
            pergunta="Dá para fazer amanhã, sem me contratar?",
            sinais=[
                Sinal(
                    ok=n_passos >= PASSOS_MIN or tem_texto,
                    texto=(
                        "tem texto pronto para copiar"
                        if tem_texto
                        else f"{n_passos} passo(s) numerado(s) (mín. {PASSOS_MIN}, ou um bloco ```text)"
                    ),
                    dica="dê o que ele faz sozinho: os passos numerados ou o texto inteiro, pronto para colar",
                ),
                subtitulos,
            ],
        )
    else:
        tem_codigo = bool(_FENCE.search(corpo)) or bool(_FORMULA_BLOCO.search(corpo))
        como = Camada(
            id="como",
            rotulo="Como foi feito",
            publico="tecnico",
            pergunta="Como foi feito? Eu conseguiria repetir?",
            sinais=[
                Sinal(
                    ok=tem_codigo,
                    texto="tem bloco de código ou fórmula" if tem_codigo else "sem código nem fórmula",
                    dica="um trecho de código real, com o nome das coisas, é o que separa post técnico de resenha",
                ),
                subtitulos,
            ],
        )

    # ── recrutador: ele quer saber se você fez mesmo ──────────────────
    tem_repo = any("github.com" in u or "gitlab.com" in u for u in links)
    prova = Camada(
        id="prova",
        rotulo="Prova e origem",
        publico="recrutador",
        pergunta="Quem escreveu isso sabe fazer, ou só sabe falar?",
        sinais=[
            Sinal(
                ok=bool(links),
                texto=f"{len(links)} link(s) externo(s)",
                dica="afirmação sem fonte é opinião; link para o repo, o paper ou a doc",
            ),
            Sinal(
                ok=bool(origem) or tem_repo,
                texto="tem origem registrada ou link de repositório",
                dica="preencha 'origem' (nota do vault ou doc de fase) — é o que permite revisar o post quando a fonte mudar",
            ),
            Sinal(
                ok=len(tags) >= MIN_TAGS,
                texto=f"{len(tags)} tag(s) (mín. {MIN_TAGS})",
                dica="a tag é como o leitor acha o resto do assunto no blog",
            ),
        ],
    )

    # ── todos: o que ele faz agora ────────────────────────────────────
    ctas_no_fim = len(_LINK_QUALQUER.findall(ultimo)) + len(_CTA.findall(ultimo))
    fechamento = Camada(
        id="fechamento",
        rotulo="Fechamento",
        publico="todos",
        pergunta="E agora, o que o leitor faz?",
        sinais=[
            Sinal(
                ok=ctas_no_fim >= 1,
                texto="o fim tem link ou <CTA>" if ctas_no_fim else "o post acaba sem chamada",
                dica="feche com um pedido: ler o repo, falar comigo, ler o post seguinte",
            ),
            Sinal(
                ok=ctas_no_fim <= 1,
                texto=f"{ctas_no_fim} chamada(s) no último parágrafo (máx. 1)",
                dica="um único pedido no final, nunca dois — é a regra da voz.md",
            ),
        ],
    )

    return [abertura, resultado, como, prova, fechamento]


def tudo_verde(camadas: list[Camada]) -> bool:
    return all(c.ok for c in camadas)


def o_que_falta(camadas: list[Camada]) -> list[str]:
    """Os sinais vermelhos, em uma linha cada — o que a tela mostra no topo."""
    return [f"{c.rotulo}: {s.texto}" for c in camadas for s in c.sinais if not s.ok]


# O marcador que a geração escreve onde a matéria-prima não tem o fato
# (`app/blog/geracao.py`). Aberto, ele bloqueia o `pronto` — e quebraria o build
# do MDX de qualquer jeito, porque `{{` é expressão JS para o compilador.
FALTA = re.compile(r"\{\{\s*FALTA\s*:([^}]*)\}\}")


def faltas(corpo: str) -> list[str]:
    """Os `{{FALTA: …}}` ainda abertos, na ordem do texto."""
    return [m.strip() for m in FALTA.findall(corpo or "")]
