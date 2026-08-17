# Copiloto

> Assistente pessoal autônomo, **local-first**, 100% open source.
> Não é uma IA que sabe tudo. É uma IA que sabe **do meu mundo**.

Um modelo pequeno rodando na minha máquina (Ollama, 6 GB de VRAM), cercado de
contexto sobre um domínio restrito: meus projetos, meu jeito de escrever, minha
stack, meu mercado. Nenhuma API paga, nenhum dado meu saindo do computador.

> **Modelo pequeno com o contexto certo bate modelo grande sem contexto,
> na tarefa específica.**

```
FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 + pgvector · Alembic
Ollama (Qwen3 · Gemma · Llama 3.1 · bge-m3) · Redis + arq · faster-whisper
Front em HTML/CSS/JS puro, sem build
```

| | |
|---|---|
| **464 testes** | 447 de unidade/integração + 17 de navegador (Playwright) |
| **12.500 linhas** de Python | 105 arquivos, `ruff` limpo |
| **2.400 linhas** de front | sem `node_modules`, sem build, módulos ES nativos |
| **2.099 chunks** indexados | 291 documentos: notas, PDFs, repositórios |

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
cada 20 segundos (Whisper local, CPU, ~6,6× tempo real). Ao parar, o modelo
organiza e eu confirmo o nome.

O resultado não é a transcrição bem formatada — é uma nota de estudo:

```markdown
---
titulo: "Conectivos Lógicos em Lógica Proposicional"
tags: [logica-proposicional, conectivos, tabela-verdade]
duracao_min: 26
---

## Para lembrar
- **Uma tabela verdade tem 2^n linhas, onde n é o número de proposições.**
- **Sentença aberta, com incógnita, não é proposição.**

## Conteúdo
`⏱ 07:20`
### O Conectivo Bicondicional
...

## Relacionado
- [[logica-proposicional-p-e-q]]
```

**Onde a nota mora não é chute.** A pasta vem da vizinhança semântica: quais
notas do índice falam do mesmo assunto, e onde elas moram. Sem vizinho próximo
(distância > 0,44, medida), a nota vai para `_inbox` e a tela diz "assunto
novo" — o sistema só afirma o destino quando tem evidência dele.

### 4. Acompanha as candidaturas

O que foi enviado, o que respondeu, o que sumiu, e o que precisa de follow-up
hoje. Com métricas: funil, taxa de resposta, dias até responder, e — a mais
útil — **os requisitos que mais se repetem nas vagas e que eu não tenho**.
Trinta candidaturas viram uma lista de estudo derivada do que o mercado pediu.

---

## O princípio de arquitetura (não negociável)

> **O código decide o fluxo. O LLM faz tarefas pontuais e bem delimitadas.**

Máquinas de estado no Postgres, pipelines determinísticos em Python. O LLM entra
em nós isolados — classificar, extrair, reescrever, resumir — sempre com parser
tolerante a falha e retry.

Um 8B quantizado não é confiável para escolher qual ferramenta chamar, em que
ordem, e avaliar se deu certo. **Mas é ótimo para reescrever um parágrafo.**

Isso não é teoria: cada vez que o modelo errou, o conserto foi mover a decisão
para código.

| o modelo errou | o conserto |
|---|---|
| escreveu o currículo em 3ª pessoa | conversor de conjugação determinístico |
| citou tecnologia que eu não uso | lista branca do Perfil Mestre |
| ouviu "pigvector" | glossário de substituição |
| manteve "se inscreve no canal" | filtro de ruído por padrão fechado |
| escreveu `\rightarrow` dentro do JSON | parser que reconhece LaTeX pelo nome |

Cada erro vira uma regra que **nunca mais falha**. É por isso que os erros do
modelo são o combustível da arquitetura, não a falência dela.

---

## Decisões que valem explicação

**Um modelo por tarefa, não um generalista.** Em 6 GB o que decide não é caber,
é caber *junto*: `phi4-mini` + `bge-m3` ficam residentes e o caminho quente
nunca paga troca de modelo. Existe uma rota `compreender` que vai para o 8B,
usada onde ler 3.000 palavras e resumi-las decide o resultado — medido num
bake-off às cegas: 2 destaques contra 5, por 30 s a mais numa nota de 3 minutos.

**Todo LLM passa por um gateway.** Roteamento por tarefa, semáforo global de uma
inferência (duas concorrentes em 6 GB não ficam lentas — uma escorrega para a
RAM e o tempo explode uma ordem de grandeza), JSON com retry e reprompt, circuit
breaker por modelo, e observabilidade sempre. Foi a ausência disso no projeto
anterior que produziu quatro caminhos de chamada, dos quais só um media.

**Front sem build.** Para buscar JSON e pintar número, um framework custa
`node_modules`, um build e um segundo processo sem entregar nada que 2.400
linhas não entreguem. São módulos ES nativos — o navegador resolve os imports.

**Testes de navegador não são luxo.** Os defeitos mais graves do projeto
passaram por 375 testes unitários verdes: o refresco de 15 s apagava o texto que
eu estava digitando, e um botão novo "não funcionava" porque o cache servia o
JavaScript de ontem. Nenhuma suíte que não abre um Chromium pegaria os dois.

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

### Modelos

```bash
ollama pull phi4-mini    # classificar / extrair → JSON
ollama pull gemma4:e4b   # redigir / resumir (vencedor do bake-off)
ollama pull llama3.1:8b  # compreender texto longo
ollama pull bge-m3       # embeddings (1024 dimensões)
```

### Transcrição (opcional)

```bash
pip install -e ".[transcricao]" && sudo apt install ffmpeg
```

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

Em aberto: envio de e-mail, reranker na busca, e o fine-tune — que só começa
com ~300 pares de preferência curados, e que o uso normal do sistema coleta
sozinho.
