"""Varredura (Fase 1, passo 3): o site lido página por página, até achar tudo.

Site falso (httpx.MockTransport) e navegador falso: o que precisa ser verdade é
a ordem (contato e equipe antes do blog), a parada assim que está completo, o
teto, o mesmo site só, e a página montada por JavaScript lida de novo no
navegador.
"""
from __future__ import annotations

import httpx

from app.comercial.crm import varredura

TEXTO = "Clínica de psicologia com atendimento para adultos e casais. " * 10


def _pagina(corpo: str = "", links: tuple[str, ...] = ()) -> str:
    a = " ".join(f'<a href="{h}">{h}</a>' for h in links)
    return f"<html><body><p>{TEXTO}</p>{corpo}{a}</body></html>"


def _site(paginas: dict[str, str]) -> httpx.AsyncClient:
    lidas: list[str] = []

    def resposta(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        lidas.append(req.url.path)
        html = paginas.get(req.url.path)
        if html is None:
            return httpx.Response(404)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    c = httpx.AsyncClient(transport=httpx.MockTransport(resposta))
    c.lidas = lidas  # type: ignore[attr-defined]
    return c


class NavegadorFalso(varredura.Navegador):
    def __init__(self, renderizado: dict[str, str] | None = None) -> None:
        super().__init__()
        self.renderizado = renderizado or {}
        self.pedidas: list[str] = []

    async def html(self, url):
        self.pedidas.append(url)
        return self.renderizado.get(url)

    async def fechar(self):
        pass


async def _varrer(c, completo=lambda p: False, navegador=None, **kw):
    return await varredura.varrer(
        "clinica.test", completo, cliente=c, navegador=navegador or NavegadorFalso(), intervalo_s=0, **kw
    )


async def test_contato_e_equipe_antes_do_blog():
    site = {
        "/": _pagina(links=("/blog/post-1", "/blog/post-2", "/equipe", "/contato", "/sobre")),
        "/blog/post-1": _pagina(), "/blog/post-2": _pagina(),
        "/equipe": _pagina(), "/contato": _pagina(), "/sobre": _pagina(),
    }
    async with _site(site) as c:
        v = await _varrer(c)
    caminhos = [u.removeprefix("https://clinica.test") or "/" for u, _ in v.paginas]
    assert caminhos[:4] == ["/", "/contato", "/equipe", "/sobre"]
    assert set(caminhos[4:]) == {"/blog/post-1", "/blog/post-2"}
    assert v.parou_porque == "acabaram as páginas"


async def test_acha_a_pagina_funda_e_para_quando_completa():
    """O e-mail está em /sobre → /quem-somos/equipe → /contato-comercial: três cliques."""
    site = {
        "/": _pagina(links=("/sobre", "/blog")),
        "/sobre": _pagina(links=("/quem-somos/equipe",)),
        "/quem-somos/equipe": _pagina(links=("/contato-comercial", "/blog/velho")),
        "/contato-comercial": _pagina("oi@clinica.test", links=("/depois",)),
        "/blog": _pagina(), "/blog/velho": _pagina(), "/depois": _pagina(),
    }
    async with _site(site) as c:
        v = await _varrer(c, completo=lambda p: any("oi@clinica.test" in h for _, h in p))
        lidas = c.lidas
    assert v.parou_porque == "completo"
    assert v.paginas[-1][0].endswith("/contato-comercial")
    assert "/depois" not in lidas  # achou tudo: não lê mais nada


async def test_teto_de_paginas():
    site = {"/": _pagina(links=tuple(f"/p{i}" for i in range(40)))}
    site |= {f"/p{i}": _pagina() for i in range(40)}
    async with _site(site) as c:
        v = await _varrer(c, max_paginas=5)
    assert len(v.paginas) == 5 and v.parou_porque == "teto"


async def test_so_o_mesmo_site_e_so_paginas():
    site = {
        "/": _pagina(links=("https://outro.test/contato", "/cardapio.pdf", "/foto.jpg", "/contato#form", "/contato?x=1")),
        "/contato": _pagina(),
    }
    async with _site(site) as c:
        v = await _varrer(c)
        lidas = c.lidas
    assert [u for u, _ in v.paginas] == ["https://clinica.test", "https://clinica.test/contato"]
    assert lidas.count("/contato") == 1 and "/cardapio.pdf" not in lidas


async def test_site_fora_do_ar():
    async with _site({}) as c:
        v = await _varrer(c)
    assert v.paginas == [] and v.parou_porque == "sem acesso"


def test_sinais_de_javascript():
    assert varredura.precisa_javascript('<html><body><div id="root"></div><script src="/a.js"></script></body></html>')
    assert varredura.precisa_javascript(f"<body><noscript>Ative o JavaScript</noscript><p>{TEXTO}</p></body>")
    assert varredura.precisa_javascript("<body><p>Carregando…</p></body>")
    assert not varredura.precisa_javascript(_pagina())


async def test_pagina_de_javascript_e_lida_no_navegador():
    spa = '<html><body><div id="__next"></div><script src="/app.js"></script></body></html>'
    montada = _pagina("contato@clinica.test", links=("/equipe",))
    site = {"/": spa, "/equipe": _pagina()}
    nav = NavegadorFalso({"https://clinica.test": montada})
    async with _site(site) as c:
        v = await _varrer(c, navegador=nav)
    assert nav.pedidas == ["https://clinica.test"]  # /equipe tem texto: fica no httpx
    assert v.com_javascript == ["https://clinica.test"]
    assert "contato@clinica.test" in v.paginas[0][1]
    assert v.paginas[1][0].endswith("/equipe")  # o link só existia na versão montada


async def test_sem_navegador_fica_o_que_o_httpx_leu():
    spa = '<html><body><div id="root"></div></body></html>'
    async with _site({"/": spa}) as c:
        v = await _varrer(c, navegador=NavegadorFalso())
    assert v.paginas == [("https://clinica.test", spa)] and v.com_javascript == []
