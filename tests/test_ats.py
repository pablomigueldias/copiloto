"""As regras que o parser cobra do texto — datas, siglas e taxonomia.

São testes de código puro: nenhum modelo participa. É de propósito. Pedir ao
LLM "use sempre MM/AAAA" reduz a frequência do erro; normalizar depois elimina,
e o que elimina é o que dá para travar em teste.
"""
from __future__ import annotations

import pytest

from app.candidatura import ats

# ── Datas ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("abr/2025 – set/2025", "04/2025 – 09/2025"),
        ("ago/2024 – dez/2026", "08/2024 – 12/2026"),
        ("Abril de 2025 até Setembro de 2025", "04/2025 – 09/2025"),
        ("04/2025 - 09/2025", "04/2025 – 09/2025"),
        ("jan 2025 - atual", "01/2025 – atual"),
        ("desde março de 2024", "03/2024 – atual"),
        ("2024-2026", "2024 – 2026"),
    ],
)
def test_periodo_vira_um_formato_so(bruto, esperado):
    """O ATS calcula tempo de casa e procura lacunas: formato misturado o
    confunde, e entrada de data ilegível é recusa automática em vários."""
    assert ats.periodo(bruto) == esperado


def test_periodo_ja_normalizado_nao_muda():
    assert ats.periodo("04/2025 – 09/2025") == "04/2025 – 09/2025"


def test_periodo_que_nao_da_para_ler_volta_igual():
    """Campo apagado é pior que campo estranho — e o aviso de ATS cobra o mês."""
    assert ats.periodo("um tempo por lá") == "um tempo por lá"
    assert ats.periodo(None) == ""


def test_ano_solto_continua_ano_solto():
    """Inventar o mês seria mentir uma data."""
    assert ats.periodo("2025") == "2025"


# ── Siglas ────────────────────────────────────────────────────────


def test_sigla_ganha_o_extenso_na_primeira_ocorrencia():
    expandir = ats.expansor()
    assert expandir("Trabalho com RAG e LLMs.") == (
        "Trabalho com RAG (Retrieval-Augmented Generation) e "
        "LLMs (Large Language Models)."
    )


def test_sigla_nao_repete_o_extenso():
    """Repetir o extenso em todo bullet é o padrão que os ATS de 2026 marcam
    como manipulação de palavra-chave."""
    expandir = ats.expansor()
    expandir("Construí um sistema de RAG.")
    assert expandir("Outro bullet com RAG.") == "Outro bullet com RAG."


def test_extenso_escrito_a_mao_e_respeitado():
    expandir = ats.expansor()
    texto = "Usei RAG (Retrieval-Augmented Generation) no Copiloto."
    assert expandir(texto) == texto
    assert expandir("Depois, RAG de novo.") == "Depois, RAG de novo."


def test_sigla_em_minuscula_nao_e_sigla():
    """`ia` é verbo em português e `\\bml\\b` casaria com qualquer lixo."""
    expandir = ats.expansor()
    assert expandir("Ele ia embora e ml não é nada.") == "Ele ia embora e ml não é nada."


def test_sigla_dentro_de_palavra_nao_e_tocada():
    expandir = ats.expansor()
    assert expandir("MIA e LLMS_TESTE") == "MIA e LLMS_TESTE"


def test_llms_nao_vira_llm_mais_s():
    """Sem ordenar por tamanho, 'LLM' comeria o começo de 'LLMs'."""
    assert ats.expansor()("Integrei LLMs.") == "Integrei LLMs (Large Language Models)."


# ── Taxonomia ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "habilidade,categoria",
    [
        ("Python", "Linguagens"),
        ("SQL", "Linguagens"),
        ("SQLAlchemy 2.0 async", "Frameworks e Arquitetura"),
        ("React / Next.js", "Frameworks e Arquitetura"),
        ("API REST", "Frameworks e Arquitetura"),
        ("Machine Learning (scikit-learn)", "IA e Machine Learning"),
        ("RAG / busca semântica", "IA e Machine Learning"),
        ("Ollama / LLM local", "IA e Machine Learning"),
        ("pgvector", "Dados e Pipelines"),
        ("Alembic", "Dados e Pipelines"),
        ("Docker / docker-compose", "DevOps e Infraestrutura"),
        ("Deploy em VPS (Linux/SSH)", "DevOps e Infraestrutura"),
        ("Autenticação e segurança", "DevOps e Infraestrutura"),
        ("pytest", "Testes, Qualidade e Processo"),
        ("Playwright", "Testes, Qualidade e Processo"),
        ("ruff / lint", "Testes, Qualidade e Processo"),
    ],
)
def test_habilidade_cai_na_categoria_canonica(habilidade, categoria):
    """O rótulo é declaração sobre o item: a triagem por skills mapeia esta
    seção para os critérios da vaga antes de ler qualquer outra coisa."""
    assert ats.categoria_de(habilidade) == categoria


def test_o_que_a_tabela_nao_conhece_vai_para_ferramentas():
    """Balde genérico no fim é melhor que habilidade na categoria errada."""
    assert ats.categoria_de("Zoho One") == ats.FERRAMENTAS
    assert ats.categoria_de("") == ats.FERRAMENTAS


def test_git_nao_e_github():
    assert ats.categoria_de("Git") == "DevOps e Infraestrutura"


def test_separadores_sao_ascii():
    """O `·` saiu porque extração malfeita cola dois termos quando descarta o
    glifo — e uma habilidade perdida na seção mais lida do currículo é cara."""
    assert ats.SEP_LISTA.isascii() and ats.SEP_CAMPO.isascii()


@pytest.mark.parametrize(
    "habilidade,categoria",
    [
        ("Amazon Bedrock", "IA e Machine Learning"),
        ("Claude 3 Haiku", "IA e Machine Learning"),
        ("Gemini", "IA e Machine Learning"),
        ("AWS Step Functions", "DevOps e Infraestrutura"),
        ("IAM", "DevOps e Infraestrutura"),
    ],
)
def test_servico_de_nuvem_cai_na_categoria_certa(habilidade, categoria):
    """Bedrock é serviço de IA, Step Functions é orquestração: numa vaga de IA
    os dois pesam, mas em categorias diferentes."""
    assert ats.categoria_de(habilidade) == categoria


def test_termo_composto_nao_e_partido_ao_meio():
    """"IA (Inteligência Artificial) generativa" quebra justamente a expressão
    que a vaga procura inteira — e a ocorrência não conta como vista."""
    expandir = ats.expansor()
    assert expandir("bootcamp de IA generativa") == "bootcamp de IA generativa"
    # A sigla sozinha, depois, continua ganhando o extenso.
    assert expandir("e IA em produção") == "e IA (Inteligência Artificial) em produção"


def test_llm_local_continua_inteiro():
    assert ats.expansor()("Rodei LLM local no Ollama") == "Rodei LLM local no Ollama"


# ── A ordem do contato, que o jsonb destrói (20/08/2026) ──────────


def test_contato_sai_na_ordem_do_ats_e_nao_na_do_banco():
    # Exatamente o que o Postgres devolveu do `pessoal_perfil_mestre`: chaves
    # ordenadas por tamanho, depois por byte.
    do_banco = {
        "email": "p@x.dev",
        "github": "https://github.com/p",
        "linkedin": "https://linkedin.com/in/p",
        "telefone": "(11) 90000-0000",
        "localizacao": "Santo André, SP",
    }
    rotulos = [r for r, _ in ats.contato_ordenado(do_banco)]
    # Cidade/UF primeiro: muitos ATS filtram por localização antes de ler o
    # resto, e palavra-chave no começo pesa mais que no fim.
    assert rotulos == ["local", "tel", "email", "linkedin", "github"]


def test_contato_com_chave_desconhecida_nao_some():
    # Perder um contato porque ninguém cadastrou o rótulo é pior que exibi-lo
    # cru — e ele vai para o fim, não para a frente da cidade.
    saida = ats.contato_ordenado({"blog": "b.dev", "localizacao": "Santo André, SP"})
    assert saida == [("local", "Santo André, SP"), ("blog", "b.dev")]


def test_contato_vazio_nao_vira_rotulo_orfao():
    # `tel: ` sozinho no PDF é campo faltando com aparência de campo presente.
    assert ats.contato_ordenado({"telefone": "  ", "email": "p@x.dev"}) == [
        ("email", "p@x.dev")
    ]


# ── Barra que junta dois termos (20/08/2026) ──────────────────────


def test_barra_com_espaco_separa_dois_termos():
    # Medido no currículo da Accenture: o casador de skills compara o item
    # INTEIRO, e "pandas / numpy" não é "pandas" nem "NumPy". Os dois somem da
    # triagem apesar de estarem impressos na página.
    assert ats.separar_pares(["pandas / numpy"]) == ["pandas", "numpy"]
    assert ats.separar_pares(["WordPress / WHM / cPanel"]) == ["WordPress", "WHM", "cPanel"]


def test_barra_colada_faz_parte_do_nome_e_nao_separa():
    # Quebrar aqui destruiria o termo — e é o oposto do que se quer.
    for termo in ["ECS/Fargate", "CI/CD", "Deploy em VPS (Linux/SSH)", "IA/ML"]:
        assert ats.separar_pares([termo]) == [termo]


def test_separar_nao_repete_o_que_ja_apareceu():
    assert ats.separar_pares(["Docker / docker-compose", "Docker"]) == [
        "Docker",
        "docker-compose",
    ]


def test_pedaco_separado_ainda_acha_a_categoria():
    # `separar_pares` cria fragmentos que a taxonomia precisa conhecer, senão a
    # competência mais relevante da vaga cai no balde genérico.
    assert ats.categoria_de("LLM local") == "IA e Machine Learning"
    assert ats.categoria_de("worker assíncrono") == "Frameworks e Arquitetura"
    assert ats.categoria_de("busca semântica") == "IA e Machine Learning"


def test_pipeline_de_dados_nao_cai_em_ferramentas():
    """O rótulo da categoria é lido como declaração sobre o item.

    "Pipeline de dados" em *Ferramentas* é a competência mais relevante de uma
    vaga de dados enterrada no balde genérico do fim da seção.
    """
    assert ats.categoria_de("Pipeline de dados (ingestão e indexação)") == "Dados e Pipelines"
    assert ats.categoria_de("Observabilidade") == "DevOps e Infraestrutura"


# ── Campo que não pode quebrar em duas linhas ─────────────────────


def test_indivisivel_prende_o_rotulo_ao_valor():
    # `linkedin:` saía no fim de uma linha e a URL na seguinte; um parser que
    # lê linha a linha perde o valor.
    assert ats.indivisivel("linkedin: exemplo.com/p") == "linkedin:\xa0exemplo.com/p"
    # O `\xa0` sai do pdftotext como espaço comum: não é caractere estranho.
    assert ats.indivisivel("a b").replace("\xa0", " ") == "a b"
