"""Configuração da aplicação — tudo vem do .env, nada hardcoded.

Regra desta base: uma chave só entra aqui quando existe código que a lê. Foi o
inchaço do arquivo equivalente no repo antigo (292 linhas, com IDs de workspace
de terceiros hardcoded) que motivou a reconstrução.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Banco ─────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://copiloto:copiloto_dev@localhost:5434/copiloto"
    )
    db_echo: bool = False

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"
    timezone: str = "America/Sao_Paulo"

    # ── Observabilidade ───────────────────────────────────────────
    observer_enabled: bool = True
    observ_store_payloads: bool = True

    # ── LLM local ─────────────────────────────────────────────────
    # Um modelo por TAREFA, não um generalista: em 6 GB o que decide não é
    # caber, é caber junto. phi4-mini (2,5 GB) + bge-m3 (1,2 GB) ficam os dois
    # residentes e o caminho quente nunca paga troca de modelo.
    ollama_host: str = "http://localhost:11434"
    ollama_model_extracao: str = "phi4-mini"   # classificar / extrair → JSON
    ollama_model_redacao: str = "qwen3:4b"     # redigir / resumir (alvo do LoRA)
    ollama_model_embedding: str = "bge-m3"     # vetor de 1024 dimensões
    # Instalado para tarefas pontuais em que 6s de carga não incomodam. NÃO
    # convive com o embedder residente — por isso não está em nenhuma rota.
    ollama_model_pesado: str = "llama3.1:8b"

    llm_timeout_s: float = 180.0      # 4B em 6 GB gerando 800 tokens passa de 60s
    llm_max_tentativas: int = 3       # vale para JSON inválido e para erro de rede
    llm_breaker_falhas: int = 3       # falhas seguidas que abrem o circuito
    llm_breaker_minutos: int = 5      # tempo que ele fica aberto

    # ── Sessão ────────────────────────────────────────────────────
    # Em produção (HTTPS) fica true → cookie __Host-sessao. Em dev http puro
    # precisa ser false, senão o browser recusa o cookie.
    session_cookie_secure: bool = True
    session_dias_absoluto: int = 7
    session_horas_inatividade: int = 24

    # ── Seed do admin (scripts/seed_admin.py) ─────────────────────
    admin_email: str = ""
    admin_senha_inicial: str = ""

    # ── CORS ──────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
