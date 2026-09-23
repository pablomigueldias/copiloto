"""A régua dos quatro públicos.

Sem banco e sem LLM: é análise de texto puro. O que se testa é que cada sinal
fica **vermelho quando deve** — checklist que só sabe ficar verde não mede nada,
e é o jeito mais fácil de um CMS mentir sobre a qualidade do próprio conteúdo.
"""
from __future__ import annotations

from app.blog import camadas

# Um post que passa em tudo. Serve de contraprova: quando um teste de sinal
# vermelho falhar, dá para saber se a culpa é do sinal ou do texto de exemplo.
POST_BOM = """\
Perguntei ao meu assistente "quais são as figuras de linguagem?". Ele trouxe três
trechos sobre lógica difusa. Nenhum falava do assunto.

## O problema

A busca vetorial nunca volta vazia: sempre existe um vizinho mais próximo. O corte
por distância derrubou a taxa de invenção e a recusa passou a sair em 0,2 s, contra
12 s de antes.

```python
if distancia > CORTE:
    return "não tenho isso indexado"
```

## O que eu faria diferente

Mediria o corte antes de escolher o modelo. O código está no
[repositório do Copiloto](https://github.com/pablomigueldias/copiloto).

Se você tem um RAG que nunca diz "não sei", [me chama](/contato).
"""

CAMPOS_BONS = {
    "descricao": "Busca vetorial nunca volta vazia. Como um corte de distância fez meu RAG recusar em 0,2 s.",
    "tags": ["rag", "pgvector"],
    "origem": [{"copiloto": "docs/fase03.md"}],
}


def _camada(corpo: str, id_: str, **campos):
    dados = {**CAMPOS_BONS, **campos}
    achadas = camadas.analisar(corpo=corpo, **dados)
    return next(c for c in achadas if c.id == id_)


def test_post_bom_passa_nas_cinco():
    achadas = camadas.analisar(corpo=POST_BOM, **CAMPOS_BONS)
    vermelhas = [c.rotulo for c in achadas if not c.ok]
    assert vermelhas == [], f"deviam estar verdes: {vermelhas}"
    assert camadas.tudo_verde(achadas)
    assert camadas.o_que_falta(achadas) == []


def test_as_cinco_camadas_cobrem_os_quatro_publicos():
    achadas = camadas.analisar(corpo=POST_BOM, **CAMPOS_BONS)
    assert [c.id for c in achadas] == [
        "abertura",
        "resultado",
        "como",
        "prova",
        "fechamento",
    ]
    assert {c.publico for c in achadas} == set(camadas.PUBLICOS)


# ── abertura (entusiasta) ─────────────────────────────────────────────


def test_abertura_reprova_meta_frase():
    corpo = "Neste post vou falar sobre RAG.\n\n" + POST_BOM
    c = _camada(corpo, "abertura")
    assert not c.ok
    assert any("neste post" in s.texto for s in c.sinais if not s.ok)


def test_abertura_reprova_paragrafo_longo():
    longo = " ".join(["palavra"] * 80)
    c = _camada(f"{longo}\n\n## Depois\n\ntexto", "abertura")
    assert not c.ok
    assert any("80 palavras" in s.texto for s in c.sinais if not s.ok)


def test_abertura_nao_confunde_subtitulo_com_paragrafo():
    """Post que começa com `##` não tem abertura — e o sinal precisa dizer isso."""
    c = _camada("## Direto ao ponto\n\ntexto qualquer", "abertura")
    assert not c.ok
    assert not c.sinais[0].ok


# ── resultado (cliente) ───────────────────────────────────────────────


def test_resultado_exige_numero_com_unidade():
    corpo = "Ficou bem mais rápido e muito mais barato.\n\n## Como\n\ntexto"
    c = _camada(corpo, "resultado")
    assert not c.ok
    assert any("0 número" in s.texto for s in c.sinais if not s.ok)


def test_numero_solto_nao_conta_como_resultado():
    """"3 motivos" é enumeração, não medida — e é o falso positivo óbvio."""
    assert camadas._numeros("São 3 motivos e 4 consequências.") == 0
    assert camadas._numeros("Caiu de 3 min para 75 s.") >= 2


def test_numero_dentro_de_codigo_nao_conta():
    """Um bloco de código cheio de número não é evidência de resultado nenhum."""
    so_codigo = "```python\nx = 42\ny = 99.9\nz = 12 / 12\n```"
    assert camadas._numeros(so_codigo) == 0


def test_descricao_fora_do_tamanho_reprova():
    c = _camada(POST_BOM, "resultado", descricao="curta demais")
    assert not c.ok


# ── como (técnico) ────────────────────────────────────────────────────


def test_como_exige_codigo_ou_formula():
    corpo = "Abertura curta.\n\n## Um\n\ntexto\n\n## Dois\n\nde 3 min para 75 s"
    c = _camada(corpo, "como")
    assert not c.ok
    assert any("sem código" in s.texto for s in c.sinais if not s.ok)


def test_formula_conta_como_codigo():
    corpo = "Abertura.\n\n## Um\n\n$$\n\\text{RRF}(d)\n$$\n\n## Dois\n\ntexto"
    c = _camada(corpo, "como")
    assert c.ok


# ── prova (recrutador) ────────────────────────────────────────────────


def test_prova_exige_link_origem_e_tags():
    sem_nada = _camada(POST_BOM, "prova", tags=[], origem=[])
    assert not sem_nada.ok
    # O link para o GitHub está no corpo, então "origem ou repo" continua verde;
    # o que reprova é a tag.
    vermelhos = [s.texto for s in sem_nada.sinais if not s.ok]
    assert any("tag" in v for v in vermelhos)


def test_origem_vale_sem_link_de_repo():
    """Sem link de repo, o `origem` preenchido sustenta a camada sozinho."""
    corpo = POST_BOM.replace(
        "[repositório do Copiloto](https://github.com/pablomigueldias/copiloto)",
        "[artigo original do RRF](https://exemplo.org/rrf)",
    )
    c = _camada(corpo, "prova")
    assert c.ok, [s.texto for s in c.sinais if not s.ok]


def test_sem_origem_e_sem_repo_reprova():
    corpo = POST_BOM.replace(
        "[repositório do Copiloto](https://github.com/pablomigueldias/copiloto)",
        "[artigo original do RRF](https://exemplo.org/rrf)",
    )
    c = _camada(corpo, "prova", origem=[])
    assert not c.ok
    assert any("origem" in s.texto for s in c.sinais if not s.ok)


# ── fechamento (todos) ────────────────────────────────────────────────


def test_fechamento_reprova_post_que_acaba_sem_chamada():
    corpo = POST_BOM.rsplit("\n\n", 1)[0] + "\n\nE era isso.\n"
    c = _camada(corpo, "fechamento")
    assert not c.ok


def test_fechamento_reprova_dois_pedidos():
    """A regra da voz.md: um único pedido no final, nunca dois."""
    corpo = POST_BOM.rsplit("\n\n", 1)[0] + "\n\n[Me chama](/contato) ou [assina](/rss).\n"
    c = _camada(corpo, "fechamento")
    assert not c.ok
    assert any("2 chamada" in s.texto for s in c.sinais if not s.ok)


# ── tamanho ───────────────────────────────────────────────────────────


def test_minutos_de_leitura_tem_piso_de_um():
    assert camadas.minutos_de_leitura("duas palavras") == 1
    assert camadas.minutos_de_leitura(" ".join(["x"] * 600)) == 3


def test_palavras_ignora_codigo():
    assert camadas.palavras("uma duas\n\n```\nlixo lixo lixo lixo\n```") == 2
