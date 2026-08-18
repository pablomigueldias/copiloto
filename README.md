# Copiloto

> Assistente pessoal autônomo. **Local por padrão, externo por medida.**
> Não é uma IA que sabe tudo. É uma IA que sabe **do meu mundo**.

Modelos pequenos rodando na minha máquina (Ollama, 6 GB de VRAM), cercados de
contexto sobre um domínio restrito: meus projetos, meu jeito de escrever, minha
stack, meu mercado.

> **Modelo pequeno com o contexto certo bate modelo grande sem contexto,
> na tarefa específica.**

Isso continua sendo o princípio — e ele tem um limite, que eu encontrei medindo.
Numa aula de lógica proposicional, o `llama3.1:8b` escreveu *"a negação de P ou Q
é P e Q"*: uma Lei de Morgan sem as negações, falsa, na seção "Para lembrar" de
uma nota de estudo para concurso. **Quatro tarefas saíram da máquina por causa
disso**, e o resto ficou. Onde e por quê está em
[`docs/fase-hibrida.md`](docs/fase-hibrida.md).

```
FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 + pgvector · Alembic
Ollama (Gemma · Phi-4 · Llama 3.1 · bge-m3) · Gemini API · Redis + arq
faster-whisper large-v3 na GPU · front em HTML/CSS/JS puro, sem build
```

| | |
|---|---|
| **544 testes** | 527 de unidade/integração + 17 de navegador (Playwright) |
| **13.000 linhas** de Python | 102 arquivos, `ruff` limpo |
| **2.425 linhas** de front | sem `node_modules`, sem build, módulos ES nativos |
| **2.189 chunks** indexados | 294 documentos: 221 notas, 44 PDFs, 26 repos |

---

## O que ele faz

### 1. Responde sobre o que eu estudei — citando a fonte

Indexa notas do Obsidian, PDFs (página a página) e READMEs de repositório num
banco vetorial. A busca é **híbrida** — vetorial + full-text fundidos por
*Reciprocal Rank Fusion* — porque nenhuma das duas sozinha resolve: a vetorial
não acha "pgvector" escrito exatamente assim, e a lexical não acha
"armazenamento de vetores".

**Ele recusa quando não sabe.** Se a distância do melhor trecho passa do corte,
a resposta é "não está nas minhas notas" em 0,2 s, em vez de uma alucinação
educada. Numa avaliação de 12 perguntas fixas — 8 com resposta no índice, 4 sem
— o acerto foi 12/12.

O índice e a busca são **inteiramente locais**: o embedder é o `bge-m3` na minha
máquina, e trocá-lo custaria reindexar 2.189 chunks e migrar a dimensão da
coluna no pgvector, sem evidência de que ele seja o gargalo.

### 2. Adapta meu currículo a uma vaga, sem inventar nada

Colo a descrição da vaga; ele extrai os requisitos, cruza com o meu Perfil
Mestre, calcula a aderência com evidência item a item, e escreve um currículo
adaptado em PDF pronto para ATS.

**A regra que sustenta isso são três camadas, e a terceira é a que vale:**

1. o prompt recebe só o meu perfil e a vaga;
2. a saída referencia projetos e experiências pelo nome exato do perfil;
3. **toda tecnologia citada é conferida contra uma lista branca** — o que não
   está no perfil é removido e **contado**. O número de tentativas de invenção
   vira métrica, não surpresa em entrevista.

O PDF é feito para o parser, não para impressionar: uma coluna, sem tabela, sem
ícone no lugar de rótulo, Helvetica. Se vazar para uma segunda página, uma
escada de quatro degraus de compactação tenta caber em uma — porque currículo
cuja página 2 tem três linhas parece descuido antes de qualquer conteúdo.

### 3. Transcreve aula e reunião, e organiza no meu vault

Aperto **gravar** no painel, assisto o vídeo, e o texto vai aparecendo na tela a
cada 20 segundos. Os blocos são reescritos **durante a aula**, na GPU que antes
ficava ociosa: ao parar sobra um bloco e o fichamento, ~75 s em vez de 3 min 30.

O resultado não é a transcrição bem formatada — é uma nota de estudo:

```markdown
---
titulo: "Lógica Proposicional 5 — Negações e Equivalências"
tags: [logica-proposicional, negacao, equivalencia, leis-de-morgan]
duracao_min: 30
---

## Para lembrar
- **A negação da conjunção (P ∧ Q) é ¬P ∨ ¬Q — Lei de Morgan.**
- **A condicional (P → Q) equivale à contrapositiva (¬Q → ¬P).**

## Conteúdo
`⏱ 04:20`
### Negação das Operações Lógicas
...

## Relacionado
- [[logica-proposicional-3-conectivos-parte-2]]
```

**O título não é chute, e a pasta também não.** Os dois vêm do vault: a busca
semântica traz as notas irmãs *com o trecho que casou*, e o modelo vê que as
vizinhas se chamam "Lógica Proposicional 1/3/4 —" antes de nomear esta. Sem
vizinho próximo (distância > 0,44, medida), a nota vai para `_inbox` e a tela
diz "assunto novo" — o sistema só afirma o destino quando tem evidência dele.

**E o destaque é conferido contra a aula.** O que cita um número ou um
vocabulário que não aparece na transcrição sai marcado com ⚠, nunca apagado: o
modelo pode estar certo e o Whisper ter perdido a frase.

### 4. Acompanha as candidaturas

O que foi enviado, o que respondeu, o que sumiu, e o que precisa de follow-up
hoje. Com métricas: funil, taxa de resposta, dias até responder, e — a mais
útil — **os requisitos que mais se repetem nas vagas e que eu não tenho**. A
ideia é que trinta candidaturas virem uma lista de estudo derivada do que o
mercado pediu; hoje são 2 vagas e 33 eventos, então a métrica existe e a amostra
ainda não.

---

## O princípio de arquitetura (não negociável)

> **O código decide o fluxo. O LLM faz tarefas pontuais e bem delimitadas.**

Máquinas de estado no Postgres, pipelines determinísticos em Python. O LLM entra
em nós isolados — classificar, extrair, reescrever, resumir — sempre com parser
tolerante a falha e retry.

Isso **não mudou** quando parte do LLM saiu da máquina, e é o que tornou a saída
barata: trocar o destino de uma tarefa é editar o `.env`, porque nenhum agente
fala com modelo nenhum diretamente.

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
inteligente", é *"onde o modelo local falhou numa medida que eu registrei"*.
Hoje isso são quatro tarefas — compreender, classificar, resumir, extrair — mais
o currículo. Ficam locais o embedding (2.189 chunks indexados, migração cara,
zero evidência de problema) e a reescrita dos blocos da aula: são 83% do gasto
de token e a tarefa onde a API menos acrescenta, porque transformar fala em
prosa não é raciocínio. Detalhe e números em
[`docs/fase-hibrida.md`](docs/fase-hibrida.md).

**Todo LLM passa por um gateway.** Roteamento por tarefa *e por agente* (é o que
separa a reescrita do bloco de aula do currículo, que são a mesma tarefa),
semáforo para a inferência local (duas concorrentes em 6 GB não ficam lentas —
uma escorrega para a RAM e o tempo explode uma ordem de grandeza), JSON com
retry e reprompt, circuit breaker por modelo, **queda para o modelo local quando
a API não responde**, e observabilidade sempre, um registro por destino. Foi a
ausência disso no projeto anterior que produziu quatro caminhos de chamada, dos
quais só um media.

**Sem chave, tudo roda local.** `GEMINI_API_KEY` vazio faz o roteamento externo
ser ignorado inteiro. É o que faz a suíte e uma máquina sem internet passarem
sem tratamento especial — e é testado.

**O Whisper foi para a GPU quando ela sobrou.** Ele estava na CPU de propósito,
para a GPU ficar com o Ollama. Ao vivo roda `large-v3-turbo` quantizado
(1.217 MiB, cabe junto do modelo de reescrita); num arquivo roda o `large-v3`
inteiro (3.905 MiB, a placa é toda dele).

**Front sem build.** Para buscar JSON e pintar número, um framework custa
`node_modules`, um build e um segundo processo sem entregar nada que 2.425
linhas não entreguem. São módulos ES nativos — o navegador resolve os imports.

**Testes de navegador não são luxo.** Os defeitos mais graves do projeto
passaram por 375 testes unitários verdes: o refresco de 15 s apagava o texto que
eu estava digitando, e um botão novo "não funcionava" porque o cache servia o
JavaScript de ontem. Nenhuma suíte que não abre um Chromium pegaria os dois.

---

## Sobre os meus dados

O que sai da máquina, sai porque eu decidi e está no `.env`:

| sai | fica |
|---|---|
| a transcrição da aula (fichamento) | o áudio, sempre |
| a vaga e o Perfil Mestre (currículo) | os embeddings e o índice inteiro |
| os trechos que a busca achou (resposta) | a reescrita dos blocos da aula |

A chave está na **camada paga** da API, onde o contrato diz que o conteúdo não é
usado para treinar modelos. Na camada gratuita seria o contrário — e isso é
decisão, não detalhe.

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
./scripts/copiloto.sh up          # docker + ollama + migration + worker + api
./scripts/copiloto.sh status      # o que está de pé, e o que não está
```

Painel em **http://localhost:8010**.

### Modelos locais

```bash
ollama pull phi4-mini    # classificar / extrair → JSON (caminho sem chave)
ollama pull gemma4:e4b   # redigir / resumir (vencedor do bake-off)
ollama pull llama3.1:8b  # compreender texto longo (queda do fichamento)
ollama pull bge-m3       # embeddings (1024 dimensões) — sempre local
```

### Modelo externo (opcional)

```bash
GEMINI_API_KEY=...                 # vazio = tudo local
```

Sem a chave o sistema funciona inteiro, com a qualidade que o modelo local dá.

### Transcrição (opcional)

```bash
pip install -e ".[transcricao]" && sudo apt install ffmpeg
pip install -e ".[transcricao-gpu]"   # cuBLAS + cuDNN, para o Whisper na GPU
```

Sem o extra `-gpu`, o Whisper cai para a CPU sozinho e avisa no log.

---

## Comandos

```bash
python scripts/ingerir.py            # indexa notas, PDFs e repos (incremental)
python scripts/perguntar.py "..."    # pergunta ao conhecimento, pelo terminal
python scripts/transcrever.py        # grava e transcreve, pelo terminal
python scripts/vaga.py --colar       # cola uma vaga do stdin
python scripts/avaliar_pergunta.py   # as 12 perguntas de avaliação
python scripts/bakeoff.py            # compara modelos às cegas
```

---

## Desenvolver

```bash
ruff check .          # lint
pytest                # suíte (precisa do Postgres de pé)
pytest -m ui          # navegador — pip install -e ".[ui]"
```

**Regra do projeto: 1 passo = 1 commit, com a suíte passando ao fim de cada um.**
Cada commit explica *por que*, não *o que* — o diff já diz o que mudou.

---

## Estado

Fases 0 a 6 concluídas: chão do projeto, conhecimento indexado, resposta
ancorada, worker de fundo, candidatura ponta a ponta, painel, e uso diário.
Depois delas: a Fase T (transcrição ao vivo) e a **fase híbrida**, que é a mais
recente.

Em aberto: envio de e-mail, **reranker na busca** (o `bge-reranker-v2-m3` já
está baixado), o destaque por seleção em vez de geração, e o fine-tune — que só
começa com ~300 pares de preferência curados.
