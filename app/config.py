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
    ollama_model_redacao: str = "gemma4:e4b"   # redigir / resumir (vencedor do bake-off)
    ollama_model_embedding: str = "bge-m3"     # vetor de 1024 dimensões
    # Atende a tarefa `compreender`: ler um texto longo e dizer do que ele trata.
    # É lento (22 tok/s contra 66 do gemma4:e4b) e não fica residente junto do
    # embedder, então só vale onde a chamada é uma só e a qualidade decide o
    # resultado — o fichamento de uma transcrição é exatamente isso.
    ollama_model_pesado: str = "llama3.1:8b"

    # ── LLM de fora (o escape da §10 do plano) ────────────────────
    # A regra: sai o que precisa de raciocínio, fica o que o modelo local já
    # resolve. Medido em 17/08/2026 sobre as 234 chamadas do histórico, se
    # tudo tivesse rodado no Gemini:
    #
    #   redigir      157 chamadas   US$ 1,155   ← 83% da conta, e a tarefa
    #                                             onde a API menos acrescenta
    #   extrair       40 chamadas   US$ 0,100
    #   resumir       17 chamadas   US$ 0,077
    #   compreender   13 chamadas   US$ 0,055
    #   classificar    7 chamadas   US$ 0,005
    #
    # `redigir` NÃO entra por tarefa: os 157 são a reescrita do bloco ao vivo
    # (8 por aula), que transforma fala em prosa e não resolve lógica nenhuma —
    # e que a Fase T pôs de propósito na GPU que ficava ociosa durante a aula.
    # O currículo, que é `redigir` e importa, entra por `gemini_agentes`.
    #
    # Sem chave, isto tudo é ignorado e roda local — é o que faz a suíte e uma
    # máquina sem internet passarem sem tratamento especial.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.7-flash"
    # `extrair` é o único aqui sem falha medida do modelo local; entrou porque
    # alimenta o match e o currículo, e custa US$ 0,0025 por chamada. Se algum
    # dia o phi4-mini provar que basta, é o primeiro a voltar.
    gemini_tarefas: str = "compreender,classificar,resumir,extrair"

    # ── O modelo pesado, onde a consequência do erro é alta ───────
    # **O fichamento saiu daqui, e a medida é o motivo.** Em 17/08/2026, na
    # mesma aula: o `2.5-pro` acertou 5 de 5 e o `3.7-flash` acertou 4 de 4 — o
    # Pro não errou, só não acertou *mais*. E cobrou 40 s contra 8 s, que caem
    # inteiros na espera depois do `parar`: os 75 s que a Fase T conquistou
    # viravam ~105 s. Pagar 5× o tempo por empate é o oposto do que aquela fase
    # fez.
    #
    # O currículo fica, por dois motivos que o fichamento não tem: nunca foi
    # medido, e lá a latência não custa nada — o currículo se gera uma vez, sem
    # ninguém olhando a tela.
    #
    # `gemini-2.5-pro` e não o `3.1-pro-preview`: os dois acertaram igual no
    # sweep, o 2.5 é estável (o outro é preview, que muda e sai do ar) e custa
    # 40% menos.
    gemini_model_pesado: str = "gemini-2.5-pro"
    # Tarefa ou prefixo de agente — mesma regra de casamento do `gemini_agentes`.
    gemini_pesado: str = "candidatura.curriculo"

    @property
    def gemini_pesado_list(self) -> list[str]:
        return [p.strip() for p in self.gemini_pesado.split(",") if p.strip()]

    # Por agente, porque tarefa sozinha não separa os dois usos de `redigir`:
    # `conhecimento.transcricao.bloco{N}` roda 8× por aula e **tem** que ficar
    # local (é o que a Fase T moveu para dentro da aula, na GPU ociosa), e
    # `candidatura.curriculo.{etapa}` é o texto que vai para uma entrevista de
    # verdade. Casamento por prefixo: `candidatura.curriculo` pega as etapas.
    gemini_agentes: str = "candidatura.curriculo"

    @property
    def gemini_tarefas_list(self) -> list[str]:
        return [t.strip() for t in self.gemini_tarefas.split(",") if t.strip()]

    @property
    def gemini_agentes_list(self) -> list[str]:
        return [a.strip() for a in self.gemini_agentes.split(",") if a.strip()]

    # ── Base de conhecimento ──────────────────────────────────────
    # Pastas varridas pelo indexador: `tipo:caminho`, separadas por vírgula.
    # Sem prefixo, o tipo é `nota`. Não é "o vault do Obsidian" de propósito:
    # hoje não existe vault nesta máquina, e o parser entende
    # frontmatter/tag/wikilink de qualquer jeito — no dia em que o vault
    # nascer, entra aqui sem código novo.
    #
    # O tipo importa porque é a unidade de reindexação e de filtro na busca:
    # "só nas minhas notas" e "só nos READMEs" são perguntas diferentes.
    conhecimento_fontes: str = (
        "nota:/mnt/dados/Second-Brain,"  # o vault do Obsidian — a fonte principal
        "nota:~/Documentos/Estudos,"
        "repo:~/Documentos/copiloto,"    # inclui docs/ — planejamento fora do git
        "pdf:/mnt/dados/Second-Brain"
    )
    conhecimento_lote_embedding: int = 16

    # ── Transcrição (aula, curso, reunião) ────────────────────────
    # Dois modelos porque são duas situações de VRAM, não por indecisão: ao vivo
    # o `gemma4:e4b` reescreve os blocos e ocupa ~4 dos 6 GB, então o Whisper
    # entra pequeno e quantizado; no caminho de arquivo a placa é toda dele.
    # A escolha de dispositivo e precisão está em `app/conhecimento/whisper.py`.
    whisper_modelo: str = "large-v3-turbo"    # ao vivo, dividindo a GPU
    whisper_modelo_arquivo: str = "large-v3"  # arquivo/reprocessamento, GPU livre
    whisper_dispositivo: str = "auto"         # 'auto' | 'cuda' | 'cpu'
    whisper_idioma: str = "pt"                # 'pt', 'en' ou 'auto'

    @property
    def conhecimento_fontes_list(self) -> list[tuple[str, str]]:
        """`[(tipo, caminho), ...]` — sem prefixo, o tipo é `nota`."""
        saida: list[tuple[str, str]] = []
        for bruto in self.conhecimento_fontes.split(","):
            entrada = bruto.strip()
            if not entrada:
                continue
            tipo, sep, caminho = entrada.partition(":")
            saida.append((tipo.strip(), caminho.strip()) if sep else ("nota", entrada))
        return saida

    # ── Worker (Fase 4) ───────────────────────────────────────────
    # Porta 6380 no compose: a 6379 pode estar ocupada por outro projeto.
    redis_url: str = "redis://localhost:6380"
    # Intervalo da varredura do conhecimento. Dez minutos porque a varredura
    # incremental custa segundos quando nada mudou, e "em até 10 min" contra
    # "instantâneo" não paga uma dependência de watcher (§2 da fase04).
    worker_reindexar_minutos: int = 10

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
