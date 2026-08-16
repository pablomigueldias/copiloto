"""PDF → um documento por página.

**Por página, e não por arquivo**, porque a citação é o produto: dizer "está no
edital" sobre um PDF de 200 páginas é a mesma coisa que não responder. Com
`metadados.pagina` preenchido, a resposta da F3 sai como *"edital, p. 47"* — e
isso é verificável.

O outro trabalho aqui é **desfazer o layout**. Extração de PDF devolve uma
quebra de linha por linha impressa e palavra cortada com hífen no fim da linha;
embedar isso é embedar o formato da página, não o texto. Juntar as linhas de um
parágrafo custa vinte linhas de código e melhora tudo que vem depois.

PDF escaneado (sem camada de texto) é **avisado, não ignorado em silêncio** —
senão o arquivo some do índice e ninguém descobre por que a busca não acha.
OCR fica fora da fase; entra quando aparecer um caso real.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pymupdf

from app.conhecimento.fontes import IGNORAR, Documento
from app.utils.logger import get_logger

logger = get_logger()

# Abaixo disso a página é capa, separador ou número de página solto: vira chunk
# de ruído que nunca é a resposta certa e ainda ocupa lugar no ranking.
MINIMO_PAGINA = 80
# Média de caracteres por página abaixo da qual o arquivo é tratado como
# escaneado. Um PDF de texto de verdade passa de mil.
MEDIA_ESCANEADO = 40

_HIFEN_NA_QUEBRA = re.compile(r"(\w)-\n(\w)")
_QUEBRA_SIMPLES = re.compile(r"(?<![\n\-•])\n(?![\n\s•\-\d])")
_ESPACOS = re.compile(r"[ \t]{2,}")
_LINHAS_VAZIAS = re.compile(r"\n{3,}")


def limpar(texto: str) -> str:
    """Texto de PDF → texto de leitura.

    Junta as linhas de um mesmo parágrafo, mantém a separação entre parágrafos
    e preserva o começo de item de lista (`-`, `•`, `1.`), que é justamente o
    formato de requisito de edital e de vaga.
    """
    texto = texto.replace("\xa0", " ").replace("\r\n", "\n")
    texto = _HIFEN_NA_QUEBRA.sub(r"\1\2", texto)
    texto = _QUEBRA_SIMPLES.sub(" ", texto)
    texto = _ESPACOS.sub(" ", texto)
    return _LINHAS_VAZIAS.sub("\n\n", texto).strip()


def _titulo(doc: pymupdf.Document, arquivo: Path) -> str:
    do_pdf = (doc.metadata or {}).get("title") or ""
    do_pdf = do_pdf.strip()
    # Muito PDF traz título de gerador ("Microsoft Word - final2.doc"), que diz
    # menos que o nome do arquivo escolhido por quem salvou.
    if do_pdf and not do_pdf.lower().startswith(("microsoft word", "untitled", "sem título")):
        return do_pdf
    return arquivo.stem


def _escaneado(arquivo: Path, paginas: list[tuple[int, str]]) -> bool:
    """PDF sem camada de texto: avisa e fica de fora, em vez de sumir calado."""
    if not paginas:
        logger.warning(f"{arquivo.name}: PDF sem páginas")
        return True
    total = sum(len(t) for _, t in paginas)
    if total / len(paginas) >= MEDIA_ESCANEADO:
        return False
    logger.warning(
        f"{arquivo.name}: {len(paginas)} páginas e só {total} caracteres — parece "
        "escaneado (sem camada de texto). Fora do índice até haver OCR."
    )
    return True


def ler_pdf(raiz: Path, *, fonte_tipo: str = "pdf") -> Iterator[Documento]:
    """Todos os `.pdf` de uma pasta (ou o arquivo, se `raiz` for um arquivo)."""
    raiz = raiz.expanduser()
    if not raiz.exists():
        logger.warning(f"Fonte inexistente, pulando: {raiz}")
        return

    arquivos = [raiz] if raiz.is_file() else sorted(raiz.rglob("*.pdf"))
    for arquivo in arquivos:
        if any(parte in IGNORAR for parte in arquivo.parts):
            continue
        try:
            with pymupdf.open(arquivo) as doc:
                titulo = _titulo(doc, arquivo)
                paginas = [(i, limpar(p.get_text("text"))) for i, p in enumerate(doc, start=1)]
        except Exception as e:  # noqa: BLE001 — PDF corrompido não para a varredura
            logger.warning(f"Não consegui ler {arquivo}: {type(e).__name__}: {e}")
            continue

        if _escaneado(arquivo, paginas):
            continue

        for numero, texto in paginas:
            if len(texto) < MINIMO_PAGINA:
                continue
            yield Documento(
                fonte_tipo=fonte_tipo,
                # A página no ref: reindexar um PDF editado troca só as páginas
                # que mudaram, e a citação aponta para uma unidade que existe.
                fonte_ref=f"{arquivo}#p{numero}",
                titulo=f"{titulo} > p. {numero}",
                conteudo=texto,
                metadados={
                    "arquivo": arquivo.name,
                    "caminho": str(arquivo),
                    "pagina": numero,
                    "paginas": len(paginas),
                },
            )
