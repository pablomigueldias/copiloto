# Copiloto

**Assistente pessoal autônomo — RAG local, transcrição na GPU, agentes com aprovação humana.**

Um sistema de produção de uma pessoa só: FastAPI assíncrono, PostgreSQL com
pgvector, modelos rodando em 6 GB de VRAM e uma API externa entrando só onde eu
medi que o local falhava. Não é um notebook de estudo nem um wrapper de chat —
é um serviço que roda todo dia, tem migrations versionadas, 685 testes e um
painel Next.js na frente.

> **Pablo Miguel Dias Ortiz** — AI Engineer · Python, LLMs e Automação
> Análise e Desenvolvimento de Sistemas (Faculdade Impacta, 08/2024 – 12/2026)

```
Python 3.12 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 + pgvector · Alembic
Ollama (Gemma · Phi-4 · Llama 3.1 · bge-m3) · Gemini API · Redis + arq
faster-whisper large-v3 na GPU · Next.js 16 · TypeScript · Tailwind 4 · Playwright
Docker Compose · systemd · pytest · ruff · ESLint
```

| | |
|---|---|
| **685 testes** | 666 de unidade/integração + 19 de navegador |
| **14.081 linhas** de Python em `app/` | 98 arquivos, `ruff` limpo |
| **5.862 linhas** de front | `tsc --noEmit` e `eslint` limpos |
| **3.064 chunks** indexados | 871 documentos: 615 PDFs, 202 notas, 32 repos |
| **726 chamadas de LLM** registradas | provider, latência, tokens e erro, uma linha cada |

---

## O que este projeto demonstra

| Competência | Onde ver, e o que exatamente |
|---|---|
| **RAG / busca semântica** | `app/conhecimento/` — busca híbrida (vetorial + full-text) fundida por *Reciprocal Rank Fusion*, índice HNSW no pgvector, corte de distância que faz o sistema recusar em vez de alucinar |
| **Integração de LLMs em produção** | `app/llm/gateway.py` — roteamento por tarefa **e** por agente, retry com reprompt em JSON inválido, circuit breaker por modelo, queda automática para o modelo local, semáforo de concorrência para caber em 6 GB |
| **API assíncrona** | `app/api/` — FastAPI + SQLAlchemy 2.0 async, autenticação por cookie httpOnly com CSRF, schemas Pydantic, 8 routers |
| **Modelagem e migrations** | `app/db/models/`, `alembic/` — 15 tabelas de domínio, migrations escritas à mão, `ON DELETE CASCADE` onde o domínio pede |
| **Pipelines determinísticos** | `app/candidatura/`, `app/estudo/` — máquinas de estado no Postgres; o LLM entra em nós isolados, nunca no controle de fluxo |
| **Processamento de áudio / ML aplicado** | `app/conhecimento/transcricao.py` — faster-whisper na GPU, reescrita em blocos durante a gravação, glossário de correção de termos técnicos |
| **Front-end** | `web/` — Next.js 16 (App Router), TypeScript estrito, design system em OKLCH, 9 telas |
| **Qualidade e processo** | `tests/` — 41 arquivos, incluindo testes de navegador com Playwright; 1 passo = 1 commit, suíte verde em cada um |
| **Infra** | `docker-compose.yml`, `scripts/copiloto.sh`, `scripts/systemd/` — sobe banco, fila, worker, API e front num comando |

---

## O que ele faz

### 1. Responde sobre o que eu estudei — citando a fonte

Indexa notas do Obsidian, PDFs página a página e READMEs de repositório num banco
vetorial. A busca é **híbrida** porque nenhuma das duas sozinha resolve: a
vetorial não acha "pgvector" escrito exatamente assim, e a lexical não acha
"armazenamento de vetores".

**Ele recusa quando não sabe.** Se a distância do melhor trecho passa do corte, a
resposta é "não está nas minhas notas" em 0,2 s, em vez de uma alucinação
educada. Numa avaliação de 12 perguntas fixas — 8 com resposta no índice, 4 sem —
o acerto foi 12/12.

O índice e a busca são **inteiramente locais**: o embedder é o `bge-m3` na minha
máquina, 1024 dimensões.

### 2. Transcreve aula e reunião, e organiza no vault

Aperto **gravar** no painel, assisto o vídeo, e o texto aparece na tela a cada
20 segundos. Os blocos são reescritos **durante a aula**, na GPU que antes ficava
ociosa: ao parar sobra um bloco e o fichamento, ~75 s em vez de 3 min 30.

A saída não é a transcrição bem formatada — é uma nota de estudo, com título,
tags, destaques e vizinhas ligadas.

**O título não é chute, e a pasta também não.** Os dois saem do vault: a busca
semântica traz as notas irmãs *com o trecho que casou*, e o modelo vê como as
vizinhas se chamam antes de nomear esta. Sem vizinho próximo (distância > 0,44,
medida), a nota vai para `_inbox` e a tela diz "assunto novo" — o sistema só
afirma o destino quando tem evidência dele.

**E o destaque é conferido contra a aula.** O que cita um número ou um vocabulário
que não aparece na transcrição sai marcado com ⚠, nunca apagado: o modelo pode
estar certo e o Whisper ter perdido a frase.

### 3. Devolve as questões de prova na hora certa

Repetição espaçada sobre um acervo de questões extraídas de provas anteriores,
com gabarito conferido no oficial da banca — no bloco do cargo correspondente,
porque cadernos são compartilhados entre níveis e gabaritos não.

| aconteceu | quando volta |
|---|---|
| acertei | 7 dias, e o intervalo cresce ×2,2 a cada acerto seguido (teto 180) |
| errei | 2 dias, e a sequência **zera** |
| adiei | 30 dias, e **não conta como acerto** |

Errar não recua um degrau, zera: quem errou depois de 35 dias não sabia há 35
dias, sabia há 7.

**A tela deixa tentar de novo antes de revelar, e só a primeira tentativa
reagenda** — se as duas contassem igual, o intervalo cresceria sobre uma memória
que não existe. E **o gabarito não desce para o cliente**: não viaja com a questão
nem dentro da string de origem, porque se estivesse no DevTools a diferença entre
"eu sabia" e "eu vi" sumiria do histórico — e é o histórico que agenda a revisão.

### 4. Adapta meu currículo a uma vaga, sem inventar nada

Colo a descrição da vaga; ele extrai os requisitos, cruza com o meu Perfil Mestre,
calcula a aderência com evidência item a item, e escreve um currículo adaptado em
PDF pronto para ATS.

**A anti-alucinação são três camadas, e a terceira é a que vale:**

1. o prompt recebe só o meu perfil e a vaga;
2. a saída referencia projetos e experiências pelo nome exato do perfil;
3. **toda tecnologia citada é conferida contra uma lista branca** — o que não está
   no perfil é removido e **contado**. O número de tentativas de invenção vira
   métrica, não surpresa em entrevista.

O PDF é feito para o parser, não para impressionar: uma coluna, sem tabela, sem
ícone no lugar de rótulo, Helvetica. Se vazar para a segunda página, uma escada de
quatro degraus de compactação tenta caber em uma.

### 5. Acompanha as candidaturas

Funil, taxa de resposta, dias até responder e follow-up vencido. A métrica mais
útil é a última: **os requisitos que mais se repetem nas vagas e que eu não
tenho**. Trinta candidaturas viram uma lista de estudo derivada do que o mercado
pediu.

### 6. Para e espera por mim

Todo texto que o modelo escreve em meu nome vai para uma **fila de aprovação**. O
agente observa e prepara sozinho; executar é decisão minha — não existe rota de
enviar.

E daí nasce um dataset sem esforço extra: o que eu aprovo vira exemplo de estilo
(few-shot); o que eu **edito antes de aprovar** vira par de preferência para
fine-tune. Cem revisões viram cem pares, produzidos por uso normal.

---

## O princípio de arquitetura (não negociável)

> **O código decide o fluxo. O LLM faz tarefas pontuais e bem delimitadas.**

Máquinas de estado no Postgres, pipelines determinísticos em Python. O LLM entra
em nós isolados — classificar, extrair, reescrever, resumir — sempre com parser
tolerante a falha e retry.

Isso **não mudou** quando parte da inferência saiu da máquina, e é o que tornou a
saída barata: trocar o destino de uma tarefa é editar o `.env`, porque nenhum
agente fala com modelo nenhum diretamente.

Cada vez que o modelo errou, o conserto foi mover a decisão para código:

| o modelo errou | o conserto |
|---|---|
| escreveu o currículo em 3ª pessoa | conversor de conjugação determinístico |
| citou tecnologia que eu não uso | lista branca do Perfil Mestre |
| ouviu "pigvector" | glossário de substituição |
| manteve "se inscreve no canal" | filtro de ruído por padrão fechado |
| escreveu `\rightarrow` dentro do JSON | parser que reconhece LaTeX pelo nome |
| destacou "2^n" numa aula que não disse | âncora do destaque no corpo (⚠) |

Cada erro vira uma regra que **nunca mais falha**. É por isso que os erros do
modelo são o combustível da arquitetura, não a falência dela.

---

## Decisões que valem explicação

**Local por padrão, externo por medida.** A régua não é "o que é mais
inteligente", é *"onde o modelo local falhou numa medida que eu registrei"*. Numa
aula de lógica proposicional o `llama3.1:8b` escreveu *"a negação de P ou Q é P e
Q"* — uma Lei de Morgan sem as negações, falsa, na seção "Para lembrar" de uma
nota. Quatro tarefas saíram da máquina por causa disso, e o resto ficou.

**Todo LLM passa por um gateway.** Semáforo para a inferência local (duas
concorrentes em 6 GB não ficam lentas — uma escorrega para a RAM e o tempo explode
uma ordem de grandeza), JSON com retry e reprompt, circuit breaker por modelo,
queda para o local quando a API não responde, e observabilidade sempre. Foi essa
tabela que mostrou por que uma nota saiu pela metade: quatro blocos com latência
de exatamente 180 014 ms, o timeout.

**Sem chave, tudo roda local.** `GEMINI_API_KEY` vazio faz o roteamento externo
ser ignorado inteiro. É o que faz a suíte e uma máquina sem internet passarem sem
tratamento especial — e é testado.

**O front é Next.js porque o design pediu.** Foi HTML+CSS+JS puro por seis fases,
e a troca não foi pela stack: foi por um design system de nove telas com escala
tipográfica própria, rampas em OKLCH e estados de revisão. Reproduzir aquilo à mão
seria escrever um framework de componentes sem chamá-lo assim.

**Testes de navegador não são luxo.** Os defeitos mais graves do projeto passaram
por centenas de testes unitários verdes: o refresco de 15 s apagava o texto que eu
estava digitando na fila, e um botão novo "não funcionava" porque o cache servia o
JavaScript de ontem. Nenhuma suíte que não abre um Chromium pegaria os dois.

---
---

## Rodar

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d              # postgres:5434 + redis:6380
alembic upgrade head
python scripts/seed_admin.py
```

Depois disso, um comando:

```bash
cd web && npm install && cd ..    # uma vez só
./scripts/copiloto.sh up          # docker, ollama, migration, worker, api e front
```

Painel em **http://localhost:3000** — a API fica na 8010, e a raiz dela redireciona
para cá.

### Modelos locais

```bash
ollama pull phi4-mini    # classificar / extrair → JSON (caminho sem chave)
ollama pull gemma4:e4b   # redigir / resumir (vencedor do bake-off)
ollama pull llama3.1:8b  # compreender texto longo (queda do fichamento)
ollama pull bge-m3       # embeddings (1024 dimensões) — sempre local
```

### Opcionais

```bash
GEMINI_API_KEY=...                    # vazio = tudo local, sem tratamento especial
pip install -e ".[transcricao]"       # + sudo apt install ffmpeg
pip install -e ".[transcricao-gpu]"   # cuBLAS + cuDNN, para o Whisper na GPU
```

Sem o extra `-gpu`, o Whisper cai para a CPU sozinho e avisa no log.

---

## Comandos

```bash
python scripts/ingerir.py                        # indexa notas, PDFs e repos
python scripts/perguntar.py "..."                # pergunta pelo terminal
python scripts/transcrever.py                    # grava e transcreve
python scripts/vaga.py --gerar <id>              # currículo adaptado + PDF
python scripts/reprocessar_nota.py "<nota>"      # passa a nota pelo pipeline atual
python scripts/importar_questoes.py "<json>"     # acervo de questões (idempotente)
python scripts/avaliar_pergunta.py               # as 12 perguntas de avaliação
python scripts/bakeoff.py                        # compara modelos às cegas
```

---

## Desenvolver

```bash
ruff check .                      # lint do Python
pytest                            # 666 testes (precisa do Postgres de pé)
pytest -m ui                      # 19 testes de navegador — pip install -e ".[ui]"
cd web && npx tsc --noEmit && npm run lint
``