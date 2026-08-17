"""Transcrição bruta → nota de estudo.

O que se testa aqui é a parte determinística — glossário, segmentação, nome de
arquivo, frontmatter — porque é ela que decide se a nota fica achável. A
reescrita pelo LLM tem um teste só, e é o do guarda: **o modelo não pode
resumir**, e quando resume o texto original é que vale.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.conhecimento import transcricao as tr
from app.llm import gateway
from app.llm.tipos import RespostaCrua

GLOSSARIO = {
    "FastAPI": ["fast api", "fastapy"],
    "pgvector": ["pigvector", "pig vector"],
    "Python": ["paiton"],
}


@pytest.fixture
def glossario(tmp_path):
    arquivo = tmp_path / "glossario.json"
    arquivo.write_text(json.dumps({"_leia_me": "ignore isto", **GLOSSARIO}), encoding="utf-8")
    return tr.carregar_glossario(arquivo)


# ── glossário ─────────────────────────────────────────────────────


def test_carrega_nos_dois_formatos(glossario):
    assert glossario["fast api"] == "FastAPI"
    assert glossario["paiton"] == "Python"
    # `_leia_me` é comentário do arquivo, não regra de substituição.
    assert "_leia_me" not in glossario


def test_glossario_ausente_nao_quebra(tmp_path):
    assert tr.carregar_glossario(tmp_path / "nao-existe.json") == {}


def test_corrige_e_lista_o_que_trocou(glossario):
    texto, trocados = tr.aplicar_glossario(
        "o fast api usa paiton e guarda no pigvector", glossario
    )
    assert texto == "o FastAPI usa Python e guarda no pgvector"
    assert set(trocados) == {"fast api → FastAPI", "paiton → Python", "pigvector → pgvector"}


def test_corrige_ignorando_caixa_e_acento(glossario):
    texto, _ = tr.aplicar_glossario("Fast Api e PAITON", glossario)
    assert texto == "FastAPI e Python"


def test_nao_corrige_dentro_de_outra_palavra(glossario):
    """'paiton' dentro de 'paitonzinho' não é o termo — é outra palavra."""
    texto, trocados = tr.aplicar_glossario("paitonzinho", glossario)
    assert texto == "paitonzinho"
    assert trocados == []


def test_termo_ja_certo_nao_entra_na_lista_de_trocas(glossario):
    texto, trocados = tr.aplicar_glossario("uso FastAPI todo dia", glossario)
    assert texto == "uso FastAPI todo dia"
    assert trocados == []


def test_limpa_muleta_e_repeticao():
    assert "né" not in tr.limpar_fala("então isso aqui né é assim")
    assert tr.limpar_fala("o o o sistema roda") == "o sistema roda"


# ── segmentação ───────────────────────────────────────────────────


def test_texto_curto_fica_num_bloco_so():
    assert len(tr.blocos("Uma frase curta. E outra.")) == 1


def test_parte_no_fim_da_frase():
    texto = ". ".join(f"Frase número {i} com algumas palavras a mais" for i in range(400)) + "."
    partes = tr.blocos(texto, palavras=100)
    assert len(partes) > 1
    # Nenhum bloco começa no meio de uma frase.
    assert all(p[0].isupper() for p in partes)


def test_sobra_pequena_gruda_no_bloco_anterior():
    texto = " ".join(f"palavra{i}." for i in range(1000)) + " Fim."
    partes = tr.blocos(texto, palavras=400)
    assert partes[-1].endswith("Fim.")
    assert len(partes[-1].split()) > 4


# ── nome, tags e markdown ─────────────────────────────────────────


def test_nome_de_arquivo_sem_acento_nem_data():
    assert tr.nome_de_arquivo("Introdução ao RAG & Embeddings") == "introducao-ao-rag-embeddings.md"


def test_tags_normalizadas():
    assert tr._tags_limpas(["#Banco de Dados", "RAG", "rag"], "x") == ["banco-de-dados", "rag"]


def test_tags_caem_no_tema_quando_o_modelo_nao_deu_nenhuma():
    assert tr._tags_limpas([], "Busca Semântica") == ["busca-semantica"]


def test_markdown_traz_frontmatter_que_o_indexador_le():
    nota = tr.Nota(
        fichamento=tr.Fichamento(
            titulo="RAG na prática",
            resumo="Como montar busca semântica.",
            conceitos=["embedding", "pgvector"],
            tags=["rag", "pgvector"],
        ),
        corpo="## Conteúdo\n\nTexto.",
        corrigidos=["pigvector → pgvector"],
    )
    md = tr.montar_markdown(nota, fonte="gravação (sistema)", duracao_min=42)

    assert md.startswith("---\n")
    assert "tags: [rag, pgvector]" in md
    assert "tipo: transcricao" in md
    assert "duracao_min: 42" in md
    # O que o glossário trocou fica na nota: é como eu descubro o que corrigir.
    assert "pigvector → pgvector" in md

    # E o indexador tem que conseguir ler esse frontmatter de volta.
    from app.conhecimento.fontes import _frontmatter

    fm, corpo = _frontmatter(md)
    assert fm["tags"] == ["rag", "pgvector"]
    assert fm["tipo"] == "transcricao"
    assert corpo.lstrip().startswith("# RAG na prática")


def test_salvar_nao_sobrescreve_nota_existente(tmp_path):
    nota = tr.Nota(fichamento=tr.Fichamento(titulo="Igual", pasta="Estudos"), corpo="a")
    primeiro = tr.salvar(nota, raiz=tmp_path, fonte="x")
    segundo = tr.salvar(nota, raiz=tmp_path, fonte="x")
    assert primeiro != segundo
    assert primeiro.exists() and segundo.exists()


def test_pastas_do_vault_ignora_ocultas_e_de_sistema(tmp_path):
    for p in ("Estudos/Python", ".obsidian/plugins", "_inbox", "Bancos"):
        (tmp_path / p).mkdir(parents=True)
    pastas = tr.pastas_do_vault(tmp_path)
    assert "Estudos/Python" in pastas
    assert "Bancos" in pastas
    assert not any(p.startswith((".", "_")) for p in pastas)


# ── reescrita: o guarda contra resumo ─────────────────────────────


class LLMFalso:
    nome = "falso"

    def __init__(self, resposta: str) -> None:
        self.resposta = resposta

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        return RespostaCrua(texto=self.resposta, modelo=modelo)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


@pytest.fixture
def llm():
    def usar(resposta: str):
        gateway.usar_provider(LLMFalso(resposta))

    yield usar
    gateway.usar_provider(gateway.OllamaProvider())


async def test_reescrita_boa_e_aceita(llm):
    original = " ".join(["palavra"] * 100)
    reescrito = " ".join(["Palavra."] * 100)
    llm(reescrito)
    assert await tr.reescrever(original, tema="x") == reescrito


async def test_modelo_que_resume_e_descartado(llm):
    """Perder formatação é reversível; perder metade do conteúdo, não."""
    original = " ".join(["palavra"] * 100)
    llm("Resumo curtinho de tudo.")
    assert await tr.reescrever(original, tema="x") == original


# ── onde a nota mora (fase06 §6.6) ────────────────────────────────


def test_pastas_do_vault_vai_ate_o_terceiro_nivel(tmp_path):
    """Com profundidade 2, `Machine Learning/08 - LLMs` — o destino óbvio de uma
    aula sobre LLM — nunca aparecia como opção, e o modelo escolhia a menos
    errada entre as que via."""
    (tmp_path / "Pessoal/Machine Learning/08 - LLMs e IA Generativa").mkdir(parents=True)
    (tmp_path / "Pessoal/Bancos de Dados/IMG").mkdir(parents=True)
    pastas = tr.pastas_do_vault(tmp_path)

    assert "Pessoal/Machine Learning/08 - LLMs e IA Generativa" in pastas
    # Pasta de arquivo não é destino de nota de estudo.
    assert not any(p.endswith("IMG") for p in pastas)


def test_pasta_do_modelo_vale_quando_existe_e_ha_vizinho():
    """Com vizinho perto, o modelo escolhe entre pastas que fazem sentido — e
    ele vê o texto inteiro, que os vizinhos não veem."""
    pastas = ["Estudos/IA", "Estudos/Banco"]
    proximos = [tr.Vizinho("RAG", Path("/v/Estudos/Banco/rag.md"), "Estudos/Banco")]
    assert tr._pasta_escolhida("Estudos/IA", pastas, proximos) == "Estudos/IA"


def test_pasta_inventada_cai_para_a_dos_vizinhos():
    """Criar pasta por erro de digitação de um 4B é como um vault vira duas
    árvores paralelas do mesmo assunto."""
    proximos = [
        tr.Vizinho("RAG", Path("/v/ML/rag.md"), "ML"),
        tr.Vizinho("Vector Stores", Path("/v/ML/vs.md"), "ML"),
        tr.Vizinho("SQL", Path("/v/Banco/sql.md"), "Banco"),
    ]
    assert tr._pasta_escolhida("Estudos/LLM", ["ML", "Banco"], proximos) == "ML"


def test_sem_vizinho_vai_para_o_inbox_mesmo_com_pasta_valida():
    """Sem vizinho, o palpite do modelo não vale: ele escolheu a menos errada
    de 46 pastas que não falam do assunto. Foi assim que uma transcrição sobre
    carro elétrico foi parar em 'Machine Learning / LLMs' no teste real."""
    assert tr._pasta_escolhida("ML", ["ML", "Banco"], []) == "_inbox"
    assert tr._pasta_escolhida(None, [], []) == "_inbox"


def test_vizinho_distante_nao_conta_como_vizinho():
    """0,52 é a distância de um assunto que o vault não tem. Ver a medição na
    constante DISTANCIA_MESMO_ASSUNTO."""
    assert tr.DISTANCIA_MESMO_ASSUNTO < 0.48
    assert tr.DISTANCIA_MESMO_ASSUNTO > 0.43


def test_tag_longa_e_cortada_no_hifen():
    """`processamento-de-linguagem-natur` não casa com nada e não quer dizer
    nada — pior que a tag longa que ela substituiu."""
    assert tr._encurtar_tag("processamento-de-linguagem-natural") == "processamento-de-linguagem"
    assert tr._encurtar_tag("rag") == "rag"


def test_nota_nasce_com_wikilink_para_as_vizinhas():
    """146 das 232 notas do vault se ligam entre si; uma transcrição órfã fica
    de fora dessa teia — existe, mas não é encontrada por quem navega."""
    nota = tr.Nota(
        fichamento=tr.Fichamento(
            titulo="Embeddings na prática",
            relacionadas=["[[03 - RAG]]", "[[04 - Vector Stores]]"],
        ),
        corpo="## Conteúdo\n\nTexto.",
    )
    md = tr.montar_markdown(nota, fonte="gravação")
    assert "## Relacionado" in md
    assert "[[03 - RAG]]" in md

    # E o indexador tem que enxergar os wikilinks como metadado.
    from app.conhecimento.fontes import _tags_e_links

    meta = _tags_e_links(md, {})
    assert "03 - RAG" in meta["wikilinks"]


def test_indice_da_pasta_ganha_a_nota_sem_ser_reescrito(tmp_path):
    """O índice é escrito à mão, com ordem pensada. Só se acrescenta a ele."""
    pasta = tmp_path / "Machine Learning"
    pasta.mkdir(parents=True)
    indice = pasta / "_Índice Machine Learning.md"
    original = "---\ntags: [indice, moc]\n---\n\n# Índice\n\n## Base\n\n1. [[01 - Intro]]\n"
    indice.write_text(original, encoding="utf-8")

    nota = tr.Nota(
        fichamento=tr.Fichamento(
            titulo="Embeddings", pasta="Machine Learning", resumo="O que é um vetor. E mais."
        ),
        corpo="texto",
    )
    tr.salvar(nota, raiz=tmp_path, fonte="gravação")

    novo = indice.read_text(encoding="utf-8")
    assert original.strip() in novo, "o índice original não pode ser reescrito"
    assert "## Transcrições" in novo
    assert "[[embeddings]]" in novo
    assert "O que é um vetor." in novo


def test_nota_nao_entra_duas_vezes_no_indice(tmp_path):
    pasta = tmp_path / "ML"
    pasta.mkdir(parents=True)
    (pasta / "_Índice ML.md").write_text("# Índice\n", encoding="utf-8")
    ficha = tr.Fichamento(titulo="Embeddings", pasta="ML")

    tr._anotar_no_indice(pasta, pasta / "embeddings.md", ficha)
    tr._anotar_no_indice(pasta, pasta / "embeddings.md", ficha)

    assert (pasta / "_Índice ML.md").read_text(encoding="utf-8").count("[[embeddings]]") == 1


def test_pasta_sem_indice_nao_quebra(tmp_path):
    nota = tr.Nota(fichamento=tr.Fichamento(titulo="Solta", pasta="Nova"), corpo="x")
    assert tr.salvar(nota, raiz=tmp_path, fonte="x").exists()


# ── timestamps e destaques (fase06 §6.8) ──────────────────────────


def test_blocos_com_tempo_agrupam_pedacos_inteiros():
    """Agrupar pedaços inteiros — e não cortar por frase — é o que dá a cada
    bloco um instante exato do vídeo."""
    marcas = [(i * 20, " ".join(["palavra"] * 200)) for i in range(6)]
    blocos = tr.blocos_com_tempo(marcas, palavras=400)

    assert [s for s, _ in blocos] == [0, 40, 80]
    assert all(len(t.split()) >= 400 for _, t in blocos[:-1])


def test_relogio():
    assert tr.relogio(0) == "00:00"
    assert tr.relogio(20) == "00:20"
    assert tr.relogio(3725) == "62:05"


async def test_reescrita_carimba_o_instante_do_video(llm):
    """`⏱ 08:20` é o que me faz conseguir voltar na fonte para rever."""
    llm(" ".join(["Palavra."] * 300))
    marcas = [(i * 20, " ".join(["palavra"] * 200)) for i in range(6)]
    corpo = await tr.reescrever("", tema="x", marcas=marcas)

    # 6 pedaços de 200 palavras com teto de 600 = blocos aos 0 s e aos 60 s.
    assert "`⏱ 00:00`" in corpo
    assert "`⏱ 01:00`" in corpo


async def test_sem_marcas_nao_inventa_timestamp(llm):
    """Arquivo e YouTube não têm instante conhecido: melhor sem do que chutado."""
    llm(" ".join(["Palavra."] * 100))
    corpo = await tr.reescrever(" ".join(["palavra"] * 100), tema="x")
    assert "⏱" not in corpo


def test_destaques_aparecem_no_topo_da_nota():
    """A seção que decide se a nota vale a releitura ou se eu reassisto o vídeo."""
    nota = tr.Nota(
        fichamento=tr.Fichamento(
            titulo="Índices",
            destaques=["A casa sempre tem margem", "Índice acelera leitura e atrasa escrita."],
        ),
        corpo="## Conteúdo\n\nTexto.",
    )
    md = tr.montar_markdown(nota, fonte="gravação")

    assert "## Para lembrar" in md
    assert md.index("## Para lembrar") < md.index("## Conteúdo")
    # Frase sem ponto final ganha um: é lista de frases, não de títulos.
    assert "- **A casa sempre tem margem.**" in md
    assert "- **Índice acelera leitura e atrasa escrita.**" in md


def test_destaque_que_e_tarefa_de_estudo_e_descartado():
    """"Aprenda a usar tabelas verdade" parece útil e não serve para nada:
    daqui a um mês eu leio isso e continuo sem saber usar tabela verdade."""
    bruto = [
        "Entenda a importância da lógica proposicional para concursos.",
        "O número de linhas de uma tabela verdade é 2^n, com n = proposições.",
        "Domine o conceito de VIF para aplicações em programação.",
        "Sentença aberta, com incógnita, não é proposição.",
        "Tabela verdade",
    ]
    limpos = tr._destaques_limpos(bruto)
    assert limpos == [
        "O número de linhas de uma tabela verdade é 2^n, com n = proposições.",
        "Sentença aberta, com incógnita, não é proposição.",
    ]


async def test_vizinhos_excluem_a_propria_nota(tmp_path, monkeypatch):
    """Reprocessar uma nota já indexada a fazia virar vizinha de si mesma, e
    nascer um wikilink apontando para o próprio arquivo."""
    from app.conhecimento import busca

    eu = tmp_path / "Estudos" / "logica.md"
    outra = tmp_path / "Estudos" / "conjuntos.md"
    eu.parent.mkdir(parents=True)

    def falso(*_, **__):
        async def resposta():
            return [
                busca.Trecho(id=uuid4(), fonte_tipo="nota", fonte_ref=str(eu),
                             ordem=0, titulo="Lógica", conteudo="x", distancia=0.01),
                busca.Trecho(id=uuid4(), fonte_tipo="nota", fonte_ref=str(outra),
                             ordem=0, titulo="Conjuntos", conteudo="y", distancia=0.30),
            ]

        return resposta()

    monkeypatch.setattr(busca, "buscar", falso)
    achados = await tr.vizinhos("lógica proposicional", tmp_path, excluir=eu)

    assert [v.titulo for v in achados] == ["Conjuntos"]


async def test_fichamento_com_lista_no_lugar_do_objeto_nao_derruba(llm):
    """Um modelo pequeno às vezes responde `[...]` no lugar de `{...}`.
    Sem checagem, o `.get` estoura e o fichamento inteiro cai."""
    llm('[{"titulo": "errado"}]')
    ficha = await tr.fichar("texto", tema="Meu Tema", pastas=[], tags_do_vault=[])
    assert ficha.titulo == "Meu Tema"


# ── ruído de vídeo (fase06 §6.7) ──────────────────────────────────


def test_ruido_de_video_sai_por_codigo():
    """Estava no prompt e competia com "NÃO resuma": numa rodada o modelo tirava
    a abertura, na seguinte mantinha e cortava conteúdo."""
    texto = (
        "Olá, meus amigos. Aqui é o professor Vaguinho. "
        "Uma proposição é uma frase com sujeito e declaração. "
        "Se ainda não se inscreveu no meu canal, clica em inscrever. "
        "O número de linhas da tabela verdade é 2 elevado a n. "
        "Um beijo grande para vocês, até a próxima."
    )
    limpo, removidas = tr.limpar_ruido(texto)

    assert "proposição é uma frase" in limpo
    assert "2 elevado a n" in limpo
    assert "inscrever" not in limpo
    assert "professor Vaguinho" not in limpo
    assert "até a próxima" not in limpo
    assert len(removidas) == 4   # saudação, apresentação, inscrição, despedida


def test_conteudo_parecido_com_ruido_fica():
    """"No vídeo 2 você aprende conectivos" é estrutura do curso — me diz o que
    estudar depois, e some junto se o filtro for ganancioso."""
    texto = (
        "No vídeo 2 vocês vão aprender os conectivos. "
        "A banca CESPE cobra a definição de proposição."
    )
    limpo, removidas = tr.limpar_ruido(texto)
    assert removidas == []
    assert limpo == texto


def test_ruido_vai_para_a_nota_e_nao_some_calado():
    nota = tr.Nota(
        fichamento=tr.Fichamento(titulo="Lógica"),
        corpo="## Conteúdo\n\nTexto.",
        ruido=["Se inscreve no canal.", "Até a próxima."],
    )
    md = tr.montar_markdown(nota, fonte="gravação")
    assert "descartadas como ruído" in md
    assert "Se inscreve no canal." in md


def test_amostra_do_fichamento_cobre_a_aula_inteira():
    """Com `corpo[:3000]` o modelo fichava só a abertura, e os destaques saíam
    vagos — ele não tinha visto nada concreto para destacar."""
    corpo = (
        "abertura " * 400
        + "\n## Tabela Verdade\n"
        + "meio " * 900
        + "\n## Fórmula\n"
        + "a formula e 2 elevado a n. " * 60
    )
    amostra = tr._amostra_para_fichar(corpo)

    assert "## Tabela Verdade" in amostra
    assert "## Fórmula" in amostra
    assert "2 elevado a n" in amostra, "o fim da aula precisa aparecer"
    assert len(amostra) < len(corpo)


def test_nota_curta_vai_inteira_para_o_fichamento():
    corpo = "uma nota curta de estudo."
    assert tr._amostra_para_fichar(corpo) == corpo


def test_professor_x_aqui_tambem_e_ruido():
    """A ordem invertida ("Professor Vaguinho aqui") escapou na segunda aula:
    o padrão só cobria "aqui é o professor"."""
    limpo, removidas = tr.limpar_ruido(
        "Professor Vaguinho aqui. Negar é dizer a ideia contraria."
    )
    assert removidas == ["Professor Vaguinho aqui."]
    assert "ideia contraria" in limpo


def test_correcao_com_contexto_nao_pega_a_palavra_legitima():
    """`tosse -> torce` so vale com a preposicao de torcida junto: "tosse" e
    palavra de verdade, e uma regra global estragaria "tosse muito de gripe"."""
    g = tr.carregar_glossario()
    texto, trocas = tr.aplicar_glossario(
        "Jose tosse pro Bahia, mas ele tosse muito quando esta gripado.", g
    )
    assert "torce pro Bahia" in texto
    assert "ele tosse muito" in texto
    assert trocas == ["tosse pro → torce pro"]


def test_amostra_abre_pelo_roteiro_e_nao_pelo_comeco():
    """Abrindo com 2.500 caracteres do inicio, o modelo ancorava neles: uma aula
    de 26 min sobre quatro conectivos virou a nota "Negacao em Logica
    Proposicional", com os dois destaques falando so de negacao."""
    corpo = (
        "so sobre negacao " * 300
        + "\n## Conjuncao\n" + "texto " * 400
        + "\n## Disjuncao Exclusiva\n" + "texto " * 400
    )
    amostra = tr._amostra_para_fichar(corpo)

    assert amostra.startswith("ROTEIRO DA AULA")
    # O escopo inteiro aparece antes de qualquer detalhe.
    assert amostra.index("## Disjuncao Exclusiva") < amostra.index("COMEÇO DA AULA")


def test_titulos_do_modelo_ficam_dentro_de_conteudo():
    """O modelo escreve `##`, que no documento final fica no mesmo nivel de
    "Para lembrar" — o indice do Obsidian mostrava os assuntos da aula como
    irmaos das secoes da nota."""
    assert tr._aninhar_titulos("## Conectivos\ntexto\n### Negacao\n") == (
        "### Conectivos\ntexto\n#### Negacao\n"
    )
    # Texto sem titulo passa intacto.
    assert tr._aninhar_titulos("so um paragrafo") == "so um paragrafo"


def test_destaque_que_so_afirma_importancia_e_descartado():
    """"A logica proposicional e fundamental para as provas" ocupa uma linha da
    secao que existe para eu nao reassistir o video, e nao diz uma regra."""
    limpos = tr._destaques_limpos([
        "A logica proposicional e fundamental para o raciocinio logico e as provas.",
        "Os recursos de estudo incluem o treinamento pratico com o conectivo OU.",
        "A negacao de P e verdadeira exatamente quando P e falsa.",
    ])
    assert limpos == ["A negacao de P e verdadeira exatamente quando P e falsa."]


def test_latex_vira_simbolo_de_verdade():
    """A nota tem que mostrar `p → q`, nao `$p \\rightarrow q$`. O prompt pede o
    simbolo e o modelo escreve LaTeX assim mesmo — as duas ultimas aulas
    gravadas sairam com `\\neg` e `\\rightarrow` nos destaques."""
    f = tr.latex_para_simbolo
    assert f(r"$p \rightarrow q$") == "p → q"
    assert f(r"$p \leftrightarrow q$") == "p ↔ q"
    assert f(r"\neg P, P \land Q, P \lor Q, P \oplus Q") == "¬ P, P ∧ Q, P ∨ Q, P ⊕ Q"
    assert f("texto sem latex") == "texto sem latex"
    assert f("$P$") == "P"


def test_destaque_com_latex_sai_legivel():
    limpos = tr._destaques_limpos([r"O condicional e representado por $p \rightarrow q$ na tabela."])
    assert limpos == ["O condicional e representado por p → q na tabela."]
