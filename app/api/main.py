"""App FastAPI do Copiloto.

Fase 0: health + auth, e só. Cada agente entra como router próprio na sua fase.
Sem scheduler in-process: a partir da Fase 4 o trabalho de fundo é do worker
`arq`, fora do processo da API.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import auth as auth_router
from app.api.routers import candidatura as candidatura_router
from app.api.routers import conhecimento as conhecimento_router
from app.api.routers import fila as fila_router
from app.api.routers import observabilidade as observabilidade_router
from app.api.routers import painel as painel_router
from app.api.routers import transcricao as transcricao_router
from app.api.services.auth.cookie import cookie_name
from app.api.services.auth.csrf import valido as csrf_valido
from app.config import BASE_DIR, settings
from app.db.session import dispose_engine
from app.utils.logger import get_logger

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Copiloto subindo...")
    yield
    await dispose_engine()
    logger.info("Copiloto encerrando.")


app = FastAPI(
    title="Copiloto",
    description="Assistente pessoal autônomo, local-first.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_METODOS_MUTACAO = {"POST", "PUT", "PATCH", "DELETE"}
# O login estabelece uma sessão nova; exigir CSRF nele trava a re-autenticação
# quando o browser ainda carrega um cookie de sessão velho.
_CSRF_ISENTAS = {"/api/auth/login"}


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """Exige CSRF só quando a mutação vem autenticada por cookie de sessão.

    Requests sem cookie de sessão (clientes de API, webhooks com secret próprio)
    passam direto — não há o que forjar via browser.
    """
    if (
        request.method in _METODOS_MUTACAO
        and request.url.path not in _CSRF_ISENTAS
        and request.cookies.get(cookie_name())
        and not csrf_valido(request)
    ):
        return JSONResponse(
            status_code=403, content={"detail": "CSRF token inválido ou ausente."}
        )
    return await call_next(request)


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "service": "copiloto"}


app.include_router(auth_router.router)
app.include_router(observabilidade_router.router)
app.include_router(conhecimento_router.router)
app.include_router(fila_router.router)
app.include_router(candidatura_router.router)
app.include_router(painel_router.router)
app.include_router(transcricao_router.router)

# O painel é servido pelo mesmo processo: um `uvicorn` sobe API e tela juntos.
# HTML+CSS+JS puro, sem build — ver docs/fase-painel.md §2 para o porquê de não
# ser Next.js ainda. Fica por último para não sombrear nenhuma rota /api/*.
WEB_DIR = BASE_DIR / "app" / "web"


def _versao_dos_assets() -> str:
    """Impressão digital do front, para o navegador não servir JS velho.

    Sem carimbo, a aba aberta fica com o JS de antes do deploy e um botão novo
    simplesmente não existe nela — o defeito parece do botão e é do cache.

    O mtime mais recente dos arquivos servidos: muda quando eu edito, não muda
    a cada request, e não exige build nem hash de conteúdo.
    """
    if not WEB_DIR.is_dir():
        return "0"
    mtimes = [
        p.stat().st_mtime
        for p in WEB_DIR.rglob("*")
        if p.is_file() and p.suffix in {".js", ".css", ".html"}
    ]
    return str(int(max(mtimes))) if mtimes else "0"


if WEB_DIR.is_dir():

    @app.get("/", include_in_schema=False)
    async def painel_index() -> HTMLResponse:
        """O `index.html` com `?v=<mtime>` nos assets, sem cache.

        Só o HTML precisa chegar sempre fresco; JS e CSS podem ser cacheados
        para sempre, porque a URL deles muda quando o conteúdo muda.
        """
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("{{v}}", _versao_dos_assets())
        return HTMLResponse(
            html,
            headers={"Cache-Control": "no-cache, must-revalidate", "Pragma": "no-cache"},
        )

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="painel")
