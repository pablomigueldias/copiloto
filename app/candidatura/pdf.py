"""Currículo em PDF — feito para o ATS ler, não para impressionar.

O filtro que decide se um humano vai te ver é um parser de texto. O que ele
quebra, na ordem em que mais quebra:

| O que quebra | O que fazemos |
|---|---|
| Duas colunas | uma coluna, sempre |
| Tabela para alinhar | nada de tabela |
| Nome/contato em cabeçalho ou imagem | texto no corpo, primeira linha |
| Ícone no lugar de rótulo | "email:" escrito |
| Fonte exótica embutida | Helvetica, a padrão do PDF |
| Texto dentro de caixa/gráfico | parágrafo simples |

Por isso `reportlab` com `SimpleDocTemplate` e nada além de parágrafo. O bonito
é inimigo do aprovado — e a versão bonita pode existir depois, para mandar por
e-mail a um humano.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.candidatura.curriculo import Curriculo
from app.candidatura.perfil import Fatos
from app.config import DATA_DIR
from app.utils.logger import get_logger

logger = get_logger()

PASTA = DATA_DIR / "curriculos"

_NOME = ParagraphStyle("nome", fontName="Helvetica-Bold", fontSize=16, leading=19, spaceAfter=2)
_CARGO = ParagraphStyle("cargo", fontName="Helvetica", fontSize=11, leading=14, spaceAfter=2)
_CONTATO = ParagraphStyle("contato", fontName="Helvetica", fontSize=9, leading=12, spaceAfter=10)
_SECAO = ParagraphStyle(
    "secao", fontName="Helvetica-Bold", fontSize=10.5, leading=13, spaceBefore=10, spaceAfter=4
)
_CORPO = ParagraphStyle(
    "corpo", fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_JUSTIFY, spaceAfter=3
)
_ITEM = ParagraphStyle("item", parent=_CORPO, leftIndent=10, bulletIndent=2, spaceAfter=2)
_SUBTITULO = ParagraphStyle(
    "sub", fontName="Helvetica-Bold", fontSize=9.5, leading=12, spaceBefore=5, spaceAfter=1
)


def _escapar(texto: str) -> str:
    """`reportlab` interpreta a string como mini-HTML; `&` e `<` quebram tudo."""
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def nome_do_arquivo(nome_pessoa: str, titulo_vaga: str, empresa: str | None = None) -> str:
    """`curriculo-pablo-ortiz-dev-python-pleno-acme.pdf`.

    Previsível de propósito: o recrutador salva 200 arquivos por semana, e
    "curriculo (3).pdf" é o que acontece com quem não pensou nisso.
    """
    def limpar(t: str) -> str:
        t = unicodedata.normalize("NFKD", str(t or "").lower())
        t = "".join(c for c in t if not unicodedata.combining(c))
        return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t)).strip("-")

    partes = ["curriculo", limpar(nome_pessoa), limpar(titulo_vaga)]
    if empresa:
        partes.append(limpar(empresa))
    return "-".join(p for p in partes if p)[:120] + ".pdf"


def gerar_pdf(
    curriculo: Curriculo,
    fatos: Fatos,
    *,
    empresa: str | None = None,
    caminho: Path | None = None,
) -> Path:
    """Monta o PDF e devolve onde ele foi parar."""
    perfil = fatos.perfil
    destino = caminho or (
        PASTA / f"{datetime.now(UTC):%Y-%m-%d}" /
        nome_do_arquivo(perfil.nome, curriculo.titulo, empresa)
    )
    destino.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
        title=f"{perfil.nome} — {curriculo.titulo}",
        author=perfil.nome,
    )

    fluxo = [
        Paragraph(_escapar(perfil.nome), _NOME),
        Paragraph(_escapar(curriculo.titulo), _CARGO),
    ]

    contato = perfil.contato or {}
    if contato:
        # Rótulo escrito, não ícone: ícone vira caractere estranho no parser.
        rotulos = {"email": "email", "telefone": "tel", "linkedin": "linkedin",
                   "github": "github", "portfolio": "site"}
        partes = [
            f"{rotulos.get(k, k)}: {v}" for k, v in contato.items() if v
        ]
        fluxo.append(Paragraph(_escapar(" · ".join(partes)), _CONTATO))

    if curriculo.resumo:
        fluxo += [Paragraph("RESUMO", _SECAO), Paragraph(_escapar(curriculo.resumo), _CORPO)]

    # Competências agrupadas por categoria: o parser lê a linha inteira, e
    # "Backend: FastAPI · SQLAlchemy" diz mais ao humano que uma lista de 30.
    if curriculo.competencias:
        fluxo.append(Paragraph("COMPETÊNCIAS", _SECAO))
        for grupo in curriculo.competencias:
            itens = _escapar(" · ".join(grupo.get("itens") or []))
            categoria = _escapar(grupo.get("categoria") or "")
            fluxo.append(Paragraph(f"<b>{categoria}:</b> {itens}", _CORPO))

    # Experiência antes de projetos: é a ordem que o parser espera, e entrada
    # de trabalho é o que ele procura primeiro para calcular tempo de carreira.
    if curriculo.experiencias:
        fluxo.append(Paragraph("EXPERIÊNCIA PROFISSIONAL", _SECAO))
        for e in curriculo.experiencias:
            titulo = f"{e.get('cargo', '')} · {e.get('empresa', '')}"
            if e.get("periodo"):
                titulo += f" ({e['periodo']})"
            fluxo.append(Paragraph(_escapar(titulo), _SUBTITULO))
            for b in e.get("bullets") or []:
                fluxo.append(Paragraph(_escapar(b), _ITEM, bulletText="•"))

    if curriculo.projetos:
        fluxo.append(Paragraph("PROJETOS", _SECAO))
        for p in curriculo.projetos:
            cabecalho = _escapar(p.get("nome", ""))
            if p.get("stack"):
                cabecalho += f" — {_escapar(', '.join(p['stack']))}"
            if p.get("link"):
                cabecalho += f" — {_escapar(p['link'])}"
            fluxo.append(Paragraph(cabecalho, _SUBTITULO))
            for b in p.get("bullets") or []:
                fluxo.append(Paragraph(_escapar(b), _ITEM, bulletText="•"))

    if curriculo.formacao:
        fluxo.append(Paragraph("FORMAÇÃO ACADÊMICA", _SECAO))
        for f in curriculo.formacao:
            linha = f"{f.get('instituicao', '')} — {f.get('curso', '')}"
            if f.get("periodo"):
                linha += f" ({f['periodo']})"
            fluxo.append(Paragraph(_escapar(linha), _CORPO))

    if curriculo.certificacoes:
        fluxo.append(Paragraph("CERTIFICAÇÕES", _SECAO))
        for c in curriculo.certificacoes:
            linha = c.get("nome", "")
            if c.get("instituicao"):
                linha += f" — {c['instituicao']}"
            if c.get("ano"):
                linha += f" ({c['ano']})"
            fluxo.append(Paragraph(_escapar(linha), _ITEM, bulletText="•"))

    fluxo.append(Spacer(1, 4))
    doc.build(fluxo)

    logger.info(f"PDF: {destino}")
    return destino
