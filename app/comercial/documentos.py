"""Documentos do processo com cliente (M01–M16): modelo em Markdown → PDF.

O modelo mora em `data/comercial/modelos/`, fora do git (D3 do passo 3.8), e é
Markdown com campos `{{assim}}` e um cabeçalho simples:

    ---
    codigo: M03
    titulo: Proposta comercial
    versao: 1
    ---

O caminho é `preencher` → pandoc (Markdown → HTML) → Chromium (HTML → PDF). O
Chromium, e não o reportlab do currículo, porque o documento tem tabela e
precisa de "página N de M" no rodapé, que o Chromium faz sozinho.

**Notas:** o que vem depois de uma linha `<!-- notas -->` (orientação de
preenchimento, pontos para o advogado) não vai para o cliente. `gerar_pdf(...,
com_notas=True)` inclui essa parte, para a versão de revisão; nela não há
`{{campo}}`, só `[colchetes]`.

**Nenhum campo sobra:** `preencher` falha se um `{{campo}}` do modelo não tem
valor. Um PDF com "{{cliente_razao_social}}" no meio vai para o cliente do
mesmo jeito, e é pior do que não gerar.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.config import DATA_DIR

MODELOS = DATA_DIR / "comercial" / "modelos"

_CAMPO = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")
_CABECALHO = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_NOTAS = re.compile(r"^<!-- notas -->[ \t]*$", re.M)


class CampoFaltando(ValueError):
    """O modelo pede um campo que não veio."""

    def __init__(self, faltando: list[str]) -> None:
        self.faltando = faltando
        super().__init__("campos sem valor: " + ", ".join(faltando))


@dataclass(frozen=True, slots=True)
class Modelo:
    codigo: str
    titulo: str
    versao: str
    corpo: str
    notas: str = ""


def ler_modelo(texto: str) -> Modelo:
    m = _CABECALHO.match(texto)
    if not m:
        raise ValueError("modelo sem cabeçalho (--- codigo/titulo/versao ---)")
    meta = dict(
        (chave.strip(), valor.strip())
        for chave, _, valor in (linha.partition(":") for linha in m.group(1).splitlines() if linha.strip())
    )
    faltando = [c for c in ("codigo", "titulo", "versao") if not meta.get(c)]
    if faltando:
        raise ValueError("cabeçalho sem " + ", ".join(faltando))
    resto = texto[m.end():]
    n = _NOTAS.search(resto)
    corpo, notas = (resto, "") if not n else (resto[: n.start()], resto[n.end():])
    return Modelo(meta["codigo"], meta["titulo"], meta["versao"], corpo, notas)


def campos_do_modelo(texto: str) -> list[str]:
    """Os campos na ordem em que aparecem, sem repetir."""
    return list(dict.fromkeys(_CAMPO.findall(texto)))


def preencher(texto: str, valores: dict[str, str]) -> str:
    faltando = [c for c in campos_do_modelo(texto) if not str(valores.get(c, "")).strip()]
    if faltando:
        raise CampoFaltando(faltando)
    return _CAMPO.sub(lambda m: str(valores[m.group(1)]), texto)


_CSS = """
@page { size: A4; margin: 28mm 20mm 22mm 20mm; }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1b1b1b; }
h1 { font-size: 17pt; margin: 0 0 4mm; }
h2 { font-size: 12.5pt; margin: 7mm 0 2mm; border-bottom: 0.4pt solid #999; padding-bottom: 1mm; }
h3 { font-size: 11pt; margin: 5mm 0 1.5mm; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 9.5pt; }
th, td { border: 0.4pt solid #999; padding: 1.5mm 2mm; text-align: left; vertical-align: top; }
th { background: #eee; }
blockquote { margin: 3mm 0; padding-left: 4mm; border-left: 1.5pt solid #999; color: #444; }
"""

_TOPO = (
    '<div style="font-size:8pt;width:100%;margin:0 20mm;display:flex;justify-content:space-between;color:#555">'
    "<span>{nome}</span><span>{numero} · {codigo} v{versao} · {data}</span></div>"
)
_RODAPE = (
    '<div style="font-size:8pt;width:100%;margin:0 20mm;display:flex;justify-content:space-between;color:#555">'
    '<span>{identificacao}</span><span>página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>'
)


def _html(markdown: str, titulo: str) -> str:
    if not shutil.which("pandoc"):
        raise RuntimeError("pandoc não encontrado no PATH")
    corpo = subprocess.run(
        ["pandoc", "--from=gfm", "--to=html5"], input=markdown, capture_output=True, text=True, check=True
    ).stdout
    return (
        f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        f"<title>{html.escape(titulo)}</title><style>{_CSS}</style></head><body>{corpo}</body></html>"
    )


def gerar_pdf(texto_modelo: str, valores: dict[str, str], destino: Path, *, com_notas: bool = False) -> Path:
    """Preenche o modelo e grava o PDF. O cabeçalho e o rodapé usam campos fixos:

    `contratada_nome`, `documento_numero`, `data` e `contratada_identificacao`
    (a linha do rodapé: razão social e CNPJ, ou só o nome antes do CNPJ, D3).
    """
    from playwright.sync_api import sync_playwright  # extra [ui]: só quem gera PDF precisa

    modelo = ler_modelo(texto_modelo)
    fixos = ("contratada_nome", "documento_numero", "data", "contratada_identificacao")
    faltando = [c for c in fixos if not str(valores.get(c, "")).strip()]
    if faltando:
        raise CampoFaltando(faltando)
    corpo = preencher(modelo.corpo, valores)
    if com_notas and modelo.notas.strip():
        if campos_do_modelo(modelo.notas):
            raise ValueError("as notas não podem ter {{campo}}; use [colchetes]")
        corpo += "\n\n---\n\n" + modelo.notas
    esc = {k: html.escape(str(valores[k])) for k in fixos}
    topo = _TOPO.format(
        nome=esc["contratada_nome"], numero=esc["documento_numero"], codigo=html.escape(modelo.codigo),
        versao=html.escape(modelo.versao), data=esc["data"],
    )
    rodape = _RODAPE.format(identificacao=esc["contratada_identificacao"])

    destino.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            pagina = navegador.new_page()
            pagina.set_content(_html(corpo, modelo.titulo), wait_until="load")
            pagina.pdf(
                path=str(destino), format="A4", print_background=True, prefer_css_page_size=True,
                display_header_footer=True, header_template=topo, footer_template=rodape,
            )
        finally:
            navegador.close()
    return destino
