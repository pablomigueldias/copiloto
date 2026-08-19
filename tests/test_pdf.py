"""O PDF que o ATS lê.

O teste central extrai o texto de volta com o pymupdf: se o parser do teste não
acha a palavra, o parser do Workday também não acha.
"""
from __future__ import annotations

import pymupdf

from app.candidatura.curriculo import Curriculo
from app.candidatura.pdf import gerar_pdf, nome_do_arquivo
from app.candidatura.perfil import montar_fatos
from app.db.models.pessoal.perfil_mestre import PerfilMestre

PERFIL = PerfilMestre(
    nome="Pablo Miguel Dias Ortiz",
    contato={"email": "pablo@exemplo.dev", "github": "github.com/pablomigueldias"},
    habilidades=[{"nome": "Python"}],
    formacao=[{"instituicao": "Impacta", "curso": "ADS", "periodo": "2026"}],
)
FATOS = montar_fatos(PERFIL)

CURRICULO = Curriculo(
    titulo="Analista de Automação & IA",
    resumo="Construí APIs em FastAPI com PostgreSQL.",
    competencias=[{"categoria": "Linguagens", "itens": ["Python", "TypeScript"]}],
    experiencias=[{"empresa": "Sechat", "cargo": "Analista", "periodo": "jan/2025 – dez/2025",
                   "bullets": ["Administrei o Zoho One"]}],
    projetos=[{"nome": "Copiloto", "stack": ["Python", "pgvector"],
               "bullets": ["Indexei 1.773 chunks"], "link": "github.com/x/copiloto"}],
    formacao=[{"instituicao": "Impacta", "curso": "ADS", "periodo": "2026"}],
    certificacoes=[{"nome": "T-SQL", "instituicao": "Bradesco", "ano": 2025}],
)


def texto_do_pdf(caminho) -> str:
    with pymupdf.open(caminho) as d:
        return "\n".join(p.get_text("text") for p in d)


def test_pdf_tem_texto_de_verdade(tmp_path):
    destino = gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "cv.pdf")
    texto = texto_do_pdf(destino)

    # PDF de imagem é rejeição garantida: o parser vê zero caractere.
    assert len(texto) > 200
    assert "Pablo Miguel Dias Ortiz" in texto
    assert "pablo@exemplo.dev" in texto
    assert "Indexei 1.773 chunks" in texto


def test_secoes_na_ordem_que_o_parser_espera(tmp_path):
    texto = texto_do_pdf(gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "cv.pdf"))
    posicoes = [
        texto.index(s)
        for s in ("RESUMO", "COMPETÊNCIAS", "EXPERIÊNCIA PROFISSIONAL", "PROJETOS",
                  "FORMAÇÃO ACADÊMICA", "CERTIFICAÇÕES")
    ]
    assert posicoes == sorted(posicoes)


def test_contato_tem_rotulo_escrito_e_nao_icone(tmp_path):
    texto = texto_do_pdf(gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "cv.pdf"))
    # Ícone vira caractere estranho ou nada no parser.
    assert "email: pablo@exemplo.dev" in texto
    assert "github: github.com/pablomigueldias" in texto


def test_data_da_experiencia_chega_no_texto(tmp_path):
    texto = texto_do_pdf(gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "cv.pdf"))
    # Entrada sem data é recusa automática em parte dos ATS de 2026.
    assert "jan/2025" in texto and "dez/2025" in texto


def test_e_commercial_nao_quebra_o_documento(tmp_path):
    # `reportlab` lê a string como mini-HTML: "&" cru levanta exceção.
    texto = texto_do_pdf(gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "cv.pdf"))
    assert "Automação & IA" in texto


def test_uma_pagina_por_padrao(tmp_path):
    with pymupdf.open(gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "cv.pdf")) as d:
        assert d.page_count == 1


def test_nome_do_arquivo_e_previsivel():
    assert nome_do_arquivo("Pablo Miguel Dias Ortiz", "Dev Python Pleno", "Acme Ltda") == (
        "curriculo-pablo-miguel-dias-ortiz-dev-python-pleno-acme-ltda.pdf"
    )
    assert "automacao" in nome_do_arquivo("Pablo", "Automação & IA")


def test_pdf_sem_empresa_tambem_tem_nome(tmp_path):
    destino = gerar_pdf(CURRICULO, FATOS, caminho=tmp_path / "sem-empresa.pdf")
    assert destino.exists()


def test_data_nao_quebra_em_duas_linhas():
    """"(08/2024 –" numa linha e "12/2026)" na outra faz o parser ler duas
    coisas e perder a data — o campo cuja ausência derruba a entrada."""
    from app.candidatura.pdf import _data_inteira

    assert " " not in _data_inteira("08/2024 – 12/2026")
    assert _data_inteira("08/2024 – 12/2026").replace("\xa0", " ") == "08/2024 – 12/2026"
