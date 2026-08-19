"""O gerador de currículo — e a regra que impede o currículo de mentir.

Os testes de rejeição são os mais importantes do projeto inteiro: um bullet com
"Kubernetes" que eu nunca usei não é bug de formatação, é reprovação em
entrevista técnica com a minha cara na frente.
"""
from __future__ import annotations

import json

import pytest

from app.candidatura import curriculo as cur
from app.candidatura.extrator import Requisitos
from app.candidatura.match import Match
from app.candidatura.perfil import montar_fatos
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.llm import gateway
from app.llm.tipos import LLMIndisponivel, RespostaCrua

PERFIL = PerfilMestre(
    nome="Pablo Miguel Dias Ortiz",
    resumo="Desenvolvedor Python com foco em APIs e LLMs.",
    contato={"email": "pablo@exemplo.dev"},
    habilidades=[
        {"nome": "Python"}, {"nome": "FastAPI"}, {"nome": "PostgreSQL"}, {"nome": "Docker"},
    ],
    projetos=[
        {
            "nome": "Copiloto",
            "descricao": "Assistente local com RAG",
            "prova": "1.773 chunks indexados, 216 testes",
            "stack": ["Python", "FastAPI", "PostgreSQL", "pgvector"],
        },
        {"nome": "Churn Prediction", "descricao": "ML de evasão",
         "stack": ["pandas", "scikit-learn"]},
    ],
    experiencias=[{"empresa": "Sechat", "cargo": "Analista de Sistemas", "periodo": "2025",
                   "descricao": "Zoho One e site em Next.js"}],
    formacao=[{"instituicao": "Impacta", "curso": "ADS", "periodo": "2026"}],
    certificacoes=[
        {"nome": "SQL 2016 - T-SQL", "tema": "banco de dados"},
        {"nome": "Fundamentos de Machine Learning", "tema": "machine learning"},
    ],
)
FATOS = montar_fatos(PERFIL)
REQ = Requisitos(obrigatorios=["Python", "FastAPI"], stack=["PostgreSQL"], resumo="APIs")
MATCH = Match(score=80, destaques=["Copiloto"])


class LLMFalso:
    nome = "falso"

    def __init__(self, resposta: dict | None = None, quebrado: bool = False) -> None:
        self.resposta = resposta or {}
        self.quebrado = quebrado
        self.prompts: list[str] = []

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.prompts.append(prompt)
        if self.quebrado:
            raise LLMIndisponivel("fora do ar")
        return RespostaCrua(texto=json.dumps(self.resposta, ensure_ascii=False), modelo=modelo)

    async def embedar(self, textos, *, modelo):
        return [[0.01] * 1024 for _ in textos]


def usar(**kw) -> LLMFalso:
    p = LLMFalso(**kw)
    gateway.usar_provider(p)
    return p


@pytest.fixture(autouse=True)
def restaura():
    yield
    gateway.usar_provider(gateway.OllamaProvider())


async def gerar(resposta: dict, **kw):
    usar(resposta=resposta)
    return await cur.gerar(
        fatos=FATOS, requisitos=REQ, match=MATCH,
        titulo_vaga="Dev Python Pleno", descricao_vaga="Vaga de API em Python",
        usar_few_shot=False, **kw,
    )


BOA = {
    "titulo": "Desenvolvedor Python Pleno",
    "resumo": "Construí APIs em FastAPI com PostgreSQL e integrei modelos locais.",
    "competencias": [
        {"categoria": "Linguagens", "itens": ["Python"]},
        {"categoria": "Backend", "itens": ["FastAPI", "PostgreSQL"]},
    ],
    "experiencias": [
        {"empresa": "Sechat", "bullets": ["Mantive o site em Next.js", "Integrei módulos do Zoho One"]}
    ],
    "projetos": [
        {"nome": "Copiloto", "bullets": [
            "Indexei 1.773 chunks em PostgreSQL com pgvector",
            "Construí a API em FastAPI com testes automatizados",
        ]}
    ],
}


# ── Caminho feliz ─────────────────────────────────────────────────


async def test_gera_curriculo_a_partir_do_perfil():
    c = await gerar(BOA)

    assert c.resumo.startswith("Construí APIs")
    # O título é o do anúncio, não o que o modelo achou que o cargo era.
    assert c.titulo == "Dev Python Pleno"
    # Competências agrupadas — herdado do gerador do Prospector.
    assert c.competencias[0] == {"categoria": "Linguagens", "itens": ["Python"]}
    assert c.competencias_planas == ["Python", "FastAPI", "PostgreSQL"]
    assert c.projetos[0]["nome"] == "Copiloto" and len(c.projetos[0]["bullets"]) == 2
    assert c.rejeitados == []
    # Fatos que não passam pelo modelo: vêm direto do perfil.
    assert c.experiencias[0]["empresa"] == "Sechat"
    assert c.experiencias[0]["cargo"] == "Analista de Sistemas"
    assert c.experiencias[0]["bullets"][0] == "Mantive o site em Next.js"
    assert c.formacao[0]["instituicao"] == "Impacta"


async def test_numero_do_perfil_sobrevive():
    c = await gerar(BOA)
    assert "1.773" in c.projetos[0]["bullets"][0]


# ── Anti-alucinação ───────────────────────────────────────────────


async def test_bullet_com_tecnologia_inventada_e_derrubado():
    c = await gerar({
        **BOA,
        "projetos": [{"nome": "Copiloto", "bullets": [
            "Orquestrei os serviços com Kubernetes em produção",
            "Construí a API em FastAPI",
        ]}],
    })

    assert c.projetos[0]["bullets"] == ["Construí a API em FastAPI"]
    assert any("Kubernetes" in r or "kubernetes" in r for r in c.rejeitados)


async def test_projeto_inexistente_e_derrubado():
    c = await gerar({
        **BOA,
        "projetos": [
            {"nome": "Sistema Bancário XP", "bullets": ["Liderei a migração"]},
            {"nome": "Copiloto", "bullets": ["Construí a API em FastAPI"]},
        ],
    })

    assert [p["nome"] for p in c.projetos] == ["Copiloto"]
    assert any("Sistema Bancário XP" in r for r in c.rejeitados)


async def test_competencia_inventada_nao_entra():
    c = await gerar({**BOA, "competencias": [
        {"categoria": "Infra", "itens": ["Python", "Kubernetes", "Salesforce"]}
    ]})
    # A seção mais lida pelo ATS é a mais fácil de inventar.
    # E a categoria é a canônica, não o rótulo que o modelo inventou.
    assert c.competencias == [{"categoria": "Linguagens", "itens": ["Python"]}]


async def test_experiencia_inventada_e_derrubada():
    c = await gerar({**BOA, "experiencias": [
        {"empresa": "Google", "bullets": ["Liderei o time de busca"]}
    ]})
    # A empresa que existe continua no currículo (fato do perfil); a inventada
    # não entra de jeito nenhum.
    assert [e["empresa"] for e in c.experiencias] == ["Sechat"]
    assert any("Google" in r for r in c.rejeitados)


async def test_bullet_de_experiencia_com_invencao_e_derrubado():
    c = await gerar({**BOA, "experiencias": [
        {"empresa": "Sechat", "bullets": ["Migrei tudo para AWS Lambda", "Mantive o site"]}
    ]})
    assert c.experiencias[0]["bullets"] == ["Mantive o site"]


async def test_experiencia_sem_bullet_aprovado_usa_o_perfil():
    c = await gerar({**BOA, "experiencias": []})
    # Melhor a descrição do perfil que uma experiência sem uma linha sequer.
    assert c.experiencias[0]["bullets"] == ["Zoho One e site em Next.js"]


async def test_avisa_experiencia_sem_mes():
    c = await gerar(BOA)
    # Parte dos ATS de 2026 recusa automaticamente entrada sem data completa.
    assert any("sem mês" in a for a in c.avisos)


async def test_resumo_com_invencao_cai_para_o_do_perfil():
    c = await gerar({**BOA, "resumo": "Especialista em Kubernetes e Terraform."})
    # `startswith` e não `==`: o resumo do perfil também passa pela expansão de
    # siglas antes de virar documento.
    assert c.resumo.startswith("Desenvolvedor Python com foco em APIs e LLMs")
    assert any("resumo" in r for r in c.rejeitados)


async def test_tudo_rejeitado_ainda_produz_curriculo():
    c = await gerar({**BOA, "projetos": [
        {"nome": "Inventado", "bullets": ["fiz coisas com Kubernetes"]}
    ]})
    # Página em branco é pior que o texto do próprio perfil.
    assert c.projetos and c.projetos[0]["nome"] == "Copiloto"


def test_verificar_aponta_a_primeira_invencao():
    assert cur.verificar("Usei FastAPI e Kubernetes", FATOS) == "kubernetes"
    assert cur.verificar("Usei FastAPI com PostgreSQL", FATOS) is None


def test_verificar_nao_confunde_portugues_com_tecnologia():
    # Sem isto, "Desenvolvi" e "Automatizei" virariam "tecnologia inventada".
    assert cur.verificar("Desenvolvi APIs REST e automatizei o Pipeline", FATOS) is None


# ── Degradação ────────────────────────────────────────────────────


async def test_llm_fora_do_ar_devolve_o_perfil_cru():
    usar(quebrado=True)
    c = await cur.gerar(
        fatos=FATOS, requisitos=REQ, match=MATCH, titulo_vaga="Dev Python",
        descricao_vaga="x", usar_few_shot=False,
    )
    assert c.resumo.startswith("Desenvolvedor Python com foco") and c.projetos
    assert "Python" in c.competencias_planas


# ── Saída ─────────────────────────────────────────────────────────


async def test_texto_tem_as_secoes_na_ordem_que_o_ats_espera():
    texto = cur.como_texto(await gerar(BOA), FATOS)

    posicoes = [
        texto.index(s)
        for s in ("RESUMO", "COMPETÊNCIAS", "EXPERIÊNCIA PROFISSIONAL", "PROJETOS", "FORMAÇÃO")
    ]
    assert posicoes == sorted(posicoes)
    assert "pablo@exemplo.dev" in texto


async def test_certificacoes_relevantes_primeiro():
    c = await gerar(BOA)
    # Vaga de banco de dados: a certificação de SQL vem antes da de ML.
    assert c.certificacoes[0]["nome"].startswith("SQL")


# ── competências: sem repetir, sem nome de projeto ────────────────


def test_competencia_nao_repete_entre_categorias():
    """O mesmo termo em dois grupos parece revisão malfeita, não reforço."""
    bruto = [
        {"categoria": "Banco de Dados", "itens": ["PostgreSQL", "Python"]},
        {"categoria": "Backend", "itens": ["Python", "FastAPI"]},
    ]
    grupos = cur._competencias_limpas(bruto, FATOS, REQ)
    todos = [i for g in grupos for i in g["itens"]]
    assert todos.count("Python") == 1


def test_competencia_nao_repete_o_termo_dentro_de_outro():
    """'Machine Learning (scikit-learn)' e 'scikit-learn' são o mesmo termo."""
    bruto = [{"categoria": "IA", "itens": ["Python", "Python (async)"]}]
    grupos = cur._competencias_limpas(bruto, FATOS, REQ)
    itens = grupos[0]["itens"]
    assert len(itens) == 1
    # Fica o mais informativo dos dois.
    assert itens[0] == "Python (async)"


def test_nome_de_projeto_nao_vira_competencia():
    """'Churn Prediction' na linha de habilidades manda o recrutador procurar
    uma tecnologia que não existe. O projeto tem seção própria."""
    bruto = [{"categoria": "Ciência de Dados", "itens": ["Churn Prediction", "Python"]}]
    grupos = cur._competencias_limpas(bruto, FATOS, REQ)
    todos = [i for g in grupos for i in g["itens"]]
    assert "Churn Prediction" not in todos
    assert "Python" in todos


def test_grupo_que_esvaziou_nao_vira_categoria_vazia():
    bruto = [
        {"categoria": "Fantasmas", "itens": ["Churn Prediction"]},
        {"categoria": "Backend", "itens": ["Python"]},
    ]
    grupos = cur._competencias_limpas(bruto, FATOS, REQ)
    assert [g["categoria"] for g in grupos] == ["Linguagens"]


def test_sql_nao_e_confundido_com_sqlalchemy():
    """O bug que a primeira versão do filtro criou: 'SQL' é prefixo de
    'SQLAlchemy', e sumia do currículo — sendo requisito obrigatório da vaga."""
    assert not cur._mesmo_termo("sql", "sqlalchemy 2.0 async")
    assert cur._mesmo_termo("scikit-learn", "machine learning scikit-learn")
    assert cur._mesmo_termo("python", "python async")

    bruto = [{"categoria": "Banco de Dados", "itens": ["SQL", "PostgreSQL"]}]
    itens = cur._competencias_limpas(bruto, FATOS, REQ)[0]["itens"]
    assert "PostgreSQL" in itens


# ── o caminho de volta: o que eu editei vira o documento ──────────


def _curriculo_base() -> cur.Curriculo:
    return cur.Curriculo(
        titulo="Dev Python",
        resumo="Resumo do modelo.",
        competencias=[{"categoria": "Backend", "itens": ["Python", "FastAPI"]}],
        experiencias=[
            {"empresa": "Sechat", "cargo": "Analista", "periodo": "2025",
             "bullets": ["Bullet do modelo."]}
        ],
        projetos=[
            {"nome": "Copiloto", "stack": ["Python", "pgvector"],
             "link": "https://github.com/x", "bullets": ["Bullet do modelo."]}
        ],
        formacao=[{"instituicao": "Impacta", "curso": "ADS", "periodo": "2026"}],
    )


def test_texto_aprovado_volta_para_o_curriculo():
    """Eu editava na fila, aprovava, e o PDF continuava com o texto do modelo."""
    base = _curriculo_base()
    texto = cur.como_texto(base, FATOS).replace(
        "Bullet do modelo.", "Reduzi de 3h para 20min o fechamento mensal."
    ).replace("Resumo do modelo.", "Meu resumo, escrito por mim.")

    novo = cur.de_texto(texto, base)
    assert novo.resumo == "Meu resumo, escrito por mim."
    assert novo.experiencias[0]["bullets"] == ["Reduzi de 3h para 20min o fechamento mensal."]
    assert novo.projetos[0]["bullets"] == ["Reduzi de 3h para 20min o fechamento mensal."]


def test_o_que_o_texto_nao_carrega_vem_da_base():
    """`stack`, `link`, `cargo` e `periodo` não são reconstruíveis do texto."""
    base = _curriculo_base()
    novo = cur.de_texto(cur.como_texto(base, FATOS), base)

    assert novo.projetos[0]["stack"] == ["Python", "pgvector"]
    assert novo.projetos[0]["link"] == "https://github.com/x"
    assert novo.experiencias[0]["cargo"] == "Analista"
    assert novo.experiencias[0]["periodo"] == "2025"
    assert novo.formacao == base.formacao


def test_competencias_editadas_no_texto_valem():
    base = _curriculo_base()
    texto = cur.como_texto(base, FATOS).replace(
        "Backend: Python, FastAPI", "Backend: Python, FastAPI, SQLAlchemy"
    )
    novo = cur.de_texto(texto, base)
    assert novo.competencias == [
        {"categoria": "Backend", "itens": ["Python", "FastAPI", "SQLAlchemy"]}
    ]


def test_texto_irreconhecivel_nao_apaga_nada():
    """Perder a formatação é reversível; jogar fora o meu texto, não."""
    base = _curriculo_base()
    novo = cur.de_texto("escrevi tudo de outro jeito, sem seção nenhuma", base)
    assert novo.como_json() == base.como_json()


def test_ida_e_volta_nao_muda_nada():
    """`de_texto(como_texto(c)) == c` é o que garante que aprovar sem editar
    não mexe no documento."""
    base = _curriculo_base()
    assert cur.de_texto(cur.como_texto(base, FATOS), base).como_json() == base.como_json()


def test_projeto_apagado_do_texto_sai_do_curriculo():
    """O gerador escolhe três projetos; às vezes o terceiro não ajuda naquela
    candidatura, e apagá-lo do texto é uma decisão legítima minha."""
    base = _curriculo_base()
    base.projetos.append({"nome": "Churn", "stack": ["pandas"], "bullets": ["Bullet."]})
    texto = cur.como_texto(base, FATOS)
    # Tira o bloco do Churn, como eu faria à mão.
    texto = "\n".join(
        linha for linha in texto.splitlines()
        if "Churn" not in linha and "Bullet." not in linha
    )

    novo = cur.de_texto(texto, base)
    assert [p["nome"] for p in novo.projetos] == ["Copiloto"]


def test_secao_de_projetos_ilegivel_mantem_tudo():
    """Se a seção inteira ficou irreconhecível, o certo é manter, não zerar."""
    base = _curriculo_base()
    texto = cur.como_texto(base, FATOS).replace("Copiloto |", "escrevi outra coisa aqui")
    novo = cur.de_texto(texto, base)
    assert len(novo.projetos) == len(base.projetos)


def test_contato_no_texto_sai_sem_https_como_no_pdf():
    """O texto da fila é o que eu reviso: tem que ser o mesmo documento que
    sai impresso."""
    from app.candidatura.perfil import montar_fatos
    from app.db.models.pessoal.perfil_mestre import PerfilMestre

    fatos = montar_fatos(
        PerfilMestre(
            nome="Pablo",
            contato={"github": "https://github.com/pablomigueldias/"},
            habilidades=[], projetos=[], experiencias=[], formacao=[], certificacoes=[],
        )
    )
    texto = cur.como_texto(cur.Curriculo(titulo="Dev"), fatos)
    assert "github: github.com/pablomigueldias" in texto
    assert "https://" not in texto


def test_ai_em_ingles_nao_derruba_o_resumo():
    """"IA" estava na lista branca e "AI" não: o resumo inteiro — o parágrafo
    mais importante da página — era descartado por uma tradução."""
    assert FATOS.conheco("IA") == FATOS.conheco("AI")
    assert FATOS.conheco("inteligência artificial") == FATOS.conheco("IA")


# ── o que o parser de 2026 cobra do conteúdo ──────────────────────


async def test_titulo_e_o_do_anuncio_nao_o_que_o_modelo_acha():
    """"Desenvolvedor de IA" e "Engenheiro de IA" são a mesma vaga para mim e
    strings diferentes para o filtro. Quem decide qual ranqueia é quem escreveu
    o anúncio — então o modelo não escreve mais o título."""
    c = await gerar({**BOA, "titulo": "Arquiteto de Soluções Sênior"})
    assert c.titulo == "Dev Python Pleno"


async def test_periodo_sai_no_formato_unico():
    """O ATS calcula tempo de casa; "abr/2025" numa entrada e "08/2024" na
    outra faz ele errar a conta."""
    perfil = PerfilMestre(
        nome="Pablo",
        contato={"email": "p@x.dev"},
        habilidades=[{"nome": "Python"}],
        projetos=[{"nome": "Copiloto", "descricao": "x", "stack": ["Python"]}],
        experiencias=[{"empresa": "Sechat", "cargo": "Analista",
                       "periodo": "abr/2025 – set/2025", "descricao": "Zoho"}],
        formacao=[{"instituicao": "Impacta", "curso": "ADS",
                   "periodo": "ago/2024 – dez/2026"}],
        certificacoes=[],
    )
    fatos = montar_fatos(perfil)
    usar(resposta=BOA)
    c = await cur.gerar(
        fatos=fatos, requisitos=REQ, match=MATCH, titulo_vaga="Dev Python",
        descricao_vaga="x", usar_few_shot=False,
    )
    assert c.experiencias[0]["periodo"] == "04/2025 – 09/2025"
    assert c.formacao[0]["periodo"] == "08/2024 – 12/2026"
    assert not any("sem mês" in a for a in c.avisos)


async def test_sigla_ganha_o_extenso_uma_vez_no_documento():
    """Um ATS não semântico procura a string "Retrieval-Augmented Generation" e
    não acha "RAG"; um semântico casa os dois. Escrever as duas formas atende
    os dois — mas só na primeira ocorrência, senão vira repetição punida."""
    c = await gerar({
        **BOA,
        "resumo": "Construí sistemas de RAG em produção.",
        "projetos": [{"nome": "Copiloto", "bullets": [
            "Indexei 1.773 chunks e servi RAG sobre PostgreSQL",
        ]}],
    })
    assert "RAG (Retrieval-Augmented Generation)" in c.resumo
    assert c.projetos[0]["bullets"][0].count("Retrieval-Augmented") == 0


async def test_avisa_experiencia_sem_numero():
    """É a seção que mais pesa e a que costuma ficar sem métrica — o contrário
    do que se espera."""
    c = await gerar(BOA)
    assert any("nenhum bullet com número" in a for a in c.avisos)


async def test_avisa_contato_sem_telefone_e_sem_cidade():
    """Campo faltando é score perdido, e localização é filtro ativo: parte dos
    ATS elimina por cidade antes de ler o conteúdo."""
    c = await gerar(BOA)
    faltando = [a for a in c.avisos if a.startswith("contato sem")]
    assert faltando and "telefone" in faltando[0] and "localizacao" in faltando[0]


async def test_competencias_saem_nas_categorias_canonicas():
    """O rótulo do modelo misturava categorias ("Agentes e Aplicações" com
    Next.js, Docker e Playwright dentro), e a triagem por skills lê o rótulo
    como declaração sobre o item."""
    c = await gerar({**BOA, "competencias": [
        {"categoria": "Agentes e Aplicações", "itens": ["Python", "FastAPI", "PostgreSQL"]}
    ]})
    assert [g["categoria"] for g in c.competencias] == [
        "Linguagens", "Frameworks e Arquitetura", "Bancos de Dados"
    ]


async def test_texto_nao_tem_ponto_medio():
    """O `·` cola dois termos quando o extrator descarta o glifo sem pôr espaço
    no lugar — e uma habilidade perdida na seção mais lida do currículo é cara."""
    texto = cur.como_texto(await gerar(BOA), FATOS)
    assert "·" not in texto


def test_de_texto_ainda_le_o_separador_antigo():
    """Currículo gravado antes da troca de separador tem que voltar a ser lido:
    perder a formatação é reversível, jogar fora o meu texto não."""
    base = _curriculo_base()
    antigo = (
        "COMPETÊNCIAS\n"
        "Backend: Python · FastAPI · SQLAlchemy\n"
        "\n"
        "EXPERIÊNCIA PROFISSIONAL\n"
        "Analista · Sechat (2025)\n"
        "  - Reduzi de 3h para 20min o fechamento mensal.\n"
    )
    novo = cur.de_texto(antigo, base)
    assert novo.competencias == [
        {"categoria": "Backend", "itens": ["Python", "FastAPI", "SQLAlchemy"]}
    ]
    assert novo.experiencias[0]["bullets"] == ["Reduzi de 3h para 20min o fechamento mensal."]


async def test_ml_abreviado_nao_derruba_bullet():
    """Mesmo caso do "AI" em inglês: o currículo agora escreve a sigla de
    propósito, e sem o sinônimo a anti-alucinação derruba texto honesto."""
    c = await gerar({**BOA, "projetos": [
        {"nome": "Churn Prediction",
         "bullets": ["Construí o pipeline de ML da limpeza ao modelo servido por API"]}
    ]})
    assert c.rejeitados == []
    assert c.projetos[0]["bullets"][0].startswith("Construí o pipeline de ML")


def test_rotulo_do_contato_e_o_mesmo_no_texto_e_no_pdf():
    """O texto da fila é o que eu reviso: tem que ser o mesmo documento que sai
    impresso. Com o mapa só no PDF, a fila mostrava "localizacao:"."""
    from app.candidatura import ats

    fatos = montar_fatos(
        PerfilMestre(
            nome="Pablo",
            contato={"localizacao": "Santo André, SP", "telefone": "(11) 94390-8225"},
            habilidades=[], projetos=[], experiencias=[], formacao=[], certificacoes=[],
        )
    )
    texto = cur.como_texto(cur.Curriculo(titulo="Dev"), fatos)
    assert "local: Santo André, SP" in texto
    assert "tel: (11) 94390-8225" in texto
    assert ats.ROTULOS_CONTATO["localizacao"] == "local"


async def test_fallback_da_experiencia_vira_um_bullet_por_frase():
    """A descrição inteira num bullet só é um parágrafo com marcador na frente:
    o recrutador pula e o parser conta como uma realização única."""
    perfil = PerfilMestre(
        nome="Pablo", contato={"email": "p@x.dev"},
        habilidades=[{"nome": "Python"}],
        projetos=[{"nome": "Copiloto", "descricao": "x", "stack": ["Python"]}],
        experiencias=[{
            "empresa": "Sechat", "cargo": "Analista", "periodo": "04/2025 – 09/2025",
            "descricao": "Administrei o Zoho One. Mantive 4 sites em WordPress. "
                         "Atendeu as equipes internas.",
        }],
        formacao=[], certificacoes=[],
    )
    usar(resposta={**BOA, "experiencias": []})
    c = await cur.gerar(
        fatos=montar_fatos(perfil), requisitos=REQ, match=MATCH,
        titulo_vaga="Dev Python", descricao_vaga="x", usar_few_shot=False,
    )
    bullets = c.experiencias[0]["bullets"]
    assert len(bullets) == 3
    assert bullets[1] == "Mantive 4 sites em WordPress."
    # E a voz é corrigida no caminho, como em qualquer outro bullet.
    assert bullets[2] == "Atendi as equipes internas."


async def test_sigla_nao_e_expandida_dentro_de_competencia():
    """Ali o item não é prosa, é um termo: "Ollama / LLM (Large Language Model)
    local" parte o termo e destrói o casamento exato."""
    c = await gerar({**BOA, "resumo": "Sem sigla nenhuma aqui.",
                     "competencias": [{"categoria": "IA", "itens": ["Python"]}]})
    assert all("(" not in i for g in c.competencias for i in g["itens"])


async def test_projeto_sem_bullet_aprovado_preserva_a_prova():
    """A prova é a única linha com número do projeto — se ela cai no corte, o
    projeto vira texto genérico."""
    c = await gerar({**BOA, "projetos": [
        {"nome": "Copiloto", "bullets": ["Migrei tudo para Kubernetes"]}
    ]})
    assert any("1.773" in b for b in c.projetos[0]["bullets"])


async def test_descricao_do_certificado_conta_no_ranqueamento():
    """O nome do curso raramente usa a palavra da vaga: "Fundamentos de SOC" não
    casa com "monitoramento", mas a descrição dele sim."""
    perfil = PerfilMestre(
        nome="Pablo", contato={"email": "p@x.dev"},
        habilidades=[{"nome": "Python"}],
        projetos=[{"nome": "Copiloto", "descricao": "x", "stack": ["Python"]}],
        experiencias=[], formacao=[],
        certificacoes=[
            {"nome": "Curso A", "tema": "outro", "descricao": "nada a ver"},
            {"nome": "Fundamentos de SOC", "tema": "segurança",
             "descricao": "monitoramento e resposta a incidentes de segurança"},
        ],
    )
    req = Requisitos(obrigatorios=["monitoramento"], stack=[])
    escolhidas = cur._selecionar_certificacoes(montar_fatos(perfil), req)
    assert escolhidas[0]["nome"] == "Fundamentos de SOC"


def test_tecnologia_citada_so_na_descricao_do_certificado_e_verdade():
    """Sem isto, "Construí um chatbot com IBM Watson" seria acusado de invenção
    — sendo que o certificado está no vault."""
    fatos = montar_fatos(PerfilMestre(
        nome="Pablo", habilidades=[], projetos=[], experiencias=[], formacao=[],
        certificacoes=[{"nome": "Fundamentos de IA e Chatbot",
                        "descricao": "chatbot na plataforma IBM Watson"}],
    ))
    assert fatos.conheco("IBM Watson")
