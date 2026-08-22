"""App FastAPI do Copiloto.

Fase 0: health + auth, e só. Cada agente entra como router próprio na sua fase.
Sem scheduler in-process: a partir da Fase 4 o trabalho de fundo é do worker
`arq`, fora do processo da API.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.routers import auth as auth_router
from app.api.routers import candidatura as candidatura_router
from app.api.routers import conhecimento as conhecimento_router
from app.api.routers import estudo as estudo_router
from app.api.routers import fila as fila_router
from app.api.routers import observabilidade as observabilidade_router
from app.api.routers import painel as painel_router
from app.api.routers import transcricao as transcricao_router
from app.api.services.auth.cookie import cookie_name
from app.api.services.auth.csrf import valido as csrf_valido
from app.config import settings
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
app.include_router(estudo_router.router)
app.include_router(fila_router.router)
app.include_router(candidatura_router.router)
app.include_router(painel_router.router)
app.include_router(transcricao_router.router)

# ── A raiz ────────────────────────────────────────────────────────────────
#
# O painel deixou de morar aqui. Era HTML+CSS+JS puro servido por `StaticFiles`
# no mesmo processo; virou um app Next.js em `web/`, e o motivo foi o design
# system em `web/modelo` — reproduzir oito telas desenhadas à mão em
# `painel.css` seria escrever um framework de componentes sem chamá-lo assim.
#
# A raiz redireciona em vez de dar 404 porque `http://localhost:8010` está no
# favorito e na documentação há meses. `307` e não `301`: permanente fica no
# cache do navegador para sempre, e o dia em que o front voltar a ser servido
# daqui — um `next build` estático, por exemplo — o redirecionamento gravado
# seria impossível de desfazer sem limpar o cache de cada máquina.
FRONT_URL = settings.front_url


@app.get("/", include_in_schema=False)
async def raiz() -> RedirectResponse:
    return RedirectResponse(FRONT_URL, status_code=307)
