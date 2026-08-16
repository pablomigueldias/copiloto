"""Leitura de PDF: uma página por documento, texto sem o layout.

Os PDFs de teste são gerados aqui mesmo com o pymupdf — nada de binário
versionado, e o teste diz exatamente que texto entrou.
"""
from __future__ import annotations

import pymupdf
import pytest

from app.conhecimento.fontes_pdf import ler_pdf, limpar

PARAGRAFO = (
    "Este edital estabelece as regras do certame e o conteúdo programático "
    "exigido de cada candidato inscrito no processo seletivo em questão."
)


def escrever_pdf(caminho, paginas: list[str]) -> None:
    doc = pymupdf.open()
    for texto in paginas:
        pagina = doc.new_page()
        pagina.insert_textbox(pymupdf.Rect(50, 50, 550, 750), texto, fontsize=11)
    doc.save(caminho)
    doc.close()


@pytest.fixture
def pasta(tmp_path):
    return tmp_path


# ── Limpeza do texto ──────────────────────────────────────────────


def test_junta_linhas_do_mesmo_paragrafo():
    assert limpar("uma frase que\ncontinua na linha\nde baixo") == (
        "uma frase que continua na linha de baixo"
    )


def test_desfaz_hifen_de_fim_de_linha():
    assert limpar("desen-\nvolvimento de software") == "desenvolvimento de software"


def test_preserva_paragrafos_e_itens_de_lista():
    limpo = limpar("Requisitos:\n\n- Python\n- Postgres\n\nDesejáveis:\n\n- Terraform")
    assert "- Python\n- Postgres" in limpo
    assert "\n\nDesejáveis" in limpo


# ── Leitura ───────────────────────────────────────────────────────


def test_uma_pagina_por_documento_com_o_numero_nos_metadados(pasta):
    escrever_pdf(pasta / "edital.pdf", [f"Página um. {PARAGRAFO}", f"Página dois. {PARAGRAFO}"])

    docs = list(ler_pdf(pasta))
    assert len(docs) == 2
    assert [d.metadados["pagina"] for d in docs] == [1, 2]
    assert docs[0].metadados["paginas"] == 2
    assert "Página um" in docs[0].conteudo


def test_fonte_ref_aponta_para_a_pagina(pasta):
    escrever_pdf(pasta / "edital.pdf", [PARAGRAFO, PARAGRAFO + " Segunda."])
    refs = [d.fonte_ref for d in ler_pdf(pasta)]
    assert refs == [f"{pasta / 'edital.pdf'}#p1", f"{pasta / 'edital.pdf'}#p2"]


def test_titulo_carrega_a_pagina_para_a_citacao(pasta):
    escrever_pdf(pasta / "edital.pdf", [PARAGRAFO])
    (doc,) = ler_pdf(pasta)
    assert doc.titulo == "edital > p. 1"


def test_pagina_quase_vazia_nao_vira_chunk(pasta):
    escrever_pdf(pasta / "doc.pdf", [PARAGRAFO, "12", PARAGRAFO + " Fim."])
    paginas = [d.metadados["pagina"] for d in ler_pdf(pasta)]
    assert paginas == [1, 3]  # a capa/numeração sozinha fica de fora


def test_pdf_escaneado_e_avisado_e_nao_entra(pasta):
    # Sem camada de texto: páginas em branco imitam o resultado da extração.
    escrever_pdf(pasta / "escaneado.pdf", ["", "", ""])
    assert list(ler_pdf(pasta)) == []


def test_pdf_corrompido_nao_para_a_varredura(pasta):
    (pasta / "quebrado.pdf").write_bytes(b"nao sou um pdf")
    escrever_pdf(pasta / "bom.pdf", [PARAGRAFO])

    docs = list(ler_pdf(pasta))
    assert len(docs) == 1 and docs[0].metadados["arquivo"] == "bom.pdf"


def test_pasta_inexistente_nao_explode(tmp_path):
    assert list(ler_pdf(tmp_path / "nao-existe")) == []


def test_aceita_um_arquivo_direto(pasta):
    caminho = pasta / "edital.pdf"
    escrever_pdf(caminho, [PARAGRAFO])
    assert len(list(ler_pdf(caminho))) == 1


def test_ignora_pastas_de_dependencia(pasta):
    (pasta / "node_modules").mkdir()
    escrever_pdf(pasta / "node_modules" / "manual.pdf", [PARAGRAFO])
    assert list(ler_pdf(pasta)) == []
