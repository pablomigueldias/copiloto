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

Primeira vez:

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d              # postgres:5434 + redis:6380
alembic upgrade head
python scripts/seed_admin.py      # usa ADMIN_EMAIL / ADMIN_SENHA_INICIAL
```

Depois disso, um comando só:

```bash
./scripts/copiloto.sh up          # docker + ollama + migration + worker + api
./scripts/copiloto.sh status      # o que está de pé (e o que não está)
./scripts/copiloto.sh down
```

O painel abre em **http://localhost:8010**.

> **O worker precisa estar rodando.** É ele que reindexa o conhecimento, embeda
> os exemplos de estilo e marca follow-up vencido. Sem ele o sistema *parece*
> funcionar e vai envelhecendo em silêncio — foi assim que 42 PDFs ficaram 14 h
> fora do índice. O cabeçalho do painel mostra um ponto para ele, e o
> `status` responde a mesma pergunta no terminal.
>
> Para ele subir junto com a sessão: `scripts/systemd/` tem os units.

## LLM local

O Ollama roda **nativo, fora do Docker** (precisa da GPU). As variáveis que
fazem dois modelos caberem em 6 GB estão versionadas no script:

```bash
./scripts/ollama-serve.sh &       # ou num terminal separado

ollama pull phi4-mini             # classificar / extrair → JSON
ollama pull qwen3:4b              # redigir / resumir
ollama pull bge-m3                # embeddings (1024 dim)

python scripts/bench_modelos.py   # tokens/s, VRAM pico, tempo de carga
```

## Transcrever aula, curso ou reunião

No painel, o card **Transcrever**: escolha a fonte (áudio do sistema ou
microfone), clique em **gravar** antes de dar play, e o texto vai aparecendo na
tela. Ao parar, o modelo local reescreve, sugere título, pasta e tags — você
confirma e a nota entra no vault já indexada.

```bash
pip install -e ".[transcricao]"   # faster-whisper (~200 MB)
sudo apt install ffmpeg
```

Pelo terminal, o mesmo caminho: `python scripts/transcrever.py`.

O Whisper roda na **CPU** de propósito: a GPU fica livre para o Ollama, que é
quem reescreve depois. Num Ryzen 5600 o `small` transcreve a ~6,6× tempo real.

> `data/glossario.json` é o que faz a transcrição melhorar com o uso: cada nota
> mostra o que foi corrigido (`pigvector → pgvector`), e o que o Whisper errou e
> ficou faltando você acrescenta ali.

## Desenvolver

```bash
ruff check .          # lint
pytest                # suíte (precisa do Postgres de pé)
pytest -m ui          # testes de navegador (pip install -e ".[ui]")
alembic revision -m "..."   # nova migration
```

Os testes de navegador ficam fora do `pytest` padrão porque sobem um `uvicorn` e
um Chromium. **Rode-os sempre que mexer no front:** os defeitos que motivaram a
Fase 6 passaram por 375 testes verdes — nenhum deles abria um navegador.

Regra do projeto: **1 passo = 1 commit**, com a suíte passando ao fim de cada um.
