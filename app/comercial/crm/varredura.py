"""Varrer o site da clínica, página por página, até achar o que importa.

O que importa para prospectar não mora sempre na página inicial: o e-mail está
em "contato", a equipe (os CRPs) em "equipe" ou "quem somos", o agendamento
num botão de outra página. Então a varredura segue os links do próprio site,
**as páginas com cara de ter a informação primeiro**, e **para assim que quem
chamou disser que está completo** (o Pesquisador: e-mail, WhatsApp,
agendamento e equipe). Não achou tudo, para no teto de páginas: é o site de
alguém, não um alvo de raspagem.

Cada página é lida pelo `httpx`, que é rápido. Página montada por JavaScript
(pouco texto visível, contêiner de SPA vazio, "ative o JavaScript") é lida de
novo no **Chromium do Playwright**, aberto uma vez só para a varredura toda e
só se precisar. Sem o Playwright instalado, fica o que o `httpx` leu.

Regras que valem nos dois caminhos: `robots.txt`, só o mesmo site, só páginas
(nada de PDF ou imagem), um intervalo curto entre as leituras.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from html import unescape
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.utils.logger import get_logger

logger = get_logger()

USER_AGENT = "PabloOrtizBot/1.0 (+https://pabloortiz.dev/contato)"
MAX_PAGINAS = 15
MAX_BYTES = 800_000
INTERVALO_S = 0.4
TEXTO_MINIMO = 300  # abaixo disso, a página provavelmente é montada por JavaScript

# Mais peso = mais cedo na fila. O que mais responde "como falar com a clínica".
_PRIORIDADE = [
    (re.compile(r"contato|contact|fale|atendimento", re.I), 5),
    (re.compile(r"equipe|profissionais|psicolog|terapeutas|corpo-clinico|nosso-time", re.I), 4),
    (re.compile(r"agend|marcar|consulta", re.I), 4),
    (re.compile(r"sobre|quem-somos|a-clinica|clinica", re.I), 3),
]
_NAO_PAGINA = re.compile(r"\.(pdf|jpe?g|png|gif|webp|svg|zip|docx?|xlsx?|mp4|mp3|css|js|ico)$", re.I)
_LINK = re.compile(r"""href\s*=\s*["']([^"'#]+)""", re.I)
_TAG = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.S | re.I)
_SPA_VAZIO = re.compile(
    r"""<div[^>]+id=["'](?:root|__next|app|__nuxt|__layout)["'][^>]*>\s*</div>""", re.I
)
_PEDE_JS = re.compile(r"(?:enable|ative|habilite|ativar) (?:o )?javascript", re.I)


@dataclass
class Varredura:
    paginas: list[tuple[str, str]] = field(default_factory=list)
    com_javascript: list[str] = field(default_factory=list)  # lidas pelo navegador
    parou_porque: str = ""  # "completo" | "teto" | "acabaram as páginas" | "sem acesso"


def texto_visivel(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", html))).strip()


def precisa_javascript(html: str) -> bool:
    """Sinais de página montada no navegador: o `httpx` só veria o esqueleto."""
    if _SPA_VAZIO.search(html) or _PEDE_JS.search(texto_visivel(html)):
        return True
    return len(texto_visivel(html)) < TEXTO_MINIMO


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _prioridade(url: str) -> int:
    caminho = urlparse(url).path
    return max((peso for padrao, peso in _PRIORIDADE if padrao.search(caminho)), default=1)


def _links(url: str, html: str, host: str) -> list[str]:
    saida = []
    for href in _LINK.findall(html):
        alvo = urljoin(url, unescape(href.strip())).split("?")[0].split("#")[0]
        if not alvo.startswith(("http://", "https://")) or _host(alvo) != host:
            continue
        if _NAO_PAGINA.search(urlparse(alvo).path):
            continue
        saida.append(alvo.rstrip("/") or alvo)
    return saida


class Navegador:
    """O Chromium do Playwright, aberto na primeira página que precisar dele."""

    def __init__(self) -> None:
        self._pw = None
        self._navegador = None
        self._contexto = None
        self.indisponivel = False

    async def html(self, url: str) -> str | None:
        if self.indisponivel:
            return None
        try:
            if self._contexto is None:
                from playwright.async_api import async_playwright

                self._pw = await async_playwright().start()
                self._navegador = await self._pw.chromium.launch()
                self._contexto = await self._navegador.new_context(user_agent=USER_AGENT)
            pagina = await self._contexto.new_page()
            try:
                await pagina.goto(url, wait_until="networkidle", timeout=15_000)
                return (await pagina.content())[:MAX_BYTES]
            finally:
                await pagina.close()
        except Exception as e:  # noqa: BLE001 — navegador é opcional: sem ele, fica o httpx
            logger.warning(f"Varredura: navegador indisponível para {url} ({e})")
            if self._contexto is None:
                self.indisponivel = True
            return None

    async def fechar(self) -> None:
        if self._navegador is not None:
            await self._navegador.close()
        if self._pw is not None:
            await self._pw.stop()


async def _robots(cliente: httpx.AsyncClient, base: str) -> RobotFileParser:
    robos = RobotFileParser()
    try:
        r = await cliente.get(f"{base}/robots.txt")
        robos.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        robos.parse([])
    return robos


async def varrer(
    site: str,
    completo: Callable[[list[tuple[str, str]]], bool],
    *,
    cliente: httpx.AsyncClient | None = None,
    navegador: Navegador | None = None,
    max_paginas: int = MAX_PAGINAS,
    intervalo_s: float = INTERVALO_S,
) -> Varredura:
    """Lê o site em ordem de prioridade até `completo(paginas)` ou o teto."""
    p = urlparse(site if re.match(r"^https?://", site, re.I) else f"https://{site}")
    base = f"{p.scheme}://{p.netloc}".lower()
    host = _host(base)
    resultado = Varredura()

    proprio_cliente = cliente is None
    cliente = cliente or httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    proprio_navegador = navegador is None
    navegador = navegador or Navegador()
    try:
        robos = await _robots(cliente, base)
        fila: dict[str, int] = {base: 10}  # url → prioridade; a inicial primeiro
        vistas: set[str] = set()
        while fila and len(resultado.paginas) < max_paginas:
            url = max(fila, key=lambda u: (fila[u], -len(u)))
            del fila[url]
            if url in vistas or not robos.can_fetch(USER_AGENT, url):
                continue
            vistas.add(url)
            if resultado.paginas and intervalo_s:
                await asyncio.sleep(intervalo_s)
            try:
                r = await cliente.get(url)
            except httpx.HTTPError:
                continue
            if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
                continue
            final = str(r.url).rstrip("/") or str(r.url)
            if _host(final) != host:
                continue  # redirecionou para fora do site
            html = r.text[:MAX_BYTES]
            if precisa_javascript(html) and (renderizado := await navegador.html(final)):
                html = renderizado
                resultado.com_javascript.append(final)
            vistas.add(final)
            resultado.paginas.append((final, html))
            if completo(resultado.paginas):
                resultado.parou_porque = "completo"
                return resultado
            for alvo in _links(final, html, host):
                if alvo not in vistas:
                    fila[alvo] = max(fila.get(alvo, 0), _prioridade(alvo))
        if not resultado.paginas:
            resultado.parou_porque = "sem acesso"
        else:
            resultado.parou_porque = "teto" if len(resultado.paginas) >= max_paginas else "acabaram as páginas"
        return resultado
    finally:
        if proprio_cliente:
            await cliente.aclose()
        if proprio_navegador:
            await navegador.fechar()
