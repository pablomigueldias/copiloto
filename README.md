# Copiloto

> Assistente pessoal autônomo. **Local por padrão, externo por medida.**
> Não é uma IA que sabe tudo. É uma IA que sabe **do meu mundo**.

Modelos pequenos rodando na minha máquina (Ollama, 6 GB de VRAM), cercados de
contexto sobre um domínio restrito: meus estudos, meus projetos, meu jeito de
escrever, minha stack, minha prova de concurso.

> **Modelo pequeno com o contexto certo bate modelo grande sem contexto,
> na tarefa específica.**

Isso continua sendo o princípio — e ele tem um limite, que eu encontrei medindo.
Numa aula de lógica proposicional o `llama3.1:8b` escreveu *"a negação de P ou Q
é P e Q"*: uma Lei de Morgan sem as negações, falsa, na seção "Para lembrar" de
uma nota de estudo. **Quatro tarefas saíram da máquina por causa disso**, e o
resto ficou.

```
FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 + pgvector · Alembic
Ollama (Gemma · Phi-4 · Llama 3.1 · bge-m3) · Gemini API · Redis + arq
faster-whisper large-v3 na GPU · Next.js 16 + Tailwind 4 · Playwright
```

| | |
|---|---|
| **679 testes** | 661 de unidade/integração + 18 de navegador |
| **16.900 linhas** de Python | 98 arquivos, `ruff` limpo |
| **5.700 linhas** de front | `tsc` e `eslint` limpos |
| **2.429 chunks** indexados | 681 documentos: 464 PDFs, 172 notas, 33 repos |
| **505 chamadas** de LLM medidas | sucesso, falha e latência, uma linha cada |

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
máquina.

### 2. Transcreve aula e reunião, e organiza no meu vault

Aperto **gravar** no painel, assisto o vídeo, e o texto vai aparecendo na tela a
cada 20 segundos. Os blocos são reescritos **durante a aula**, na GPU que antes
ficava ociosa: ao parar sobra um bloco e o fichamento, ~75 s em vez de 3 min 30.

O resultado não é a transcrição bem formatada — é uma nota de estudo:

```markdown
---
titulo: "Fundamentos de SVM, Hiperplanos e Comparação com Redes Neurais"
tags: [machine-learning, algoritmos, redes-neurais-artificiais]
duracao_min: 24
---

## Para lembrar
- **A SVM busca o hiperplano de margem máxima; a rede neural busca o erro mínimo.**
- **Os vetores de suporte são as amostras mais próximas da fronteira de decisão.**

## Conteúdo
`⏱ 00:00`
### O que são Máquinas de Vetores de Suporte

## Relacionado
- [[logica-difusa-redes-neurais-generalizacao-e-algoritmos-bioinspirados]]
```

**O título não é chute, e a pasta também não.** Os dois vêm do vault: a busca
semântica traz as notas irmãs *com o trecho que casou*, e o modelo vê como as
vizinhas se chamam antes de nomear esta. Sem vizinho próximo (distância > 0,44,
medida), a nota vai para `_inbox` e a tela diz "assunto novo" — o sistema só
afirma o destino quando tem evidência dele.

**E o destaque é conferido contra a aula.** O que cita um número ou um
vocabulário que não aparece na transcrição sai marcado com ⚠, nunca apagado: o
modelo pode estar certo e o Whisper ter perdido a frase.

### 3. Devolve as questões de prova na hora certa

Tenho prova de Ciência de Dados no fim do ano. As questões vêm dos PDFs de
provas anteriores, com o gabarito conferido no gabarito oficial da banca — no
bloco do cargo correspondente, porque cadernos são compartilhados entre níveis e
gabaritos não.

Cada resposta vira **uma linha com a data e o acerto**, e é dela que sai a
próxima data:

| aconteceu | quando volta |
|---|---|
| acertei | 7 dias, e o intervalo cresce ×2,2 a cada acerto seguido (teto 180) |
| errei | 2 dias, e a sequência **zera** |
| adiei | 30 dias, e **não conta como acerto** |

Errar não recua um degrau, zera: quem errou depois de 35 dias não sabia há 35
dias, sabia há 7. O custo de rever cedo demais é um minuto; o de rever tarde
demais é errar na prova.

**A tela deixa tentar de novo antes de revelar, e só a primeira tentativa
reagenda.** Se as duas contassem igual, o intervalo cresceria sobre uma memória
que não existe — a questão sumiria por 35 dias por causa de um chute que deu
certo na repescagem.

**O gabarito não desce para o cliente.** Ele não viaja com a questão que estou
respondendo, nem dentro da string de origem. Não é segurança contra um atacante;
é honestidade comigo: se estivesse no DevTools, a diferença entre "eu sabia" e
"eu vi" sumiria do histórico — e é o histórico que agenda a revisão.

### 4. Adapta meu currículo a uma vaga, sem inventar nada

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
escada de quatro degraus de compactação tenta caber em uma.

### 5. Acompanha as candidaturas

O que foi enviado, o que respondeu, o que sumiu, e o que precisa de follow-up
hoje. Com métricas: funil, taxa de resposta, dias até responder, e — a mais
útil — **os requisitos que mais se repetem nas vagas e que eu não tenho**.
Trinta candidaturas viram uma lista de estudo derivada do que o mercado pediu.

### 6. Para e espera por mim

Todo texto que o modelo escreve em meu nome vai para uma **fila de aprovação**.
O agente observa e prepara sozinho; executar é decisão minha. Não existe rota de
enviar — ação aprovada fica marcada como aprovada, e quem manda é o executor.

E é aqui que nasce um dataset, sem esforço extra: o que eu aprovo vira exemplo
de estilo (few-shot); o que eu **edito antes de aprovar** vira par de
preferência para fine-tune. Cem revisões viram cem pares, produzidos por uso
normal — não por sessão de rotulagem.

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
O roteamento é por tarefa **e por agente** — é o que separa a reescrita do bloco
de aula do currículo, que são a mesma tarefa `redigir` e têm exigências opostas.
Fica local o embedding: 2.429 chunks indexados, migração de dimensão cara, zero
evidência de que ele seja o gargalo.

**Todo LLM passa por um gateway.** Semáforo para a inferência local (duas
concorrentes em 6 GB não ficam lentas — uma escorrega para a RAM e o tempo
explode uma ordem de grandeza), JSON com retry e reprompt, circuit breaker por
modelo, **queda para o modelo local quando a API não responde**, e
observabilidade sempre: um registro por destino, com latência. Foi essa tabela
que mostrou por que uma nota saiu pela metade — quatro blocos com latência de
exatamente 180 014 ms, o timeout.

**Sem chave, tudo roda local.** `GEMINI_API_KEY` vazio faz o roteamento externo
ser ignorado inteiro. É o que faz a suíte e uma máquina sem internet passarem
sem tratamento especial — e é testado.

**O Whisper foi para a GPU quando ela sobrou.** Ao vivo roda `large-v3-turbo`
quantizado (1.217 MiB, cabe junto do modelo de reescrita); num arquivo roda o
`large-v3` inteiro (3.905 MiB, a placa é toda dele).

**O front é Next.js porque o design pediu.** Ele foi HTML+CSS+JS puro por seis
fases, e a troca não foi pela stack: foi por um design system de oito telas com
escala tipográfica própria, rampas geradas em OKLCH e estados de revisão.
Reproduzir aquilo à mão em CSS seria escrever um framework de componentes sem
chamá-lo assim. O front fala com a API pela **mesma origem** — a autenticação é
cookie httpOnly, e cookie cross-origin custa `SameSite=None`, que custa HTTPS,
que custa certificado numa máquina local.

**Testes de navegador não são luxo.** Os defeitos mais graves do projeto
passaram por 375 testes unitários verdes: o refresco de 15 s apagava o texto que
eu estava digitando na fila, e um botão novo "não funcionava" porque o cache
servia o JavaScript de ontem. Nenhuma suíte que não abre um Chromium pegaria os
dois.

---

## Sobre os meus dados

O que sai da máquina, sai porque eu decidi e está no `.env`:

| sai | fica |
|---|---|
| a transcrição da aula (fichamento e reescrita) | o áudio, sempre |
| a vaga e o Perfil Mestre (currículo) | os embeddings e o índice inteiro |
| os trechos que a busca achou (resposta) | e-mail frio e mensagem de recrutador |

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
cd web && npm install && cd ..    # uma vez só
./scripts/copiloto.sh up          # docker, ollama, migration, worker, api e front
```

Painel em **http://localhost:3000** — a API fica na 8010, e a raiz dela
redireciona para cá.

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
python scripts/ingerir.py                        # indexa notas, PDFs e repos
python scripts/perguntar.py "..."                # pergunta pelo terminal
python scripts/transcrever.py                    # grava e transcreve
python scripts/reprocessar_nota.py "<nota>"      # passa a nota pelo pipeline atual
python scripts/importar_questoes.py "<json>"     # acervo de questões (idempotente)
python scripts/avaliar_pergunta.py               # as 12 perguntas de avaliação
python scripts/bakeoff.py                        # compara modelos às cegas
```

---

## Desenvolver

```bash
ruff check .                      # lint do Python
pytest                            # suíte (precisa do Postgres de pé)
pytest -m ui                      # navegador — pip install -e ".[ui]"
cd web && npx tsc --noEmit && npm run lint
```

**Regra do projeto: 1 passo = 1 commit, com a suíte passando ao fim de cada um.**
Cada commit explica *por que*, não *o que* — o diff já diz o que mudou.
