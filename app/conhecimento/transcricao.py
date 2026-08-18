"""Transcrição bruta → nota de estudo que eu leio e a IA indexa.

O Whisper devolve um bloco de texto corrido, sem pontuação confiável, com os
termos técnicos errados. É o pior formato possível para as duas pontas: eu não
releio um muro de 6.000 palavras, e o chunker corta no meio de uma frase e
embeda parágrafo que fala de duas coisas.

Cinco etapas do bruto até a nota. **As três primeiras são código**, e essa
divisão é a decisão central do módulo: o que é padrão fechado o regex resolve
sempre igual, e o modelo fica só com o que exige ler.

1. **glossário** — "fast API" → "FastAPI", "pigvector" → "pgvector". Um 4B
   corrigindo termo a termo inventa termo novo; uma tabela de substituição não.
2. **ruído de vídeo** — saudação, "se inscreve no canal", despedida. Já esteve
   no prompt da etapa 3 e falhava: ver `limpar_ruido`.
3. **segmentação** — blocos de ~600 palavras. Com gravação, blocos de pedaços
   inteiros, que carregam o instante do vídeo.
4. **reescrita** (LLM, um bloco por vez) — pontua e organiza em subtítulos.
   Não resume: transcrição resumida perde o detalhe pelo qual eu assisti.
5. **fichamento** (LLM, uma chamada) — título, resumo, destaques, tags e pasta.

## Quando cada etapa acontece

As cinco valem para os dois caminhos, mas o **momento** é diferente e é isso que
divide o módulo em duas metades encaixáveis:

- **arquivo, YouTube, reprocessar** — tudo de uma vez: `processar`.
- **gravação pela tela** — as etapas 1 a 4 rodam **durante a aula**, um bloco por
  vez (`limpar` + `reescrever_um`, chamados por `gravacao.py`), e ao apertar
  parar só sobra `juntar_blocos` + `catalogar`. Esperar 3 min 30 depois do parar
  virou esperar ~1 min: docs/fase-transcricao.md §P1.

## Onde a nota mora

A pasta e as tags são **como a busca vai achar isso depois**, e a escolha vem
da vizinhança semântica: quais notas do índice falam do mesmo assunto, e onde
elas moram (`vizinhos`). Sem vizinho próximo a nota vai para `_inbox` e a tela
diz "assunto novo" — o sistema só afirma o destino quando tem evidência dele.

O frontmatter serve às duas pontas: `tags` e `wikilinks` já são lidos por
`fontes.ler_markdown`, então a nota entra no índice com metadado no dia em que
é escrita, sem passo extra.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.config import DATA_DIR
from app.llm import gateway
from app.llm.tipos import LLMErro
from app.utils.logger import get_logger

logger = get_logger()

GLOSSARIO_PADRAO = DATA_DIR / "glossario.json"

# Blocos de ~600 palavras: cabe folgado nos 8k de contexto junto do prompt, e é
# grande o bastante para o modelo ver o assunto inteiro de um tópico.
PALAVRAS_POR_BLOCO = 600
# Abaixo disso não vale partir: um bloco de 80 palavras vira um subtítulo solto.
MINIMO_PARA_PARTIR = 900

_FIM_DE_FRASE = re.compile(r"(?<=[.!?…])\s+")

# Muleta de fala. Sai por código porque é lista fechada e o modelo às vezes
# "corrige" trocando por outra muleta.
_MULETAS = re.compile(
    r"\b(né|tá|tipo assim|então assim|é isso aí|beleza|ok pessoal|"
    r"galera|pessoal)\b[,.]?\s*",
    re.IGNORECASE,
)
_REPETIDA = re.compile(r"\b(\w+)(\s+\1\b){1,}", re.IGNORECASE)
_ESPACOS = re.compile(r"[ \t]{2,}")


@dataclass(slots=True)
class Fichamento:
    """O que o modelo decide sobre a nota — tudo corrigível na tela final."""

    titulo: str
    resumo: str = ""
    conceitos: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    pasta: str = ""
    perguntas: list[str] = field(default_factory=list)
    # O que decide se a nota vale a releitura. Sem isto eu reassisto o vídeo.
    destaques: list[str] = field(default_factory=list)
    # Os que citam número, fórmula ou símbolo que **não existe** no corpo da
    # aula. Ficam na nota marcados, não apagados: o modelo pode estar certo e o
    # corpo incompleto — mas eu preciso saber qual conferir. Ver `ancorar`.
    suspeitos: list[str] = field(default_factory=list)
    # Wikilinks para notas do mesmo assunto. 146 das 232 notas do vault se ligam
    # entre si; a que nasce órfã fica fora da teia e some.
    relacionadas: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Nota:
    fichamento: Fichamento
    corpo: str
    corrigidos: list[str] = field(default_factory=list)
    # Vai para a nota: filtro que apaga em silêncio não é confiável.
    ruido: list[str] = field(default_factory=list)
    caminho: Path | None = None


# ── 1. Glossário: o que o Whisper erra ────────────────────────────


def carregar_glossario(caminho: Path | None = None) -> dict[str, str]:
    """`{errado: certo}`. Arquivo ausente não é erro — só significa sem correção."""
    alvo = caminho or GLOSSARIO_PADRAO
    if not alvo.exists():
        logger.info(f"Sem glossário em {alvo}; a transcrição vai crua.")
        return {}
    try:
        bruto = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Glossário ilegível ({e}); seguindo sem ele.")
        return {}

    # Aceita os dois formatos: {"certo": ["errado", ...]} é como se escreve à
    # mão (agrupado pelo termo), {"errado": "certo"} é como se aplica.
    plano: dict[str, str] = {}
    for chave, valor in bruto.items():
        if chave.startswith("_"):
            continue          # `_leia_me` e afins são comentário, não regra
        if isinstance(valor, list):
            for errado in valor:
                plano[str(errado).lower()] = chave
        else:
            plano[str(chave).lower()] = str(valor)
    return plano


def _sem_acento(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def aplicar_glossario(texto: str, glossario: dict[str, str]) -> tuple[str, list[str]]:
    """Troca os termos errados e devolve o que foi trocado.

    Ignora acento e caixa na hora de casar, mas escreve o termo exatamente como
    está no glossário: "Fast Api", "fast api" e "fastapi" viram todos "FastAPI".
    """
    if not glossario:
        return texto, []

    trocados: list[str] = []
    # Do termo mais longo para o mais curto: senão "api" trocaria dentro de
    # "fast api" e a regra maior nunca chegaria a casar.
    for errado, certo in sorted(glossario.items(), key=lambda kv: -len(kv[0])):
        # `\b` não fecha em termo com espaço no meio ("fast api"); a fronteira
        # é montada à mão para funcionar nos dois casos.
        padrao = re.compile(
            rf"(?<![\w-]){re.escape(_sem_acento(errado))}(?![\w-])", re.IGNORECASE
        )
        # Casa sem acento e recorta no texto original pela mesma posição:
        # `_sem_acento` preserva o comprimento, então os índices valem nos dois.
        pedacos: list[str] = []
        fim = 0
        for m in padrao.finditer(_sem_acento(texto)):
            original = texto[m.start() : m.end()]
            if original != certo:
                trocados.append(f"{original} → {certo}")
            pedacos.append(texto[fim : m.start()])
            pedacos.append(certo)
            fim = m.end()
        if pedacos:
            pedacos.append(texto[fim:])
            texto = "".join(pedacos)

    return texto, sorted(set(trocados))


def limpar_fala(texto: str) -> str:
    """Tira muleta, palavra repetida e espaço duplo. Não mexe no conteúdo."""
    texto = _MULETAS.sub("", texto)
    texto = _REPETIDA.sub(r"\1", texto)
    return _ESPACOS.sub(" ", texto).strip()


# ── 1b. O ruído de vídeo ──────────────────────────────────────────

# Isto já esteve no prompt da reescrita — que também diz "NÃO resuma". As duas
# instruções competem, e o 4B resolvia o conflito diferente a cada rodada: numa
# o conteúdo caía 13%, noutra 25%, e a que cortou mais manteve a abertura.
# Frase a frase, para não perder o parágrafo quando o "se inscreve" vem grudado
# numa explicação.
#
# ## Esta lista é um vocabulário que cresce, como o glossário
#
# Medido nas quatro aulas que já estão no vault (17/08/2026): **as quatro tinham
# zero frases descartadas**. O filtro não estava errado — estava cobrindo as
# fórmulas de um canal que não é o que eu assisto. Cada bloco abaixo tem o
# contra-exemplo real que o forçou a existir, no comentário.
#
# O critério para entrar aqui é o de sempre: fórmula fechada de vídeo, que não
# diz nada sobre a matéria. Frase que é *conselho de estudo* ("vão estudar um
# pouco", "ter um caderno organizado é importante") **fica** — é opinião do
# professor sobre o assunto, e cortar isso é cortar conteúdo. E o que sai vai
# para a seção de revisão da nota, então um falso positivo é visível.
_RUIDO_DE_VIDEO = re.compile(
    r"("
    r"se inscrev|inscreva-se|clica(r|ndo)? (n)?o (bot[ãa]o|link|sininho)|"
    r"ativ(e|ar) o sininho|dá?( um)? like|deixa o like|deixe seu like|"
    r"curt(a|e|ir) o v[íi]deo|comenta a[íi]|deixe (seu|um) coment[áa]rio|"
    # "Compartilhe o vídeo pelo WhatsApp" — o `(esse|este)` não cobria "o".
    r"compartilh(e|a|em) (esse|este|o) v[íi]deo|"
    # "Manda aí para a prima, para o primo que quer estudar" — o mesmo pedido
    # sem a palavra "compartilhe".
    r"manda a[íi] (o v[íi]deo )?(para|pra)|"
    # patrocínio e venda
    r"patrocinad|cupom|c[óo]digo de desconto|link na descri[çc][ãa]o|"
    r"link (abaixo|aqui embaixo)|oferta por tempo limitado|"
    r"assine (o|a|meu|minha) (canal|curso|newsletter|plano)|"
    # "Peçam lá no Instagram um resumo teórico que eu fiz" — venda de material
    # por fora, que na nota vira instrução para abrir outro app. O `pedir` e o
    # `manda o direct` entraram depois, da segunda aula: "vocês vão me pedir lá
    # pelo Instagram. Manda o direct no Instagram."
    r"(pe[çc]am?|pedir|sig(a|am)|me sig(a|am)|cham(a|e|em|ar)|manda) "
    r"(l[áa] |o direct |me )?(no|pelo) (instagram|insta|telegram|whats|face)|"
    r"manda o direct|"
    # saudação e abertura
    r"ol[áa],? (meus? )?(amigos|pessoal|gente)|aqui [ée] o (professor|prof)|"
    # "Professor Vaguinho aqui" — a ordem invertida escapou na segunda aula.
    r"(professor|prof)\.? \w+ aqui\b|"
    # "Bem-vindos ao canal Descomplicando RLM": sem "sejam" antes, e o antigo
    # `sejam? bem[- ]vind` exigia. O `ao canal|ao v[íi]deo` é o que mantém a
    # regra fechada — "bem-vindo" solto pode ser conteúdo.
    r"sejam? bem[- ]vind|bem[- ]vind[oa]s? ao (meu )?(canal|v[íi]deo)|"
    # "Olá!" sozinho, uma frase inteira. Ancorado justo por ser curto demais.
    r"^\W*ol[áa]\W*$|"
    # A missão do canal, dita na abertura: "Meu compromisso é descomplicar a
    # matemática", "Apresento a vocês o nosso conteúdo de hoje".
    r"meu compromisso [ée]|apresento a voc[êe]s o (nosso|meu) conte[úu]do|"
    r"(para o|no) v[íi]deo de hoje,? eu (trouxe|vou)|"
    # despedida
    r"um (beijo|abra[çc]o) (grande )?(para|pra) voc[êe]s|"
    # "Um beijo grande." / "Um beijo grande e um abraço." — sem o "para vocês".
    r"^\W*um (beijo|abra[çc]o)( grande)?( e um (beijo|abra[çc]o)( grande)?)?\W*$|"
    r"at[ée] (a )?pr[óo]xima|fiquem (com deus|em paz)|"
    r"^\W*estamos juntos\W*$|"
    r"obrigado por (terem )?me assistir|"
    r"obrigado por (terem )?me assistido|por ter deixado eu entrar|"
    # "Obrigado pela audiência." fecha o vídeo e não diz nada da matéria.
    r"obrigado (pela|por sua) (audi[êe]ncia|aten[çc][ãa]o)|"
    r"desejo (essa|a sua|sua) aprova[çc][ãa]o|espero estar contribuindo|"
    # `!` faltava na classe, e "Tchau!" é como as duas aulas terminam.
    r"tchau[,.! ]*$|"
    # autopromoção e meta sobre o canal
    r"(meu|nosso) canal|(abrir|abri) (este|esse|meu|o meu) canal|"
    # "dando aula em pré-vestibular" — o antigo exigia "para|há" e um "anos"
    # depois, então a variante com "em" passava.
    r"d(ou|ando) aula (em|para|há|ha)|(meus|nossos) cursos online|"
    r"h[áa] mais de \d+ anos|"
    r"(esse|este) v[íi]deo (ficou|foi)|"
    # "No próximo vídeo eu…", "Nos próximos vídeos, ainda temos dois vídeos" e
    # "O próximo vídeo que eu voltar" — daí o `n?`, para o "o" sozinho.
    # A lista de verbos depois é o que protege a referência estrutural legítima
    # ("no próximo vídeo falaremos da Parte 2 dos conectivos"), que é conteúdo.
    r"\bn?(o|os) pr[óo]ximos? v[íi]deos?,? (eu|ainda|vamos|vou|n[óo]s|que)|"
    # `nosso` fica no formato estreito de origem. Aberto junto do `próximo`, ele
    # comia "para encerrar o nosso vídeo, vou para esse exemplo" — que é a
    # transição para um exercício resolvido, e levava o `### Exemplo Prático`.
    r"no nosso v[íi]deo eu"
    r")",
    re.IGNORECASE,
)

# Frase curta e sem conteúdo perto do ruído ("Vamos lá.", "Muito bem.") —
# só cai quando é vizinha de uma frase descartada, senão é conectivo legítimo.
_FRASE_OCA = re.compile(r"^\W*(vamos l[áa]|muito bem|beleza|ent[ãa]o t[áa])\W*$", re.IGNORECASE)


def limpar_ruido(texto: str) -> tuple[str, list[str]]:
    """Tira saudação, pedido de inscrição e despedida. Devolve o que saiu.

    O que sai vai para a nota, na seção de revisão: filtro que apaga em silêncio
    é filtro em que não dá para confiar — e um dia ele vai comer uma explicação
    que começava com "no próximo vídeo eu mostro como...".
    """
    frases = _FIM_DE_FRASE.split(texto)
    mantidas: list[str] = []
    removidas: list[str] = []

    for i, frase in enumerate(frases):
        if _RUIDO_DE_VIDEO.search(frase):
            removidas.append(frase.strip())
            continue
        vizinha_caiu = bool(removidas) and i > 0 and frases[i - 1].strip() in removidas
        if vizinha_caiu and _FRASE_OCA.match(frase):
            removidas.append(frase.strip())
            continue
        mantidas.append(frase)

    if removidas:
        logger.info(f"Ruído de vídeo: {len(removidas)} frase(s) descartada(s)")
    return _ESPACOS.sub(" ", " ".join(mantidas)).strip(), removidas


def limpar(texto: str, glossario: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """As três etapas de código, na ordem: glossário, muleta de fala, ruído.

    Existe como função porque agora há **dois** lugares que precisam desta
    sequência exata: `processar`, com o texto inteiro, e a gravação ao vivo, com
    um bloco de ~600 palavras que fechou no meio da aula
    (docs/fase-transcricao.md §P1). Duas cópias da sequência é como uma delas
    fica para trás no dia em que a quarta etapa aparecer.
    """
    texto, corrigidos = aplicar_glossario(texto, glossario)
    texto = limpar_fala(texto)
    texto, ruido = limpar_ruido(texto)
    return texto, corrigidos, ruido


# ── 2. Segmentação ────────────────────────────────────────────────


def blocos(texto: str, *, palavras: int = PALAVRAS_POR_BLOCO) -> list[str]:
    """Corta em blocos de ~N palavras, sempre no fim de uma frase."""
    if len(texto.split()) <= MINIMO_PARA_PARTIR:
        return [texto] if texto.strip() else []

    saida: list[str] = []
    atual: list[str] = []
    contador = 0
    for frase in _FIM_DE_FRASE.split(texto):
        atual.append(frase)
        contador += len(frase.split())
        if contador >= palavras:
            saida.append(" ".join(atual).strip())
            atual, contador = [], 0
    if atual:
        resto = " ".join(atual).strip()
        # Sobra minúscula gruda no bloco anterior em vez de virar seção órfã.
        if resto and saida and len(resto.split()) < palavras // 4:
            saida[-1] = f"{saida[-1]} {resto}"
        elif resto:
            saida.append(resto)
    return saida


# ── 3. Reescrita (LLM) ────────────────────────────────────────────

PROMPT_BLOCO = """\
Abaixo está um trecho de TRANSCRIÇÃO AUTOMÁTICA de um vídeo/aula sobre "{tema}".
Ela veio sem pontuação confiável e com marcas de fala.

Sua tarefa é DIAGRAMAR, não resumir. Reescreva o mesmo conteúdo em texto legível:

- pontue e separe em parágrafos curtos;
- crie subtítulos `##` quando o assunto virar;
- transforme enumeração falada ("primeiro... segundo...") em lista com `-`;
- coloque `código`, comandos e nomes de arquivo em crase;
- tire "né", "então", "pessoal", repetição e correção de fala.

REGRAS DURAS:
- NÃO resuma, NÃO corte exemplo, NÃO encurte explicação. Exercício resolvido,
  definição e macete ficam INTEIROS. O texto de saída tem que ter tamanho
  parecido com o de entrada.
- NÃO acrescente informação que não está no trecho. Se algo ficou incompreensível,
  escreva `[inaudível]` e siga.
- NÃO invente número, nome de biblioteca nem versão.
- Responda só com o texto reescrito, sem comentário seu.

TRECHO:
{trecho}

TEXTO REESCRITO:"""

SCHEMA_FICHAMENTO = {
    "type": "object",
    "required": ["titulo", "resumo", "tags"],
    "properties": {
        "titulo": {"type": "string"},
        "resumo": {"type": "string"},
        "destaques": {"type": "array"},
        "conceitos": {"type": "array"},
        "tags": {"type": "array"},
        "pasta": {"type": "string"},
        "perguntas": {"type": "array"},
    },
}

PROMPT_FICHAMENTO = """\
Você vai catalogar uma nota de estudo para um vault do Obsidian que já existe.
{vizinhanca}
PASTAS QUE JÁ EXISTEM (prefira SEMPRE uma delas):
{pastas}

TAGS QUE JÁ EXISTEM NO VAULT (reaproveite; não crie sinônimo de uma que já está aqui):
{tags}

TÍTULO QUE EU DEI: {tema}

INÍCIO DA NOTA:
{amostra}

Use os SÍMBOLOS direto (¬ ∧ ∨ → ↔ ∀ ∃), nunca LaTeX com barra invertida. Numa
string JSON a barra invertida é escape: "\\neg" vira quebra de linha e "\\land"
invalida o JSON inteiro.

Responda só com este JSON:

{{
  "titulo": "<título curto e específico que cobre a AULA INTEIRA, do primeiro
              ao último assunto do roteiro — não só o primeiro tópico. Se ela
              ensina quatro conectivos, o título é sobre conectivos, não sobre
              o primeiro deles. Sem 'Aula 1' nem 'Vídeo sobre'>",
  "resumo": "<3 frases dizendo o que a aula ensina, cobrindo o roteiro todo.
              Descreva o conteúdo — nunca comente o que a aula deixou de
              fazer nem cite estas instruções>",
  "destaques": ["<3 a 5 AFIRMAÇÕES tiradas da aula: a regra, a fórmula, a
                 definição, o macete. Cada uma tem que ser útil sozinha, sem eu
                 reabrir a nota.
                 SIM: 'O número de linhas de uma tabela verdade é 2^n, com n =
                      número de proposições'
                 SIM: 'Sentença aberta (com incógnita) não é proposição'
                 NÃO: 'Aprenda a usar tabelas verdade'   ← isso é tarefa, não fato
                 NÃO: 'Entenda a importância da lógica'  ← não diz nada
                 Proibido começar com Entenda/Aprenda/Compreenda/Domine/Observe.
                 Só o que a aula afirmou: NÃO explique sigla que ela não
                 explicou, NÃO invente o significado de abreviação.
                 ESPALHE pelo roteiro: se a aula tem quatro assuntos, não tire
                 os cinco destaques do primeiro>"],
  "conceitos": ["<5 a 8 conceitos-chave que a nota explica>"],
  "tags": ["<4 a 7 tags em minúsculo-com-hifen, das que já existem quando servir>"],
  "pasta": "<uma das pastas listadas acima; só invente outra se nenhuma servir>",
  "perguntas": ["<3 perguntas que esta nota responde, do jeito que eu perguntaria>"]
}}

JSON:"""

_BLOCO_VIZINHOS = """
O QUE EU JÁ TENHO NO VAULT SOBRE ESTE ASSUNTO (a busca semântica achou):
{lista}

Use isto para TRÊS coisas, e só para estas três:
1. escolher a pasta — a de uma dessas notas é quase sempre a certa;
2. reaproveitar o vocabulário e o padrão de título da série (se as irmãs se
   chamam "Assunto 1 — Tema", esta é a próxima da sequência, não um nome novo);
3. conferir uma fórmula ou definição que a transcrição deixou ambígua.

PROIBIDO tirar destaque daqui. Os destaques saem SÓ da aula transcrita abaixo.
Se um fato aparece nas notas do vault e não aparece na aula, ele não entra.
"""

_TRECHO_VIZINHO = 400  # o bastante para conferir uma fórmula, sem virar contexto


_TITULO_MD = re.compile(r"^(#{1,5})(\s)", re.MULTILINE)


def _aninhar_titulos(texto: str) -> str:
    """`## Conectivos` → `### Conectivos`, para caberem dentro de `## Conteúdo`.

    O modelo escreve `##`, que no documento final fica no mesmo nível de
    "Para lembrar" e "Conteúdo" — o índice do Obsidian mostra os assuntos da
    aula como irmãos das seções da nota, e uma aula com dez subtítulos vira uma
    lista chapada de treze itens sem hierarquia.
    """
    return _TITULO_MD.sub(r"\1#\2", texto)


async def reescrever_um(trecho: str, *, tema: str, indice: int) -> str:
    """Um bloco, sozinho. Falhar aqui devolve o trecho cru — nunca perdido.

    Público porque é o ponto de entrada da reescrita ao vivo: a gravação fecha um
    bloco no minuto 5 da aula e chama isto ali mesmo, enquanto o vídeo continua
    rodando (docs/fase-transcricao.md §P1). `reescrever` é o laço em cima dele,
    para quem tem o texto inteiro de uma vez (arquivo, YouTube).
    """
    try:
        r = await gateway.gerar(
            PROMPT_BLOCO.format(tema=tema, trecho=trecho),
            tarefa="redigir",
            agente=f"conhecimento.transcricao.bloco{indice}",
            temperatura=0.3,
        )
        texto = (r.texto or "").strip()
    except LLMErro as e:
        logger.warning(f"Bloco {indice} sem LLM ({type(e).__name__}); fica cru.")
        return trecho

    # O guarda que importa: um 4B que resume em vez de diagramar devolve 20% do
    # tamanho. Nesse caso o bruto é melhor — perder formatação é reversível,
    # perder conteúdo não.
    if len(texto.split()) < len(trecho.split()) * 0.55:
        logger.warning(
            f"Bloco {indice}: o modelo resumiu ({len(texto.split())} de "
            f"{len(trecho.split())} palavras); mantendo o texto original."
        )
        return trecho
    return _aninhar_titulos(texto)


def blocos_com_tempo(
    marcas: list[tuple[int, str]], *, palavras: int = PALAVRAS_POR_BLOCO
) -> list[tuple[int, str]]:
    """`[(segundo, texto)]` — blocos montados a partir dos pedaços gravados.

    Quando a transcrição veio de uma gravação, cada pedaço sabe em que instante
    do vídeo começou. Agrupando **pedaços inteiros** em vez de cortar por frase,
    cada bloco herda um instante exato — e é isso que permite carimbar a nota
    com `⏱ 08:20`, que é o que me faz conseguir voltar na fonte para rever.
    """
    saida: list[tuple[int, str]] = []
    atual: list[str] = []
    inicio = marcas[0][0] if marcas else 0
    contador = 0

    for segundo, texto in marcas:
        if not atual:
            inicio = segundo
        atual.append(texto)
        contador += len(texto.split())
        if contador >= palavras:
            saida.append((inicio, " ".join(atual).strip()))
            atual, contador = [], 0
    if atual:
        saida.append((inicio, " ".join(atual).strip()))
    return saida


def relogio(segundo: int) -> str:
    return f"{segundo // 60:02d}:{segundo % 60:02d}"


def juntar_blocos(prontos: list[tuple[int | None, str]]) -> str:
    """Os blocos já reescritos viram o corpo da nota, na ordem, carimbados.

    Separado do laço da reescrita porque a gravação ao vivo chega aqui com os
    blocos **prontos há vários minutos** — cada um reescrito no instante em que
    fechou — e só precisa da montagem.

    O carimbo é decidido aqui, e não quando o bloco é reescrito, por causa da
    regra do primeiro: `⏱ 00:00` só entra se houver um segundo bloco depois. Ao
    vivo isso não se sabe no minuto 5; na montagem, sim.
    """
    saida = []
    for segundo, texto in prontos:
        if segundo is not None and (segundo > 0 or len(prontos) > 1):
            texto = f"`⏱ {relogio(segundo)}`\n\n{texto}"
        saida.append(texto)
    return "\n\n".join(saida)


async def reescrever(
    texto: str, *, tema: str, marcas: list[tuple[int, str]] | None = None
) -> str:
    """A transcrição inteira, bloco a bloco, na ordem.

    O caminho de quem tem o texto todo de uma vez: `--arquivo`, `--sem-llm` e o
    reprocessamento de uma nota que já está no vault. A gravação pela tela não
    passa mais por aqui — ela reescreve bloco a bloco durante a própria aula.

    Com `marcas`, cada bloco entra na nota precedido do instante do vídeo em que
    ele começa. Sem elas (arquivo, YouTube), a nota sai sem carimbo — é melhor
    não ter timestamp do que ter um chutado.
    """
    partes: list[tuple[int | None, str]]
    if marcas:
        partes = [(s, t) for s, t in blocos_com_tempo(marcas)]
    else:
        partes = [(None, b) for b in blocos(texto)]

    logger.info(f"Reescrevendo {len(partes)} bloco(s) de transcrição...")
    prontos: list[tuple[int | None, str]] = []
    for i, (segundo, bloco) in enumerate(partes, start=1):
        prontos.append((segundo, await reescrever_um(bloco, tema=tema, indice=i)))
        logger.info(f"  bloco {i}/{len(partes)} pronto")
    return juntar_blocos(prontos)


# Quanto da nota o fichamento enxerga. Com os 3.000 caracteres da primeira
# versão ele via 10% de uma aula de 28 min — e os 10% de abertura. Nunca
# chegava na fórmula 2^n, então destacava o que tinha lido: "entenda a
# importância da lógica".
AMOSTRA_INICIO = 2500
AMOSTRA_FATIA = 900
AMOSTRA_FATIAS = 4


def _amostra_para_fichar(corpo: str) -> str:
    """O roteiro da aula primeiro, depois o começo e fatias do resto.

    **A ordem é a correção.** Na versão anterior a amostra abria com 2.500
    caracteres do início, e o modelo ancorava neles: uma aula de 26 minutos
    sobre quatro conectivos virou a nota "Negação em Lógica Proposicional",
    com os dois destaques falando só de negação — o conteúdo estava completo,
    o fichamento é que enxergou o primeiro tópico e parou.

    Os subtítulos são o índice do que a aula cobriu e vêm na frente, para o
    modelo ver o escopo inteiro antes de qualquer detalhe. É o mesmo motivo de
    um sumário abrir um livro.
    """
    if len(corpo) <= AMOSTRA_INICIO + AMOSTRA_FATIA:
        return corpo

    titulos = [linha for linha in corpo.splitlines() if linha.lstrip().startswith("#")]
    resto = corpo[AMOSTRA_INICIO:]
    passo = max(1, len(resto) // AMOSTRA_FATIAS)
    fatias = [resto[i : i + AMOSTRA_FATIA] for i in range(0, len(resto), passo)]

    partes = []
    if titulos:
        partes.append(
            "ROTEIRO DA AULA (todos os assuntos cobertos, do começo ao fim):\n"
            + "\n".join(titulos)
            + "\n\n"
        )
    partes.append("COMEÇO DA AULA:\n" + corpo[:AMOSTRA_INICIO])
    partes.append("\n\nTRECHOS DO RESTO DA AULA:\n\n" + "\n\n[...]\n\n".join(fatias))
    return "".join(partes)


# ── Q3: o destaque tem que estar ancorado no corpo ────────────────

# Número e potência: o que uma aula ou disse, ou não disse, sem meio-termo.
# Comparados como TOKEN e não como substring — "2" casava dentro de "2019" e
# deixava passar o `2^n` do §7.3, que é justamente o caso que isto existe para
# pegar.
_NUMERO = re.compile(r"\d+(?:[.,]\d+)?%?|\^\s*\w+")

# Símbolo lógico ficou **fora** de propósito. O modelo escreve `¬P ∨ ¬Q` onde a
# aula fala "não P ou não Q": comparar símbolo contra palavra marcaria como
# suspeito todo destaque bem escrito, e o ⚠ viraria ruído em duas notas.

# Palavra de conteúdo: 6 letras ou mais. Abaixo disso é artigo, preposição e
# verbo de ligação, que aparecem em qualquer texto e não discriminam nada.
_PALAVRA = re.compile(r"[a-zà-ÿ]{6,}", re.IGNORECASE)

# Quanto do vocabulário próprio do destaque precisa existir na aula. Meio, e não
# tudo, porque o modelo reformula: ele diz "conjunção" onde a aula disse "o e".
# Um sinônimo ou dois é reformulação; a metade ausente é outro assunto.
_FRACAO_MINIMA = 0.5

# Prefixo em vez de palavra inteira, para "proposição" casar com "proposições"
# sem arrastar um stemmer para dentro do projeto.
_PREFIXO = 6


def _radicais(texto: str) -> set[str]:
    """Prefixos das palavras de conteúdo, sem acento e em minúsculo."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )
    return {p[:_PREFIXO] for p in _PALAVRA.findall(sem_acento)}


def ancorar(destaques: list[str], corpo: str) -> tuple[list[str], list[str]]:
    """Separa os destaques em `(ancorados, suspeitos)`.

    **O que este teste pega, e o que ele não pega — a distinção importa.**

    Pega a *invenção de fato*: o §7.3 dos docs registra dois destaques que não
    existiam na aula ("o número de linhas de uma tabela verdade é 2^n",
    "sentença aberta com incógnita não é proposição"). Eram verdade sobre
    lógica e vieram do que o modelo já sabia. Dois sinais os denunciam:

    1. **número ausente** — `2^n` não aparece em lugar nenhum daquela aula;
    2. **vocabulário ausente** — "sentença", "aberta" e "incógnita" também não.

    **Não pega a fórmula invertida.** "A negação de P ou Q é P e Q" — o erro
    real do llama3.1:8b em 17/08/2026 — tem todas as palavras presentes no
    corpo; o que está errado é a relação entre elas, e isso é semântica, não
    presença. Para essa classe o remédio é o contexto do vault no prompt, que
    põe o enunciado certo na frente do modelo.

    As duas peças são complementares de propósito, e nenhuma sozinha cobre as
    duas classes de erro. Fingir que este filtro resolve tudo seria pior que
    não tê-lo: eu pararia de conferir.

    Marca, não apaga — a regra do §Q3. O modelo pode estar certo e o corpo
    incompleto (o Whisper perde número o tempo todo); quem decide sou eu.
    """
    numeros_corpo = {n.replace(" ", "") for n in _NUMERO.findall(corpo)}
    radicais_corpo = _radicais(corpo)
    ancorados: list[str] = []
    suspeitos: list[str] = []

    for d in destaques:
        numeros = {n.replace(" ", "") for n in _NUMERO.findall(d)}
        if numeros and not (numeros & numeros_corpo):
            suspeitos.append(d)
            continue

        radicais = _radicais(d)
        # Sem palavra de conteúdo não há o que conferir, e acusar seria pior que
        # não testar: um destaque curto em prosa comum não é acusável.
        if radicais:
            presentes = len(radicais & radicais_corpo) / len(radicais)
            if presentes < _FRACAO_MINIMA:
                suspeitos.append(d)
                continue
        ancorados.append(d)

    if suspeitos:
        logger.warning(
            f"{len(suspeitos)} destaque(s) sem âncora no corpo da aula: "
            + " | ".join(s[:70] for s in suspeitos)
        )
    return ancorados, suspeitos


async def fichar(
    corpo: str,
    *,
    tema: str,
    pastas: list[str],
    tags_do_vault: list[str],
    proximos: list[Vizinho] | None = None,
) -> Fichamento:
    """Título, resumo, conceitos, tags e pasta — a catalogação da nota."""
    proximos = proximos or []
    vizinhanca = (
        _BLOCO_VIZINHOS.format(
            lista="\n".join(
                f'- "{v.titulo}" — está em: {v.pasta or "(raiz)"}'
                + (f"\n  trecho: {v.trecho}" if v.trecho else "")
                for v in proximos
            )
        )
        if proximos
        else ""
    )
    prompt = PROMPT_FICHAMENTO.format(
        tema=tema,
        vizinhanca=vizinhanca,
        pastas="\n".join(f"- {p}" for p in pastas) or "- (nenhuma ainda)",
        tags=", ".join(tags_do_vault[:60]) or "(nenhuma ainda)",
        amostra=_amostra_para_fichar(corpo),
    )
    try:
        r = await gateway.gerar(
            prompt,
            tarefa="compreender",
            agente="conhecimento.transcricao.fichamento",
            json_schema=SCHEMA_FICHAMENTO,
            # Catalogar é a tarefa mais determinística do módulo: título, tags e
            # pasta não ganham nada com variedade. Em 0.2 a mesma nota rendia 5
            # destaques numa rodada e 1 na seguinte.
            temperatura=0.1,
        )
        # Modelo pequeno às vezes responde `[...]` no lugar de `{...}`; sem a
        # checagem o `.get` estoura e derruba o fichamento inteiro.
        dado = r.json if isinstance(r.json, dict) else {}
    except LLMErro as e:
        logger.warning(f"Fichamento sem LLM ({type(e).__name__}); usando o título dado.")
        dado = {}

    # Q3: o que cita número ou fórmula ausente do corpo vai marcado. Roda depois
    # dos filtros de forma — não adianta conferir a âncora de um destaque que já
    # foi descartado por ser vago.
    ancorados, suspeitos = ancorar(_destaques_limpos(dado.get("destaques")), corpo)

    return Fichamento(
        titulo=latex_para_simbolo(dado.get("titulo") or tema).strip()[:120],
        resumo=latex_para_simbolo(dado.get("resumo") or "").strip(),
        destaques=ancorados,
        suspeitos=suspeitos,
        conceitos=[latex_para_simbolo(c).strip() for c in (dado.get("conceitos") or [])][:8],
        tags=_tags_limpas(dado.get("tags"), tema),
        pasta=_pasta_escolhida(dado.get("pasta"), pastas, proximos),
        perguntas=[str(p).strip() for p in (dado.get("perguntas") or [])][:5],
        relacionadas=[v.wikilink for v in proximos[:4]],
    )


def _pasta_escolhida(bruto, pastas: list[str], proximos: list[Vizinho]) -> str:
    """Onde a nota mora — **só quando há evidência de onde**.

    Sem vizinho próximo, o palpite do modelo não vale: ele está escolhendo a
    menos errada de 46 pastas que não falam do assunto. Foi exatamente assim
    que uma transcrição sobre **carro elétrico** foi parar em "Machine
    Learning / LLMs e IA Generativa" no teste real — pasta que existe, escolha
    confiante, resultado errado.

    Então a regra é a do resto do projeto: o sistema só afirma o que consegue
    sustentar. Sem vizinho, a nota vai para `_inbox` e a tela diz "assunto
    novo" — e eu, que estou na frente da tela naquele instante, escolho em dois
    segundos no campo com as 46 pastas.

    Enfiar a nota numa pasta temática errada é pior que deixá-la na caixa de
    entrada: na caixa eu vejo que falta arrumar; na pasta errada ela some.
    """
    if not proximos:
        return "_inbox"

    pedida = str(bruto or "").strip("/ ").strip()
    if pedida and pedida in pastas:
        return pedida

    # O modelo inventou pasta: fica a onde mais vizinhos moram — a evidência.
    contagem: dict[str, int] = {}
    for v in proximos:
        if v.pasta:
            contagem[v.pasta] = contagem.get(v.pasta, 0) + 1
    if contagem:
        if pedida:
            logger.info(f"Pasta {pedida!r} não existe; usando a dos vizinhos.")
        return max(contagem, key=lambda p: contagem[p])
    return "_inbox"


MAX_TAG = 32


def _encurtar_tag(tag: str) -> str:
    """Corta no hífen, nunca no meio da palavra.

    `processamento-de-linguagem-natur` é uma tag que não casa com nada e não
    quer dizer nada — pior que a tag longa que ela substituiu. Cortando no
    separador, sobra `processamento-de-linguagem`, que ainda é buscável.
    """
    if len(tag) <= MAX_TAG:
        return tag
    cortada = tag[:MAX_TAG].rsplit("-", 1)[0]
    return cortada or tag[:MAX_TAG]


# "Entenda X", "Aprenda Y" é tarefa de estudo, não coisa lembrada. Uma nota
# cheia dessas frases parece útil e não serve para nada: daqui a um mês eu leio
# "Aprenda a usar tabelas verdade" e continuo sem saber usar tabela verdade.
_DESTAQUE_VAZIO = re.compile(
    r"^\W*(entenda|aprenda|compreenda|domine|observe|estude|revise|fique atento|"
    r"atente|note que|lembre-se de|saiba|memorize|pratique|explore|verifique)\b",
    re.IGNORECASE,
)

# O modelo escreve lógica em LaTeX mesmo quando o prompt pede o símbolo. Com a
# barra invertida já preservada pelo `json_extract`, a conversão aqui é uma
# tabela — e uma nota de estudo tem que mostrar `p → q`, não `$p \rightarrow q$`.
_SIMBOLOS = {
    r"\leftrightarrow": "↔", r"\Leftrightarrow": "↔", r"\rightarrow": "→",
    r"\Rightarrow": "→", r"\leftarrow": "←", r"\longrightarrow": "→",
    r"\to": "→", r"\neg": "¬", r"\lnot": "¬", r"\land": "∧", r"\wedge": "∧",
    r"\lor": "∨", r"\vee": "∨", r"\oplus": "⊕", r"\forall": "∀",
    # As formas grandes: numa nota de lógica proposicional o que se quer ler é
    # `∨`, não `⋁`. A substituição é por tamanho decrescente, então estas ganham
    # de `\vee` e `\wedge`.
    r"\bigvee": "∨", r"\bigwedge": "∧", r"\bigcup": "∪", r"\bigcap": "∩",
    r"\exists": "∃", r"\nexists": "∄", r"\in": "∈", r"\notin": "∉",
    r"\cup": "∪", r"\cap": "∩", r"\subset": "⊂", r"\supset": "⊃",
    r"\emptyset": "∅", r"\equiv": "≡", r"\therefore": "∴", r"\neq": "≠",
    r"\leq": "≤", r"\geq": "≥", r"\approx": "≈", r"\times": "×",
    r"\div": "÷", r"\pm": "±", r"\cdot": "·", r"\ldots": "…", r"\dots": "…",
    r"\infty": "∞",
}
_CIFRAO = re.compile(r"\$+([^$]*)\$+")

# Escape de JSON que era LaTeX: `"\bigvee"` vira <backspace> + "igvee", porque
# `\b` é escape válido. `json_extract` cobre os comandos que ele conhece; isto é
# a rede para o comando que ainda não está na lista dele — nenhum caractere de
# controle tem o que fazer numa nota de estudo, e um deles chegou a entrar numa.
_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def latex_para_simbolo(texto: str) -> str:
    r"""`$p \rightarrow q$` → `p → q`. Tabela, não modelo.

    O prompt pede o símbolo e o modelo escreve LaTeX assim mesmo — as duas
    últimas aulas gravadas saíram com `\neg` e `\rightarrow` nos destaques.
    """
    texto = _CONTROLE.sub("", str(texto or ""))
    for comando, simbolo in sorted(_SIMBOLOS.items(), key=lambda kv: -len(kv[0])):
        texto = texto.replace(comando, simbolo)
    # `$...$` sem comando nenhum dentro é enfeite de modelo: `$P$` é só P.
    return _CIFRAO.sub(r"\1", texto)


# Afirmar que o assunto importa não é afirmar nada sobre o assunto. "A lógica
# proposicional é fundamental para as provas" ocupa uma linha da seção que
# existe para eu não reassistir o vídeo, e não me diz uma regra sequer.
_DESTAQUE_VAGO = re.compile(
    r"\b(é|e) (muito |bastante )?(importante|fundamental|essencial|crucial|"
    r"indispens[áa]vel)\b|^\W*(os |as )?(recursos|materiais|t[óo]picos|conte[úu]dos) "
    r"(de estudo )?(inclu|abordad|apresentad)",
    re.IGNORECASE,
)


def _destaques_limpos(bruto) -> list[str]:
    """Só afirmações. O prompt pede e o código confere — o modelo escorrega."""
    saida: list[str] = []
    for d in bruto or []:
        texto = _ESPACOS.sub(" ", " ".join(latex_para_simbolo(d).split())).strip()
        # Curto demais é rótulo ("Tabela verdade"), não afirmação.
        if len(texto) < 25 or _DESTAQUE_VAZIO.match(texto) or _DESTAQUE_VAGO.search(texto):
            continue
        if texto not in saida:
            saida.append(texto)
    return saida[:5]


def _tags_limpas(bruto, tema: str) -> list[str]:
    """`minúsculo-com-hífen`, sem `#`, sem repetido, no máximo 7."""
    saida: list[str] = []
    for t in bruto or []:
        nu = _sem_acento(str(t)).strip().lstrip("#")
        nu = _encurtar_tag(re.sub(r"[^a-z0-9]+", "-", nu).strip("-"))
        if nu and nu not in saida:
            saida.append(nu)
    if not saida:
        base = re.sub(r"[^a-z0-9]+", "-", _sem_acento(tema)).strip("-")
        saida = [base[:32]] if base else ["transcricao"]
    return saida[:7]


# ── 4. A nota no disco ────────────────────────────────────────────


def nome_de_arquivo(titulo: str) -> str:
    """`titulo-da-nota.md` — previsível, sem data no nome.

    Sem timestamp de propósito: o nome do arquivo é o que aparece no wikilink e
    no resultado de busca, e `2026-08-16-1432` ali não ajuda ninguém a decidir
    se é a nota certa. A data mora no frontmatter, que é onde se filtra.
    """
    nu = _sem_acento(titulo)
    nu = re.sub(r"[^a-z0-9]+", "-", nu).strip("-")
    return (nu[:80] or "transcricao") + ".md"


def montar_markdown(nota: Nota, *, fonte: str, duracao_min: float | None = None) -> str:
    """A nota inteira: frontmatter + resumo + conceitos + corpo + o que revisar.

    O frontmatter é lido pelo indexador (`fontes._frontmatter`), então tudo que
    está aqui vira metadado de busca sem código novo.
    """
    f = nota.fichamento
    fm = [
        "---",
        f'titulo: "{f.titulo}"',
        f"tags: [{', '.join(f.tags)}]",
        f"data: {date.today().isoformat()}",
        f'fonte: "{fonte}"',
        "tipo: transcricao",
    ]
    if duracao_min:
        fm.append(f"duracao_min: {duracao_min:.0f}")
    if f.conceitos:
        fm.append(f"conceitos: [{', '.join(f.conceitos)}]")
    fm.append("---")

    partes = ["\n".join(fm), "", f"# {f.titulo}", ""]

    if f.resumo:
        partes += ["> [!resumo] Do que se trata", f"> {f.resumo}", ""]

    if f.destaques or f.suspeitos:
        partes += ["## Para lembrar", ""]
        partes += [f"- **{d}**" if d.endswith((".", "!", "?")) else f"- **{d}.**"
                   for d in f.destaques]
        # Marcados, não escondidos: o modelo pode estar certo e o corpo
        # incompleto. O `⚠` é o que me faz conferir só estes, em vez de reler
        # os cinco — ou, pior, confiar nos cinco.
        partes += [
            f"- ⚠ **{d}**" if d.endswith((".", "!", "?")) else f"- ⚠ **{d}.**"
            for d in f.suspeitos
        ]
        if f.suspeitos:
            partes += [
                "",
                "> [!atenção] Confira os marcados com ⚠",
                "> Citam um número ou fórmula que não aparece na transcrição. "
                "Pode ser erro do modelo, ou pode ser a aula tendo dito e o "
                "Whisper não ter ouvido.",
            ]
        partes.append("")

    if f.perguntas:
        partes += ["## O que esta nota responde", ""]
        partes += [f"- {p}" for p in f.perguntas]
        partes.append("")

    if f.conceitos:
        partes += [
            "## Conceitos",
            "",
            " · ".join(f"**{c}**" for c in f.conceitos),
            "",
        ]

    partes += ["## Conteúdo", "", nota.corpo.strip(), ""]

    # Os wikilinks entram no corpo, não no frontmatter: é assim que o Obsidian
    # monta o grafo e mostra "mencionada em" na nota do outro lado.
    if f.relacionadas:
        partes += ["## Relacionado", ""]
        partes += [f"- {link}" for link in f.relacionadas]
        partes.append("")

    if nota.corrigidos or nota.ruido:
        partes += ["---", "", "## Revisão da transcrição", ""]

    if nota.corrigidos:
        partes += [
            "Termos que o Whisper errou e o glossário corrigiu — confira se algum "
            "ficou errado e ajuste `data/glossario.json`:",
            "",
        ]
        partes += [f"- `{c}`" for c in nota.corrigidos]
        partes.append("")

    if nota.ruido:
        # Filtro que apaga em silêncio é filtro em que não dá para confiar: um
        # dia ele vai comer uma explicação que começava com "no próximo vídeo".
        partes += [
            f"<details><summary>{len(nota.ruido)} frase(s) descartadas como ruído "
            "de vídeo (inscrição, saudação, despedida)</summary>",
            "",
        ]
        partes += [f"- {r}" for r in nota.ruido]
        partes += ["", "</details>", ""]

    return "\n".join(partes)


def salvar(
    nota: Nota,
    *,
    raiz: Path,
    fonte: str,
    duracao_min: float | None = None,
    nome: str | None = None,
) -> Path:
    """Escreve na pasta escolhida, sem nunca sobrescrever nota existente."""
    pasta = raiz / (nota.fichamento.pasta or "Inbox")
    pasta.mkdir(parents=True, exist_ok=True)

    destino = pasta / (nome or nome_de_arquivo(nota.fichamento.titulo))
    n = 2
    while destino.exists():
        # Sobrescrever nota antiga é a única perda irreversível deste caminho.
        destino = pasta / f"{destino.stem.rstrip('-0123456789') or 'nota'}-{n}.md"
        n += 1

    destino.write_text(
        montar_markdown(nota, fonte=fonte, duracao_min=duracao_min), encoding="utf-8"
    )
    nota.caminho = destino
    logger.info(f"Nota salva: {destino}")
    _anotar_no_indice(pasta, destino, nota.fichamento)
    return destino


# O vault já tem 7 arquivos `_Índice <assunto>.md` — é a porta de entrada de cada
# matéria, escrita à mão. Uma nota que não entra ali existe mas não é encontrada
# por quem navega, só por quem busca.
_SECAO_TRANSCRICOES = "## Transcrições"


def _anotar_no_indice(pasta: Path, nota: Path, ficha: Fichamento) -> None:
    """Acrescenta a nota ao `_Índice ....md` da pasta, se houver um.

    **Só acrescenta, nunca reescreve.** O índice é um arquivo que o Pablo
    escreveu à mão, com ordem e comentários pensados; um programa que o
    reorganiza destrói trabalho. A linha entra numa seção própria, no fim, e é
    trivial de remover.
    """
    indices = sorted(pasta.glob("_Índice*.md")) or sorted(pasta.glob("_indice*.md"))
    if not indices:
        return

    alvo = indices[0]
    linha = f"- [[{nota.stem}]]" + (f" — {ficha.resumo.split('.')[0]}." if ficha.resumo else "")
    try:
        texto = alvo.read_text(encoding="utf-8")
        if f"[[{nota.stem}]]" in texto:
            return
        if _SECAO_TRANSCRICOES in texto:
            texto = texto.replace(_SECAO_TRANSCRICOES, f"{_SECAO_TRANSCRICOES}\n\n{linha}", 1)
        else:
            texto = f"{texto.rstrip()}\n\n{_SECAO_TRANSCRICOES}\n\n{linha}\n"
        alvo.write_text(texto, encoding="utf-8")
        logger.info(f"Nota anotada em {alvo.name}")
    except OSError as e:
        logger.warning(f"Não consegui anotar em {alvo.name}: {e}")


# ── Taxonomia do vault (o que já existe) ──────────────────────────


# Pastas que guardam arquivo, não assunto: oferecê-las como destino de uma nota
# de estudo só cria chance de erro.
_PASTAS_NAO_TEMATICAS = {"img", "imgs", "images", "anexos", "pdf", "pdfs", "assets"}


def pastas_do_vault(raiz: Path, *, profundidade: int = 3) -> list[str]:
    """As pastas que já existem, relativas à raiz — o cardápio do fichamento.

    Profundidade 3, e não 2, porque é aí que mora a pasta certa. Este vault tem
    46 pastas; com profundidade 2 o modelo via 12, e
    `Machine Learning/08 - LLMs e IA Generativa` — o destino óbvio de uma aula
    sobre LLM — nunca aparecia como opção. Ele então escolhia a menos errada
    entre as que via, que é como conteúdo sobre apostas foi parar em
    "Bancos de Dados" no primeiro teste real.
    """
    if not raiz.is_dir():
        return []
    saida = set()
    for caminho in raiz.rglob("*"):
        if not caminho.is_dir() or any(p.startswith((".", "_")) for p in caminho.parts):
            continue
        if caminho.name.lower() in _PASTAS_NAO_TEMATICAS:
            continue
        rel = caminho.relative_to(raiz)
        if len(rel.parts) <= profundidade:
            saida.add(str(rel))
    return sorted(saida)


# Acima disto, a nota "parecida" não é do mesmo assunto — é só a menos distante
# de um vault que não fala daquilo. Medido neste índice (216 notas), com a
# distância do melhor candidato e a mediana dos dez primeiros:
#
#     caso                       melhor   mediana
#     CASA (embeddings/RAG)       0,381     0,461
#     CASA (banco de dados)       0,414     0,450
#     NÃO CASA (PIX)              0,486     0,495
#     NÃO CASA (culinária)        0,513     0,533
#     NÃO CASA (carro elétrico)   0,530     0,553
#
# O corte de 0,46 da primeira versão era frouxo: uma transcrição sobre PIX
# achou "Lógica Proposicional" a 0,454 e foi arquivada em
# `Machine Learning/12 - Algoritmos de Busca`. Olhando a lista inteira daquele
# caso, **todos os candidatos estavam entre 0,454 e 0,473** — o borrão achatado
# que "nada casa" produz num espaço de embedding.
#
# 0,44 fica acima do pior acerto (0,414) e bem abaixo do melhor erro (0,486).
# A assimetria justifica apertar: perder um vizinho manda a nota para o
# `_inbox`, que eu conserto em dois cliques no seletor de pastas; aceitar um
# vizinho falso arquiva a nota no lugar errado, e isso eu só descubro quando
# não achar mais.
#
# São cinco amostras — é heurística, não lei. **A rede de segurança é a tela**,
# que mostra a lista de pastas e por que aquela foi sugerida.
DISTANCIA_MESMO_ASSUNTO = 0.44


@dataclass(slots=True)
class Vizinho:
    """Uma nota que já existe e fala do mesmo assunto.

    `trecho` é o pedaço que a busca casou. Ele já vinha do índice e era jogado
    fora: a busca custava 13 s, trazia o texto dos chunks mais parecidos, e o
    código guardava só o nome do arquivo. Numa aula de lógica isso significou
    descartar o enunciado **correto** da Lei de Morgan — que estava numa nota
    irmã, no mesmo resultado de busca — e deixar o modelo deduzi-la de uma
    transcrição embaralhada.
    """

    titulo: str
    caminho: Path
    pasta: str
    distancia: float | None = None
    trecho: str = ""

    @property
    def wikilink(self) -> str:
        return f"[[{self.caminho.stem}]]"


async def vizinhos(
    texto: str, raiz: Path, *, n: int = 5, excluir: Path | None = None
) -> list[Vizinho]:
    """As notas do vault mais parecidas com esta transcrição.

    **É a melhor informação disponível sobre onde a nota deveria morar**, e ela
    já estava no banco sem ninguém usar: perguntar a um modelo de 4B "escolha
    entre estas 46 pastas" é um chute; perguntar ao índice "de que já falo
    parecido com isto, e onde essas notas moram" é uma medida.

    A busca é sobre o **começo** da transcrição de propósito: é onde o assunto
    é apresentado. O meio de uma aula de uma hora divaga.

    `excluir` tira uma nota do resultado — a própria, quando isto roda em cima
    de uma nota que já está indexada (`scripts/reprocessar_nota.py`). Sem isso a
    nota vira vizinha de si mesma, com distância ~0, e nasce um wikilink
    apontando para o próprio arquivo.
    """
    from app.conhecimento.busca import buscar  # tardio: evita import circular

    try:
        trechos = await buscar(texto[:1200], limite=n * 2, fonte_tipo="nota")
    except Exception as e:  # noqa: BLE001 — sem índice a nota ainda é salva
        logger.warning(f"Não consegui buscar vizinhos ({type(e).__name__}: {e}).")
        return []

    eu = excluir.resolve() if excluir else None
    achados: dict[Path, Vizinho] = {}
    for t in trechos:
        caminho = Path(str(t.fonte_ref).split("#")[0])
        if caminho in achados or not caminho.name.endswith(".md"):
            continue
        # A própria nota (mesmo arquivo, ou o mesmo nome noutra pasta depois de
        # eu tê-la movido) nunca é vizinha dela mesma.
        if eu and (caminho.resolve() == eu or caminho.name == eu.name):
            continue
        # Sem distância o trecho veio só do full-text, que casa palavra solta e
        # não sustenta "é do mesmo assunto".
        if t.distancia is None or t.distancia > DISTANCIA_MESMO_ASSUNTO:
            continue
        try:
            pasta = str(caminho.parent.relative_to(raiz))
        except ValueError:
            continue  # nota fora do vault (outra fonte configurada)
        achados[caminho] = Vizinho(
            titulo=(t.titulo or caminho.stem).split(" > ")[0],
            caminho=caminho,
            pasta="" if pasta == "." else pasta,
            distancia=t.distancia,
            # O primeiro chunk de cada nota é o mais próximo: `trechos` vem
            # ordenado, e só o primeiro de cada caminho chega aqui.
            trecho=" ".join((t.conteudo or "").split())[:_TRECHO_VIZINHO],
        )
        if len(achados) >= n:
            break
    return list(achados.values())


_TAG_NA_NOTA = re.compile(r"(?:^tags:\s*\[([^\]]*)\])|(?:(?:^|\s)#([a-zA-Z][\w/-]{1,30}))", re.M)


def tags_do_vault(raiz: Path, *, limite_arquivos: int = 400) -> list[str]:
    """As tags já em uso — para o modelo reaproveitar em vez de criar sinônimo."""
    contagem: dict[str, int] = {}
    for i, arquivo in enumerate(raiz.rglob("*.md")):
        if i >= limite_arquivos:
            break
        try:
            texto = arquivo.read_text(encoding="utf-8")[:2000]
        except (OSError, UnicodeDecodeError):
            continue
        for lista, solta in _TAG_NA_NOTA.findall(texto):
            for t in (lista.split(",") if lista else [solta]):
                t = t.strip().strip("\"'").lower()
                if t:
                    contagem[t] = contagem.get(t, 0) + 1
    return [t for t, _ in sorted(contagem.items(), key=lambda kv: -kv[1])]


# ── O caminho inteiro ─────────────────────────────────────────────


async def catalogar(
    corpo: str,
    *,
    tema: str,
    raiz_vault: Path,
    texto_da_busca: str | None = None,
    corrigidos: list[str] | None = None,
    ruido: list[str] | None = None,
    excluir: Path | None = None,
) -> Nota:
    """Corpo já reescrito → `Nota` catalogada: vizinhos, pasta, título, tags.

    A segunda metade de `processar`, separada porque a gravação ao vivo chega
    aqui com o corpo **pronto**: os blocos foram reescritos durante a aula, e o
    que sobrou para depois do `parar` é só isto.

    `texto_da_busca` é o texto limpo, e não o reescrito, porque é dele que sai a
    vizinhança — e o reescrito ainda pode estar sem um bloco quando o LLM caiu no
    meio. Sem ele, a busca usa o próprio corpo.
    """
    proximos = await vizinhos(texto_da_busca or corpo, raiz_vault, excluir=excluir)
    if proximos:
        logger.info(
            "Vizinhos: " + ", ".join(f"{v.titulo!r} ({v.pasta})" for v in proximos[:3])
        )

    ficha = await fichar(
        corpo,
        tema=tema,
        pastas=pastas_do_vault(raiz_vault),
        tags_do_vault=tags_do_vault(raiz_vault),
        proximos=proximos,
    )
    return Nota(
        fichamento=ficha, corpo=corpo, corrigidos=corrigidos or [], ruido=ruido or []
    )


async def processar(
    bruto: str,
    *,
    tema: str,
    raiz_vault: Path,
    glossario: dict[str, str] | None = None,
    reescrever_com_llm: bool = True,
    marcas: list[tuple[int, str]] | None = None,
    excluir: Path | None = None,
) -> Nota:
    """Transcrição crua → `Nota` pronta para salvar. Não escreve em disco."""
    g = glossario or carregar_glossario()
    texto, corrigidos, ruido = limpar(bruto, g)

    if marcas:
        # Glossário e filtro de ruído valem para os pedaços também: são eles que
        # viram os blocos quando a nota vem de gravação.
        marcas = [(seg, limpar(t, g)[0]) for seg, t in marcas]
        marcas = [(seg, t) for seg, t in marcas if t.strip()]
    corpo = (
        await reescrever(texto, tema=tema, marcas=marcas) if reescrever_com_llm else texto
    )

    # A vizinhança vem do texto **já corrigido pelo glossário**: buscar por
    # "pigvector" no índice não acha as notas sobre pgvector.
    return await catalogar(
        corpo,
        tema=tema,
        raiz_vault=raiz_vault,
        texto_da_busca=texto,
        corrigidos=corrigidos,
        ruido=ruido,
        excluir=excluir,
    )
