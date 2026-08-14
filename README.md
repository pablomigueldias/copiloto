# Copiloto

> Assistente pessoal autônomo, local-first, 100% open source.
> Não é uma IA que sabe tudo. É uma IA que sabe **do meu mundo**.

Um modelo pequeno rodando local (Qwen3 4B/8B via Ollama), cercado de contexto
sobre um domínio restrito: meus projetos, meu jeito de escrever, minha stack,
meu mercado.

> **Modelo pequeno com o contexto certo bate modelo grande sem contexto,
> na tarefa específica.**

## Princípio de arquitetura (não negociável)

**O código decide o fluxo. O LLM faz tarefas pontuais e bem delimitadas.**

Máquinas de estado no Postgres, pipelines determinísticos em Python. O LLM entra
em nós isolados — classificar, extrair, reescrever, resumir — sempre com parser
tolerante a falha e retry. Um 8B quantizado não é confiável para escolher qual
ferramenta chamar, em que ordem, e avaliar se deu certo.

## Estado

**Fase 0 concluída** — chão do projeto: config, banco, migration única, auth,
observabilidade, suíte de smoke. Sem funcionalidade de produto ainda.

Roadmap completo: `docs/Refaroracao.md` no repo `prospector`.

## Stack

FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 + pgvector · Alembic ·
Ollama (Qwen3 + bge-m3) · Redis + arq (a partir da Fase 4) · Next.js (a partir
da Fase 1)

Tudo com licença permissiva e self-hostável. Sem API paga em regime permanente.

## Subir

```bash
cp .env.example .env

docker compose up -d              # postgres:5434 + redis:6380
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

alembic upgrade head
python scripts/seed_admin.py      # usa ADMIN_EMAIL / ADMIN_SENHA_INICIAL

uvicorn app.api.main:app --reload --port 8010
```

## Desenvolver

```bash
ruff check .          # lint
pytest                # suíte (precisa do Postgres de pé)
alembic revision -m "..."   # nova migration
```

Regra do projeto: **1 passo = 1 commit**, com a suíte passando ao fim de cada um.
