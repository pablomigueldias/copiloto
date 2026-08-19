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
| Separador fora do ASCII entre termos | vírgula e barra (`ats.SEP_*`) |
| Sem cidade/UF (filtro de localização) | `contato.localizacao`, primeira linha |

Por isso `reportlab` com `SimpleDocTemplate` e nada além de parágrafo. O bonito
é inimigo do aprovado — e a versão bonita pode existir depois, para mandar por
e-mail a um humano.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.candidatura import ats
from app.candidatura.curriculo import Curriculo
from app.candidatura.perfil import Fatos
from app.config import DATA_DIR
from app.utils.logger import get_logger

logger = get_logger()

PASTA = DATA_DIR / "curriculos"

@dataclass(frozen=True, slots=True)
class Estilos:
    """Os estilos do documento numa escala. Ver `_ESCALAS` e `gerar_pdf`."""

    nome: ParagraphStyle
    cargo: ParagraphStyle
    contato: ParagraphStyle
    secao: ParagraphStyle
    corpo: ParagraphStyle
    item: ParagraphStyle
    subtitulo: ParagraphStyle
    stack: ParagraphStyle
    margem_mm: float
    certificacoes_em_linha: bool


def _estilos(*, fonte: float, entrelinha: float, respiro: float, margem: float,
             cert_em_linha: bool) -> Estilos:
    """Monta os estilos a partir de três números: corpo, entrelinha e respiro.

    Tudo escala junto de propósito. Encolher só a fonte e manter o espaço entre
    seções produz uma página com letra miúda e buraco — que fica pior que a
    segunda página que se queria evitar.
    """
    # Alinhado à esquerda, não justificado: justificar abre buracos no meio da
    # linha e não ajuda parser nenhum — é enfeite que atrapalha a leitura.
    corpo = ParagraphStyle(
        "corpo", fontName="Helvetica", fontSize=fonte,
        leading=fonte * entrelinha, spaceAfter=2 * respiro,
    )
    return Estilos(
        nome=ParagraphStyle(
            "nome", fontName="Helvetica-Bold", fontSize=fonte + 6.5,
            leading=(fonte + 6.5) * 1.18, spaceAfter=2,
        ),
        cargo=ParagraphStyle(
            "cargo", fontName="Helvetica", fontSize=fonte + 1.5,
            leading=(fonte + 1.5) * 1.27, spaceAfter=2,
        ),
        contato=ParagraphStyle(
            "contato", fontName="Helvetica", fontSize=fonte - 0.5,
            leading=(fonte - 0.5) * 1.33, spaceAfter=10 * respiro,
        ),
        secao=ParagraphStyle(
            "secao", fontName="Helvetica-Bold", fontSize=fonte + 1,
            leading=(fonte + 1) * 1.24,
            spaceBefore=10 * respiro, spaceAfter=4 * respiro,
        ),
        corpo=corpo,
        item=ParagraphStyle(
            "item", parent=corpo, leftIndent=10, bulletIndent=2, spaceAfter=1.5 * respiro
        ),
        subtitulo=ParagraphStyle(
            "sub", fontName="Helvetica-Bold", fontSize=fonte,
            leading=fonte * 1.26, spaceBefore=5 * respiro, spaceAfter=0,
        ),
        # A stack em linha própria, cinza e pequena: ela é palavra-chave para o
        # ATS, não manchete. Em negrito junto do nome, o cabeçalho do projeto
        # virava um bloco de três linhas gritando.
        stack=ParagraphStyle(
            "stack", fontName="Helvetica", fontSize=fonte - 1,
            leading=(fonte - 1) * 1.24,
            textColor=colors.HexColor("#555555"), spaceAfter=2 * respiro,
        ),
        margem_mm=margem,
        certificacoes_em_linha=cert_em_linha,
    )


# A escada da compactação, do confortável ao apertado. `gerar_pdf` desce um
# degrau por vez até caber em uma página — e para no último, porque abaixo de
# 8,5 pt o currículo fica desagradável de ler e a economia é de duas linhas.
#
# O degrau 0 é o layout que eu escolheria se o conteúdo coubesse sempre.
_ESCALAS = (
    dict(fonte=9.5, entrelinha=1.33, respiro=1.0,  margem=15, cert_em_linha=False),
    dict(fonte=9.5, entrelinha=1.28, respiro=0.85, margem=13, cert_em_linha=True),
    dict(fonte=9.0, entrelinha=1.24, respiro=0.72, margem=12, cert_em_linha=True),
    dict(fonte=8.5, entrelinha=1.20, respiro=0.60, margem=11, cert_em_linha=True),
)

# Stack inteira de um projeto passa de 12 itens; o que ranqueia são os
# primeiros, e o resto vira ruído visual.
MAX_STACK = 8


def _escapar(texto: str) -> str:
    """`reportlab` interpreta a string como mini-HTML; `&` e `<` quebram tudo."""
    return (
        str(texto or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _data_inteira(periodo: str) -> str:
    """O intervalo de datas com espaço fixo, para não quebrar em duas linhas.

    O `reportlab` quebra a linha em qualquer espaço, e a formação saiu com
    "(08/2024 –" numa linha e "12/2026)" na outra. O parser lê as duas metades
    como coisas diferentes e a data se perde — justamente o campo cuja ausência
    derruba a entrada inteira em vários ATS.

    O `\xa0` sai do PDF como espaço comum (conferido com `pdftotext`), então
    não é caractere estranho para ninguém: só impede a quebra.
    """
    return str(periodo or "").replace(" ", "\xa0")


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


def _montar(curriculo: Curriculo, fatos: Fatos, est: Estilos) -> list:
    """O conteúdo do documento, nos estilos de um degrau da escada."""
    perfil = fatos.perfil
    fluxo = [
        Paragraph(_escapar(perfil.nome), est.nome),
        Paragraph(_escapar(curriculo.titulo), est.cargo),
    ]

    contato = perfil.contato or {}
    if contato:
        # Ver `ats.ROTULOS_CONTATO`: o mesmo mapa serve o texto da fila.
        rotulos = ats.ROTULOS_CONTATO
        # Sem "https://": ocupa duas linhas e não acrescenta nada — o
        # recrutador copia, e o parser reconhece o domínio do mesmo jeito.
        partes = [
            f"{rotulos.get(k, k)}: {re.sub(r'^https?://', '', str(v)).rstrip('/')}"
            for k, v in contato.items()
            if v
        ]
        fluxo.append(Paragraph(_escapar(ats.SEP_CAMPO.join(partes)), est.contato))

    if curriculo.resumo:
        fluxo += [Paragraph("RESUMO", est.secao), Paragraph(_escapar(curriculo.resumo), est.corpo)]

    # Competências agrupadas por categoria: o parser lê a linha inteira, e
    # "Backend: FastAPI, SQLAlchemy" diz mais ao humano que uma lista de 30.
    if curriculo.competencias:
        fluxo.append(Paragraph("COMPETÊNCIAS", est.secao))
        for grupo in curriculo.competencias:
            itens = _escapar(ats.SEP_LISTA.join(grupo.get("itens") or []))
            categoria = _escapar(grupo.get("categoria") or "")
            fluxo.append(Paragraph(f"<b>{categoria}:</b> {itens}", est.corpo))

    # Experiência antes de projetos: é a ordem que o parser espera, e entrada
    # de trabalho é o que ele procura primeiro para calcular tempo de carreira.
    if curriculo.experiencias:
        fluxo.append(Paragraph("EXPERIÊNCIA PROFISSIONAL", est.secao))
        for e in curriculo.experiencias:
            titulo = f"{e.get('cargo', '')}{ats.SEP_CAMPO}{e.get('empresa', '')}"
            if e.get("periodo"):
                titulo += f" ({_data_inteira(e['periodo'])})"
            fluxo.append(Paragraph(_escapar(titulo), est.subtitulo))
            for b in e.get("bullets") or []:
                fluxo.append(Paragraph(_escapar(b), est.item, bulletText="•"))

    if curriculo.projetos:
        fluxo.append(Paragraph("PROJETOS", est.secao))
        for p in curriculo.projetos:
            nome = _escapar(p.get("nome", ""))
            if p.get("link"):
                enxuto = re.sub(r"^https?://", "", str(p["link"])).rstrip("/")
                nome += f"{ats.SEP_CAMPO}{_escapar(enxuto)}"
            fluxo.append(Paragraph(nome, est.subtitulo))
            if p.get("stack"):
                fluxo.append(
                    Paragraph(_escapar(ats.SEP_LISTA.join(p["stack"][:MAX_STACK])), est.stack)
                )
            for b in p.get("bullets") or []:
                fluxo.append(Paragraph(_escapar(b), est.item, bulletText="•"))

    if curriculo.formacao:
        fluxo.append(Paragraph("FORMAÇÃO ACADÊMICA", est.secao))
        for f in curriculo.formacao:
            linha = f"{f.get('instituicao', '')}{ats.SEP_CAMPO}{f.get('curso', '')}"
            if f.get("periodo"):
                linha += f" ({_data_inteira(f['periodo'])})"
            fluxo.append(Paragraph(_escapar(linha), est.corpo))

    if curriculo.certificacoes:
        fluxo.append(Paragraph("CERTIFICAÇÕES", est.secao))
        nomes = []
        for c in curriculo.certificacoes:
            linha = c.get("nome", "")
            if c.get("instituicao"):
                linha += f"{ats.SEP_CAMPO}{c['instituicao']}"
            if c.get("ano"):
                linha += f" ({c['ano']})"
            nomes.append(linha)
        if est.certificacoes_em_linha:
            # Uma linha corrida em vez de um item por linha: economiza quatro
            # linhas e continua sendo texto que o parser lê igual.
            fluxo.append(Paragraph(_escapar(ats.SEP_LISTA.join(nomes)), est.corpo))
        else:
            fluxo += [Paragraph(_escapar(n), est.item, bulletText="•") for n in nomes]

    fluxo.append(Spacer(1, 4))
    return fluxo


def gerar_pdf(
    curriculo: Curriculo,
    fatos: Fatos,
    *,
    empresa: str | None = None,
    caminho: Path | None = None,
) -> Path:
    """Monta o PDF e devolve onde ele foi parar.

    Monta no layout confortável; se vazar para a segunda página, **desce um
    degrau da escada de compactação e monta de novo**, até caber ou acabarem os
    degraus. Currículo de duas páginas é legítimo — currículo cuja segunda
    página tem três linhas parece descuido, e é a primeira coisa que um
    recrutador nota antes de ler qualquer conteúdo.

    Por que tentativa e erro em vez de calcular a altura: o `reportlab` só sabe
    quantas páginas deu depois de quebrar as linhas, e quebrar linha depende da
    fonte, da largura e do texto. Cada tentativa custa ~15 ms; medir de outro
    jeito custaria reimplementar o paginador.
    """
    perfil = fatos.perfil
    destino = caminho or (
        PASTA / f"{datetime.now(UTC):%Y-%m-%d}" /
        nome_do_arquivo(perfil.nome, curriculo.titulo, empresa)
    )
    destino.parent.mkdir(parents=True, exist_ok=True)

    paginas = 0
    for degrau, escala in enumerate(_ESCALAS):
        estilos = _estilos(**escala)
        doc = SimpleDocTemplate(
            str(destino),
            pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=estilos.margem_mm * mm, bottomMargin=estilos.margem_mm * mm,
            title=f"{perfil.nome} — {curriculo.titulo}",
            author=perfil.nome,
        )
        doc.build(_montar(curriculo, fatos, estilos))
        paginas = doc.page
        if paginas == 1:
            if degrau:
                logger.info(f"PDF compactado no degrau {degrau} para caber em 1 página")
            break
    else:
        # Conteúdo que não cabe nem no degrau mais apertado é conteúdo demais,
        # não layout ruim — e a correção é cortar bullet, não diminuir a fonte.
        logger.warning(
            f"O currículo ficou com {paginas} páginas mesmo compactado ao máximo. "
            "Considere reduzir projetos ou bullets."
        )

    logger.info(f"PDF: {destino} · {paginas} página(s)")
    return destino
