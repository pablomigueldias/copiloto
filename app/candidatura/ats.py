"""As regras de escrita que o parser impõe ao texto — e que nenhum modelo garante.

`pdf.py` cuida da **forma** (uma coluna, sem tabela, sem ícone). Aqui mora o que
o parser cobra do **conteúdo**, e que um LLM erra de um jeito diferente a cada
chamada:

| O que o ATS penaliza | O que este módulo faz |
|---|---|
| data em formatos misturados | `periodo()` normaliza tudo para `MM/AAAA – MM/AAAA` |
| sigla sem o termo por extenso | `expansor()` escreve o extenso na 1ª ocorrência |
| rótulo de habilidade que mistura categorias | `categoria_de()` reclassifica |
| separador exótico entre termos | `SEP_LISTA` / `SEP_CAMPO` |

Tudo é código puro. Pedir ao modelo "use sempre MM/AAAA" reduz a frequência do
erro; normalizar depois elimina — a mesma divisão de trabalho da anti-alucinação
em `curriculo.py`.
"""
from __future__ import annotations

import re
from collections.abc import Callable

from app.candidatura.perfil import normalizar

# ── Separadores ───────────────────────────────────────────────────
#
# O ponto médio (`·`) saiu. Ele não é ASCII, e o risco é duplo: virar caractere
# de substituição em extração malfeita, ou colar dois termos ("PythonFastAPI")
# quando o extrator descarta o glifo sem pôr espaço no lugar. Uma habilidade
# perdida na seção mais lida pelo ATS é caro demais para um enfeite.
#
# São dois, e a diferença importa: vírgula separa itens do MESMO tipo (é o que
# a triagem por skills espera ler); barra vertical separa CAMPOS diferentes na
# mesma linha. Usar vírgula nos dois casos quebraria justamente o campo novo —
# "Santo André, SP" já tem vírgula dentro, e a linha de contato viraria uma
# lista de seis coisas sem dono.
SEP_LISTA = ", "
SEP_CAMPO = " | "

# ── Contato ───────────────────────────────────────────────────────
#
# Rótulo escrito, não ícone: ícone vira caractere estranho no parser. Aqui e não
# em `pdf.py` porque o texto que eu reviso na fila TEM que ser o mesmo documento
# que sai impresso — com o mapa só no PDF, a fila mostrava "localizacao:" e o
# papel mostrava "local:".
#
# A ordem é a do dicionário em `perfil.contato`, e cidade/UF vem primeiro de
# propósito: muitos ATS filtram por localização antes de ler qualquer outra
# coisa, e palavra-chave no começo pesa mais que a mesma palavra no fim.
ROTULOS_CONTATO = {
    "localizacao": "local",
    "telefone": "tel",
    "email": "email",
    "linkedin": "linkedin",
    "github": "github",
    "portfolio": "site",
}


def indivisivel(texto: str) -> str:
    """O texto com espaço fixo (`\xa0`), para o PDF não quebrá-lo em duas linhas.

    **O defeito que isto conserta é o mesmo em três lugares.** O `reportlab`
    quebra a linha em qualquer espaço, e o extrator de texto lê as duas metades
    como coisas diferentes:

    | onde | como saía do `pdftotext` | o que se perde |
    |---|---|---|
    | formação | `(08/2024 –` / `12/2026)` | a data, cuja ausência derruba a entrada |
    | contato | `linkedin:` / `www.linkedin.com/…` | o rótulo perde o valor |
    | competência | `Machine` / `Learning (scikit-learn)` | metade de uma skill |

    A regra geral: **o que é um campo tem que caber inteiro numa linha.** A
    quebra continua acontecendo, só que nos separadores — entre um campo e o
    seguinte (`SEP_CAMPO`) ou entre um item e o próximo (`SEP_LISTA`), que é
    onde ela não custa nada.

    O `\xa0` sai do PDF como espaço comum (conferido com `pdftotext`), então não
    é caractere estranho para ninguém: só impede a quebra.
    """
    return str(texto or "").replace(" ", "\xa0")


def contato_ordenado(contato: dict) -> list[tuple[str, str]]:
    """`[(rótulo, valor)]` na ordem do ATS — e não na que o banco devolveu.

    **A ordem não sobrevive ao armazenamento.** `perfil_mestre.contato` é uma
    coluna `jsonb`, e o Postgres guarda chave de objeto ordenada por tamanho e
    depois por byte: o que entra como `localizacao, telefone, email, linkedin,
    github` volta como `email, github, linkedin, telefone, localizacao`. Quem
    itera `contato.items()` herda essa ordem sem perceber, e foi o que
    aconteceu — o PDF saía com o e-mail na frente e a cidade no fim.

    Isso custa: muitos ATS filtram por localização antes de ler qualquer outra
    coisa, e palavra-chave no começo da linha pesa mais que a mesma palavra no
    fim. `ROTULOS_CONTATO` **é** a ordem pretendida, então ela manda aqui.

    Chave que não está no mapa vai para o fim, com o nome que tem: perder um
    contato porque ninguém cadastrou o rótulo seria pior que exibi-lo cru.
    """
    limpo = {k: str(v).strip() for k, v in (contato or {}).items() if str(v or "").strip()}
    conhecidas = [(r, limpo[k]) for k, r in ROTULOS_CONTATO.items() if k in limpo]
    extras = [(k, v) for k, v in limpo.items() if k not in ROTULOS_CONTATO]
    return conhecidas + extras


# ── Datas ─────────────────────────────────────────────────────────
#
# O ATS calcula tempo de casa e procura lacunas na carreira. Misturar
# "abr/2025" com "08/2024" faz o parser errar a conta ou desistir da entrada — e
# entrada de experiência sem data legível é recusa automática em vários
# sistemas.

_MESES = {
    "jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2, "mar": 3, "marco": 3,
    "abr": 4, "abril": 4, "mai": 5, "maio": 5, "jun": 6, "junho": 6,
    "jul": 7, "julho": 7, "ago": 8, "agosto": 8, "set": 9, "sep": 9,
    "setembro": 9, "out": 10, "outubro": 10, "nov": 11, "novembro": 11,
    "dez": 12, "dezembro": 12,
}

# "atual" é informação, não buraco: o parser entende que o vínculo está aberto.
_ABERTO = {"atual", "atualmente", "presente", "hoje", "momento", "now", "present"}

# O travessão da saída. É o que o recrutador espera ver num intervalo de datas,
# e — ao contrário do `·` entre termos — não corre risco de colar dois números:
# ele está cercado de espaços e os dois lados são dígitos.
_TRAVESSAO = " – "

# Só corta onde há espaço dos dois lados, para não picar "04/2025" no hífen.
_INTERVALO = re.compile(r"\s+[–—-]\s+|\s+(?:a|at[ée])\s+", re.IGNORECASE)
_DOIS_ANOS = re.compile(r"^\s*(\d{4})\s*[–—/-]\s*(\d{4})\s*$")
# "desde 2023" é vínculo aberto escrito de outro jeito. Sem isto o "desde"
# some na normalização e sobra um ano solto, que o parser lê como data única.
_DESDE = re.compile(r"^\s*(?:desde|a partir de|since)\s+(.+)$", re.IGNORECASE)

_MES_ANO = re.compile(r"\b(\d{1,2})\s*[/.-]\s*(\d{4})\b")
_NOME_ANO = re.compile(r"\b([a-zç]{3,10})\.?\s*(?:de\s+|/|\s)\s*(\d{4})\b", re.IGNORECASE)
_SO_ANO = re.compile(r"\b(\d{4})\b")


def _ponta(texto: str) -> str:
    """Um lado do intervalo → `MM/AAAA`, `AAAA` ou `atual`."""
    nu = normalizar(texto)
    if not nu:
        return ""
    if nu in _ABERTO:
        return "atual"

    if m := _MES_ANO.search(nu):
        mes = int(m.group(1))
        if 1 <= mes <= 12:
            return f"{mes:02d}/{m.group(2)}"
    if m := _NOME_ANO.search(nu):
        if mes := _MESES.get(m.group(1).lower()):
            return f"{mes:02d}/{m.group(2)}"
    if m := _SO_ANO.search(nu):
        # Ano solto continua ano solto: inventar o mês seria mentir uma data, e
        # `_avisos_de_ats` existe justamente para me cobrar o mês que falta.
        return m.group(1)
    return texto.strip()


def periodo(texto: str | None) -> str:
    """`abr/2025 – set/2025` → `04/2025 – 09/2025`. O que não dá para ler volta igual.

    Devolver o original é de propósito: um período escrito de um jeito que eu não
    previ é melhor no currículo do que um campo apagado — e o aviso de ATS
    aponta o que ficou sem mês.
    """
    bruto = str(texto or "").strip()
    if not bruto:
        return ""

    if m := _DOIS_ANOS.match(bruto):
        return f"{m.group(1)}{_TRAVESSAO}{m.group(2)}"
    if m := _DESDE.match(bruto):
        return f"{_ponta(m.group(1))}{_TRAVESSAO}atual"

    pontas = [p for p in _INTERVALO.split(bruto) if p and p.strip()]
    convertidas = [_ponta(p) for p in pontas[:2]]
    convertidas = [c for c in convertidas if c]
    if not convertidas:
        return bruto
    return _TRAVESSAO.join(convertidas)


# ── Siglas ────────────────────────────────────────────────────────
#
# O modelo semântico casa "Retrieval-Augmented Generation" com "RAG", mas nem
# todo ATS é semântico — e o que não é procura a string. Escrever as duas formas
# cobre os dois, e custa cinco palavras.
#
# Só na PRIMEIRA ocorrência: repetir o extenso em todo bullet é exatamente o
# padrão de repetição que os sistemas de 2026 marcam como manipulação.

SIGLAS: dict[str, str] = {
    "LLMs": "Large Language Models",
    "LLM": "Large Language Model",
    "RAG": "Retrieval-Augmented Generation",
    "IA": "Inteligência Artificial",
    "ML": "Machine Learning",
    "CI/CD": "Integração Contínua e Entrega Contínua",
    "RRF": "Reciprocal Rank Fusion",
    "RBAC": "Role-Based Access Control",
    "JWT": "JSON Web Token",
    "2FA": "autenticação de dois fatores",
    "E2E": "ponta a ponta",
    "VPS": "Virtual Private Server",
}

# `API` e `SQL` ficam de fora de propósito: são as duas siglas que todo parser e
# todo recrutador de tecnologia já resolve, e "API (Application Programming
# Interface)" no meio de "APIs REST" só deixa a linha pior.

# Sigla maior primeiro: sem isso "LLM" comeria o começo de "LLMs" e sobraria um
# "s" órfão depois do parêntese.
#
# O `(?:...)` em volta da alternância não é enfeite: `|` tem a precedência mais
# baixa do regex, e sem o grupo os limites de palavra grudariam só na primeira e
# na última sigla — "MIA" virava "M" + "IA (Inteligência Artificial)".
# Termo fixo que COMEÇA com sigla. "IA (Inteligência Artificial) generativa" parte
# a expressão no meio, e é justamente a expressão inteira que a vaga procura. A
# ocorrência é pulada sem ser marcada como vista: se a sigla aparecer sozinha
# depois, aí ela ganha o extenso.
_COMPOSTO = re.compile(r"\s+(generativ[ao]s?|conversacional|local|generalista)\b", re.IGNORECASE)

_ALTERNANCIA = "|".join(re.escape(s) for s in sorted(SIGLAS, key=len, reverse=True))
_SIGLAS_RE = re.compile(rf"(?<![\w-])(?:{_ALTERNANCIA})(?![\w-])")


def expansor() -> Callable[[str], str]:
    """Devolve a função que expande siglas — uma vez cada, ao longo do documento.

    O estado é a razão de ser: "primeira ocorrência" é uma propriedade do
    documento inteiro, não de um bullet. Quem chama percorre as seções na ordem
    em que elas são impressas, e a expansão cai onde o parser mais valoriza — o
    resumo e o primeiro bullet.
    """
    vistas: set[str] = set()

    def expandir(texto: str) -> str:
        if not texto:
            return texto

        def trocar(m: re.Match[str]) -> str:
            sigla = m.group(0)
            if sigla in vistas:
                return sigla
            if _COMPOSTO.match(texto[m.end():]):
                return sigla
            # Já vem com o extenso escrito à mão? Então esta é a ocorrência
            # boa: marca como vista e não mexe.
            depois = texto[m.end():].lstrip()
            vistas.add(sigla)
            if depois.startswith("("):
                return sigla
            return f"{sigla} ({SIGLAS[sigla]})"

        # Sensível a maiúscula: `\bia\b` casaria com o verbo "ia" em português,
        # e `\bml\b` com qualquer lixo. Sigla de currículo é escrita em caixa
        # alta, sempre.
        return _SIGLAS_RE.sub(trocar, texto)

    return expandir


# ── Taxonomia de competências ─────────────────────────────────────
#
# A triagem por skills mapeia esta seção para as categorias internas da vaga
# (Greenhouse e Workday fazem isso antes de qualquer outra leitura). Rótulo que
# mistura categorias — "Agentes e Aplicações" com Next.js, Docker e Playwright
# dentro — classifica mal os três.
#
# Por isso a categoria é decidida por código, não pelo modelo: o modelo escolhe
# QUAIS habilidades entram e em que ordem (é ele que leu a vaga); onde cada uma
# mora é tabela.

FERRAMENTAS = "Ferramentas"

_TABELA: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("IA e Machine Learning", (
        "llms", "rag", "ia", "machine learning", "scikit-learn", "sklearn",
        "pandas", "numpy", "ollama", "prompt", "engenharia de prompt",
        "embeddings", "busca semantica", "sentence-transformers", "bge-m3",
        "gemini", "groq", "openai", "transformers", "nlp", "deep learning",
        "agentes", "langchain", "bedrock", "amazon bedrock", "claude",
        "claude 3 haiku", "ia generativa", "llm local", "llm",
    )),
    ("Dados e Pipelines", (
        "postgresql", "pgvector", "alembic", "redis", "mongodb", "mysql",
        "sqlite", "minio", "s3", "migrations", "versionamento de banco",
        "modelagem de dados", "full-text", "pipeline de dados", "pipelines",
        "pipeline", "ingestao", "indexacao", "etl", "elt", "chunking",
        "data warehouse", "processamento de dados",
    )),
    ("Linguagens", (
        "python", "typescript", "javascript", "sql", "t-sql", "tsql", "java",
        "go", "golang", "c#", "php", "bash", "shell", "html", "css", "html5",
        "css3",
    )),
    ("Frameworks e Arquitetura", (
        "fastapi", "sqlalchemy", "pydantic", "react", "nextjs", "next.js",
        "vue", "django", "flask", "express", "nodejs", "tailwind", "vite",
        "arq", "celery", "api rest", "microsservicos", "microservicos",
        "microservices", "arquitetura de software", "arquitetura",
        "programacao assincrona", "async", "worker assincrono", "worker",
        "event-driven", "orientado a eventos",
    )),
    ("DevOps e Infraestrutura", (
        "docker", "git", "cicd", "linux", "vps", "ssh", "nginx", "aws",
        "step functions", "aws step functions", "lambda", "iam",
        "gcp", "azure", "observabilidade", "monitoramento", "logs",
        "seguranca", "autenticacao", "deploy", "wordpress", "whm", "cpanel",
    )),
    ("Testes, Qualidade e Processo", (
        "pytest", "playwright", "ruff", "lint", "tdd", "code review",
        "scrum", "agile", "kanban", "metodologias ageis",
    )),
)

# **A ordem desta tupla é a ordem impressa, e ela é posicionamento.**
#
# Era relevância: as categorias saíam ordenadas pelo número de itens que casavam
# com a vaga. Medido na vaga da Accenture, isso significou "DevOps" na frente
# por **um** item ("Observabilidade") enquanto todas as outras tinham zero — e a
# primeira linha depois do resumo, num currículo de engenharia de dados,
# abrindo com Docker, WordPress e WHM.
#
# Uma linha decidida por um termo não é relevância, é sorteio. A relevância
# continua mandando **dentro** da linha (o que a vaga pediu vem primeiro entre
# os itens), que é onde ela não depende de empate.
#
# O custo assumido: numa vaga de infraestrutura, DevOps sai em quinto. Os itens
# que a vaga pediu continuam na frente da linha dele, e cinco linhas ainda é o
# topo da página.
CATEGORIAS: tuple[str, ...] = tuple(c for c, _ in _TABELA) + (FERRAMENTAS,)

TAXONOMIA: dict[str, str] = {
    termo: categoria for categoria, termos in _TABELA for termo in termos
}


# ── Barra que junta dois termos ───────────────────────────────────
#
# Medido no currículo da Accenture, com `pdftotext` e um casador de skills:
# **um item é comparado inteiro** contra o dicionário do ATS, e
# `"pandas / numpy"` não é igual a `"pandas"` nem a `"NumPy"`. Os dois somem da
# triagem por skills, apesar de estarem impressos na página.
#
# É o mesmo raciocínio do §2.2: na seção de competências o item não é prosa, é
# um **termo**, e o que vale ali é o casamento exato. Em prosa a barra não
# incomoda; aqui ela custa duas palavras-chave por item.
#
# Só barra **com espaço dos dois lados** é separador. Sem espaço ela faz parte
# do nome, e quebrar destruiria o termo: `ECS/Fargate`, `Linux/SSH`, `CI/CD`,
# `IA/ML`, `E/S`. Essa distinção é a regra inteira.
_BARRA_SEPARADORA = re.compile(r"\s+/\s+")


def separar_pares(itens: list[str]) -> list[str]:
    """`["pandas / numpy"]` → `["pandas", "numpy"]`, sem repetir.

    Um item por termo é o que a triagem por skills espera ler, e é o que o
    `SEP_LISTA` já fazia entre itens — a barra era a mesma junção acontecendo
    *dentro* de um, onde ninguém tinha olhado.
    """
    saida: list[str] = []
    vistos: set[str] = set()
    for item in itens:
        for parte in _BARRA_SEPARADORA.split(str(item or "")):
            parte = parte.strip()
            chave = normalizar(parte)
            if parte and chave not in vistos:
                vistos.add(chave)
                saida.append(parte)
    return saida


def contem_termo(chave: str, texto: str) -> bool:
    """`git` está em `git e versionamento`; não está em `github`.

    Público porque a seleção de certificações precisa da mesma comparação: lá,
    substring fazia "s3" casar dentro de "css3".
    """
    return bool(chave) and bool(
        re.search(rf"(?<![\w+#]){re.escape(chave)}(?![\w+#])", texto)
    )


_contem_termo = contem_termo


def categoria_de(habilidade: str) -> str:
    """Em qual das categorias canônicas esta habilidade mora.

    O que a tabela não conhece cai em `Ferramentas`, que é honesto: é melhor um
    balde genérico no fim da seção do que uma habilidade fora do lugar — o
    classificador do ATS lê o rótulo como declaração sobre o item.
    """
    n = normalizar(habilidade)
    if not n:
        return FERRAMENTAS
    if direta := TAXONOMIA.get(n):
        return direta
    # Da chave mais longa para a mais curta: "machine learning" antes de "ml"
    # solto, "api rest" antes de "rest".
    for chave in sorted(TAXONOMIA, key=len, reverse=True):
        if _contem_termo(chave, n):
            return TAXONOMIA[chave]
    return FERRAMENTAS
