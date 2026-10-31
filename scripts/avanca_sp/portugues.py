"""Língua Portuguesa — o bloco comum das provas não-TI de 07/10/2026.

Fora daqui, de propósito: formação de palavras e elementos mórficos (Embu-Guaçu
q7, Itupeva q10, ITUPREV q9, Jaguariúna q5, São Miguel Arcanjo q6) — o
programa de Português do edital não cobra.
"""
from bloco_comum import Q
from textos_bloco_comum import (
    EMBU_2022,
    EMBU_2022_FONTE,
    ITUPEVA_2024,
    ITUPEVA_2024_FONTE,
    ITUPREV_2024,
    ITUPREV_2024_FONTE,
    JAGUARIUNA_2023,
    JAGUARIUNA_2023_FONTE,
    SAAE_2023,
    SAAE_2023_FONTE,
    SMA_2023,
    SMA_2023_FONTE,
)

EMBU = dict(texto=EMBU_2022, fonte_texto=EMBU_2022_FONTE)
ITUPEVA = dict(texto=ITUPEVA_2024, fonte_texto=ITUPEVA_2024_FONTE)
ITUPREV = dict(texto=ITUPREV_2024, fonte_texto=ITUPREV_2024_FONTE)
JAG = dict(texto=JAGUARIUNA_2023, fonte_texto=JAGUARIUNA_2023_FONTE)
SAAE = dict(texto=SAAE_2023, fonte_texto=SAAE_2023_FONTE)
SMA = dict(texto=SMA_2023, fonte_texto=SMA_2023_FONTE)

ICEN = "Interpretação: ideia central, tese e finalidade"
IEXP = "Interpretação: informação explícita no texto"
IINF = "Interpretação: inferência e sentido de trecho"

# ── Embu-Guaçu 2022 ──────────────────────────────────────────────────────

Q("embu", 1, "interpretacao-de-texto", ICEN, "C",
  "Em relação à temática do texto:",
  ["Há apenas o lado negativo abordado.", "Há somente o lado positivo em cotejo.",
   "Há os lados positivo e negativo apresentados.", "Há uma abordagem romantizada.",
   "Há um tratamento, totalmente, antiético."],
  "O texto ouve os dois lados: letra {G}.\n\n"
  "| Lado | Quem fala |\n|---|---|\n| negativo | Munayyer (“insensível e vergonhoso”), Mahdi, Keret, a ‘ferida dos árabes’ |\n"
  "| positivo | Avraham (“ajuda o branding”, ensina a nova geração), ‘vitória de relações públicas’ |\n\n"
  "Reportagem que cita críticos e defensores apresenta os dois lados. Alternativas com 'apenas', 'somente' e 'totalmente' radicalizam e caem.",
  dificuldade=1, **EMBU)

Q("embu", 2, "interpretacao-de-texto", IEXP, "D",
  "Segundo o texto, pode-se afirmar que:",
  ["a referência à “ferida dos árabes” só aparece, claramente, no decorrer do 9º parágrafo, justificando, plenamente, o título apresentado.",
   "a fala de especialistas em questões internacionais é categórica quando afirmam que é séria a possibilidade do surgimento de um conflito entre Oriente e Ocidente, na contemporaneidade.",
   "os críticos, mesmo considerando delicado retratar uma heroína israelense, no momento atual, reconhecem que os estúdios Marvel estão cientes da história e da experiência palestina atuais.",
   "a personagem Sabra talvez não se adeque aos tempos atuais, pois não se pode manter uma visão simplista dela hoje, como foi no tempo de suas primeiras aparições.",
   "para alguns críticos, trazer essa personagem israelense pode ser positivo, já que ela seria retratada como uma espécie de salvadora de seu povo e do mundo."],
  "Paráfrase da fala de Etgar Keret: letra {G}.\n\n"
  "O texto: Sabra 'pode não ser uma super-heroína para nossos tempos', foi criada com uma 'história simples e clara' e 'agora é difícil manter esse tipo de ícone de simplicidade'.\n\n"
  "| Alternativa | Por que cai |\n|---|---|\n| A | a ferida aparece no título e é explicada no parágrafo da Shatila — não no 9º |\n"
  "| B | ninguém fala em conflito Oriente × Ocidente |\n| C | o contrário: chamam a Marvel de 'abjetamente ignorante' sobre a região |\n| E | não são os críticos que veem lado positivo, e 'salvadora do mundo' não está no texto |",
  dificuldade=2, **EMBU)

Q("embu", 3, "interpretacao-de-texto", IINF, "A",
  "Sobre introduzir uma personagem árabe no novo filme da Marvel, Yousef Munayyer apresenta uma opinião:",
  ["Radical.", "Neutra.", "Confiante.", "Simplista.", "Impessoal."],
  "Pelas palavras dele: letra {G}.\n\n"
  "Munayyer chama o conceito de 'insensível e vergonhoso' e diz que é 'difícil não concluir que as pessoas da Marvel são abjetamente ignorantes'. É uma condenação sem meio-termo.\n\n"
  "Neutra e impessoal são o oposto; confiante não combina com a crítica.\n\n"
  "(O enunciado da banca fala em 'personagem árabe', mas Sabra é israelense — o que se pergunta é o tom da opinião, e ele não muda.)",
  dificuldade=1, **EMBU)

Q("embu", 4, "pontuacao", "Dois-pontos, travessão e outros sinais", "A",
  "O emprego dos parênteses no excerto “Esta Sabra foi criada antes de duas intifadas (revoltas palestinas), (...)” (10º parágrafo), justifica-se gramaticalmente, pois:",
  ["Destacam uma explicação.", "Indicam um juízo de valor.", "Isolam uma citação.", "Demarcam um exemplo.", "Sugerem uma ironia."],
  "'Revoltas palestinas' explica o que são intifadas: letra {G}.\n\n"
  "| Sinal | Uso típico |\n|---|---|\n| parênteses | explicação, comentário acessório, sigla |\n| aspas | citação, ironia, estrangeirismo |\n"
  "| travessão | fala, intercalação enfática |\n| dois-pontos | enumeração, explicação, citação |\n\n"
  "Teste: o termo entre parênteses responde 'o que é isso?' sobre a palavra anterior → explicação.", dificuldade=1)

Q("embu", 5, "concordancia", "Concordância verbal", "E",
  "Tendo em vista o verbo destacado na passagem “(...) que foi introduzida pela primeira vez nos quadrinhos HÁ mais de 40 anos”, (...)” (8º parágrafo), assinale o comentário correto sobre sua concordância:",
  ["A concordância está correta no singular, visto que o termo ao qual ele se refere, “primeira vez”, está no singular.",
   "A concordância deveria se realizar no plural, uma vez que o termo com valor temporal está no plural.",
   "A concordância está inadequada, já que o termo ao qual ele se refere, “quadrinhos”, está no plural.",
   "A concordância pode ser facultativa, ou seja, tanto no singular como no plural.",
   "A concordância está correta no singular, pois se trata de verbo impessoal."],
  "Haver indicando tempo decorrido é impessoal: letra {G}.\n\n"
  "Verbo impessoal não tem sujeito, então não tem com quem concordar — fica sempre na 3ª pessoa do singular: há 40 anos, havia muitos dias, faz dez anos.\n\n"
  "| Verbo impessoal | Exemplo |\n|---|---|\n| haver = existir | Há problemas. Havia alunos. |\n| haver / fazer = tempo | Há 40 anos. Faz dez anos. |\n| fenômeno da natureza | Choveu muito. |\n\n"
  "'Mais de 40 anos' é complemento (objeto direto), não sujeito — por isso não puxa o plural.", dificuldade=2)

Q("embu", 6, "coesao-conectivos", "Conectivos: valor semântico", "B",
  "A conjunção destacada no fragmento “EMBORA Sabra não seja a primeira vez, (...)” (14º parágrafo), de acordo com seu sentido no contexto, poderia ser substituída pelos conectivos abaixo, com EXCEÇÃO da alternativa:",
  ["Posto que.", "Já que.", "Mesmo que.", "Ainda que.", "Apesar de que."],
  "Embora é concessiva; 'já que' é causal: letra {G}.\n\n"
  "| Valor | Conectivos |\n|---|---|\n| concessão | embora, ainda que, mesmo que, posto que, conquanto, apesar de que, se bem que |\n"
  "| causa | porque, já que, visto que, uma vez que, como (no início) |\n\n"
  "Pegadinha clássica: 'posto que' é CONCESSIVO na norma-padrão (= embora), não causal, apesar do uso corrente.", dificuldade=2)

Q("embu", 8, "colocacao-pronominal", "Colocação pronominal (próclise, ênclise e mesóclise)", "C",
  "Quanto à colocação dos pronomes pessoais oblíquos átonos, julgue os itens, abaixo, e assinale o que está correto:",
  ["Te entreguei os livros emprestados.", "Não referi-me ao professor.", "Quando a vi, abri um sorriso largo.",
   "Ninguém dirigiu-me a palavra ali.", "Não sei o que responderam-lhe ontem."],
  "Conjunção subordinativa atrai o pronome: letra {G}.\n\n"
  "| Frase | Problema | Correção |\n|---|---|---|\n| Te entreguei | pronome no início da frase | Entreguei-te |\n"
  "| Não referi-me | 'não' atrai | Não me referi |\n| Ninguém dirigiu-me | pronome indefinido atrai | Ninguém me dirigiu |\n| o que responderam-lhe | pronome relativo/interrogativo atrai | o que lhe responderam |\n\n"
  "Palavras atrativas (pedem próclise): negação, advérbio, pronome relativo, indefinido e interrogativo, conjunção subordinativa.", dificuldade=1)

Q("embu", 9, "ortografia-acentuacao", "Hífen e prefixos", "B",
  "Assinale a alternativa com vocábulo, corretamente, grafado:",
  ["Co-habitante.", "Inter-regional.", "Super-intressante.", "Auto-escola.", "Infra-estrutura."],
  "Prefixo terminado na mesma letra que começa a palavra seguinte: hífen. Letra {G}.\n\n"
  "| Regra (Acordo de 1990) | Exemplos |\n|---|---|\n| letras iguais → hífen | inter-regional, micro-ondas, anti-inflamatório |\n"
  "| letras diferentes → junta | autoescola, infraestrutura, superinteressante |\n| prefixo + h → hífen | super-homem, anti-higiênico |\n"
  "| co- junta sempre | coabitante, coerdeiro, cooperar |\n| prefixo vogal + r/s → dobra | antirrábico, contrassenso |\n\n"
  "Superinteressante, além do hífen indevido, ainda veio com 'intressante' — erro duplo.", dificuldade=2)

Q("embu", 10, "redacao-oficial", "Redação oficial: atributos (clareza, concisão, impessoalidade)", "E",
  "Quando se trata de comunicações oficiais, existe a necessidade de que sejam uniformes, pois há sempre um único comunicador (o Serviço Público) e o receptor dessas comunicações ou é o próprio Serviço Público (no caso de expedientes dirigidos por um órgão a outro) ou o conjunto dos cidadãos ou instituições, tratados de forma homogênea (o público). Essa assertiva refere-se ao princípio da:",
  ["Legalidade.", "Moralidade.", "Eficiência.", "Seriedade.", "Impessoalidade."],
  "Trecho do Manual de Redação da Presidência sobre impessoalidade: letra {G}.\n\n"
  "Comunicador único (o Serviço Público, não a pessoa do servidor) e destinatário tratado de forma homogênea = impessoalidade.\n\n"
  "| Atributo da redação oficial | Ideia |\n|---|---|\n| clareza | entendimento imediato |\n| concisão | sem palavra inútil |\n| objetividade | ir direto ao ponto |\n"
  "| formalidade e padronização | norma-padrão e modelos fixos |\n| impessoalidade | quem fala é o órgão; sem impressão pessoal |", dificuldade=1)

# ── Itupeva 2024 ─────────────────────────────────────────────────────────

Q("itupeva", 1, "interpretacao-de-texto", IINF, "E",
  "Analise as asserções abaixo, destaque a que condiz com a perspectiva apresentada pelo autor.",
  ["A evolução da humanidade decorre do papel assumido pelo ser humano.",
   "A resiliência é considerada um traço social de personalidade.",
   "Para se tornar um líder, é necessário que o indivíduo possua todos os traços de liderança.",
   "Um traço é um atributo trivial da personalidade.",
   "Os resultados alcançados pelo líder dependerão de aspectos de ordem intrínseca e extrínseca."],
  "Traços internos (inteligência, autoconfiança) e externos (aparência, habilidades interpessoais): letra {G}.\n\n"
  "| Alternativa | Por que cai |\n|---|---|\n| A | o texto atribui o progresso a ALGUNS homens (teoria do 'grande homem'), não ao ser humano em geral |\n"
  "| B | resiliência não está na lista de traços sociais (cooperação, habilidades interpessoais, administrativa) |\n"
  "| C | o texto não exige TODOS os traços |\n| D | o texto diz 'característica distintiva', o contrário de trivial |\n\n"
  "Em 'segundo o autor', elimine o que contradiz ou extrapola o texto e fique com a que sobra.", dificuldade=3, **ITUPEVA)

Q("itupeva", 2, "sentido-das-palavras", "Sinônimos, antônimos e reescrita com mesmo sentido", "E",
  "Considere o trecho do texto: “Em resumo, um líder deve inspirar confiança, ser inteligente, perceptivo e decisivo para ter condições de liderar com sucesso.” Assinale a alternativa em que as trocas dos termos foram responsáveis por alterar o sentido proposto pelo autor do texto.",
  ["Um líder deve inspirar segurança, ser sagaz, cognoscível e essencial para ter condições de liderar com sucesso.",
   "Um líder deve inspirar convicção, ser astuto, acessível e substancial para ter condições de liderar com sucesso.",
   "Um líder deve inspirar firmeza, ser capaz, nítido e basilar para ter condições de liderar com sucesso.",
   "Um líder deve inspirar resolução, ser arguto, evidente e primordial para ter condições de liderar com sucesso.",
   "Um líder deve inspirar arrepsia, ser perspicaz, intelígível e precípuo para ter condições de liderar com sucesso."],
  "Arrepsia = indecisão, hesitação — o contrário de confiança: letra {G}.\n\n"
  "Nas outras, a troca de 'confiança' mantém o campo: segurança, convicção, firmeza, resolução.\n\n"
  "Vocabulário que a questão cobra:\n\n| Palavra | Sentido |\n|---|---|\n| sagaz, astuto, arguto, perspicaz | inteligente, esperto |\n| precípuo | principal |\n| basilar | fundamental |\n| arrepsia | hesitação, irresolução |\n\n"
  "(As alternativas também trocam 'perceptivo' e 'decisivo' por palavras que não são sinônimas — a banca concentrou o erro decisivo em 'arrepsia'.)",
  dificuldade=3)

Q("itupeva", 3, "figuras-de-linguagem", "Figuras de linguagem", "A",
  "Qual a figura de linguagem que aparece na última frase do texto anterior?",
  ["Elipse", "Aliteração", "Metáfora", "Antítese", "Paradoxo"],
  "'Prefere delegar.' — o sujeito (o líder) está omitido: letra {G}.\n\n"
  "Elipse é a omissão de um termo que o contexto deixa claro. Quando o termo omitido já apareceu antes, alguns gramáticos chamam de zeugma.\n\n"
  "| Figura | O que faz |\n|---|---|\n| elipse | omite termo subentendido |\n| aliteração | repete som consonantal |\n| metáfora | comparação implícita |\n| antítese | ideias opostas |\n| paradoxo | ideias opostas que se afirmam juntas (contradição aparente) |",
  dificuldade=2, **ITUPEVA)

Q("itupeva", 4, "pontuacao", "Vírgula", "B",
  "Analise as alternativas abaixo, destaque a que traz um erro de pontuação.",
  ["Paula, muito generosa, compartilhou seu lanche.", "Bruna era desorganizada; seu irmão organizado.",
   "Nas férias, visitamos o Cristo Redentor, no Rio de Janeiro; a Praça da Liberdade, em Belo Horizonte.",
   "Vamos ao... Que explosão foi essa?", "Essas teorias foram influenciadas pela teoria do “grande homem”."],
  "Falta a vírgula da elipse do verbo: letra {G}.\n\n"
  "Correto: 'Bruna era desorganizada; seu irmão, organizado.' — a vírgula marca o lugar do verbo 'era', omitido.\n\n"
  "| Alternativa | Por que está certa |\n|---|---|\n| A | vírgulas isolam o aposto/explicativo 'muito generosa' |\n| C | ponto e vírgula separa itens que já têm vírgula dentro |\n"
  "| D | reticências marcam interrupção da fala |\n| E | sem pontuação a corrigir |", dificuldade=2)

Q("itupeva", 5, "ortografia-acentuacao", "Ortografia: grafia das palavras", "C",
  "Assinale a alternativa que não possui erros ortográficos.",
  ["Aninha estava anciosa, pois o próximo final de semana seria sua formatura.",
   "No Brasil, não há leis de subcídio fiscal que realmente sejam eficazes.",
   "Para garantir a preservação ambiental, faz-se necessário que as licenças ambientais sejam retiradas em tempo hábil.",
   "Depois de um ano de trabalho árduo, mereço descanço.",
   "Na sala de aula, Pedrinho não parava de encomodar seus colegas."],
  "Letra {G}, a única sem erro.\n\n"
  "| Errado | Certo |\n|---|---|\n| anciosa | ansiosa (de ânsia) |\n| subcídio | subsídio |\n| descanço | descanso (de descansar) |\n| encomodar | incomodar |\n\n"
  "Atalho: a palavra derivada mantém a grafia da primitiva — ânsia → ansioso; descansar → descanso.", dificuldade=1)

Q("itupeva", 6, "concordancia", "Concordância nominal", "A",
  "Não há erro de concordância em qual das alternativas abaixo?",
  ["Há bastantes livros na estante que ainda não foram lidos.", "Tratavam-se de empregados terceirizados.",
   "É proibida entrada de menores desacompanhados.", "Meu filho só consegue dormir a partir das zero horas da manhã.",
   "Poderá ainda ocorrer desavenças entre pais e filhos."],
  "'Bastantes' antes de substantivo é adjetivo (= muitos) e varia: letra {G}.\n\n"
  "| Frase | Erro | Correção |\n|---|---|---|\n| Tratavam-se de | 'tratar-se de' é impessoal (sujeito indeterminado) | Tratava-se de |\n"
  "| É proibida entrada | sem artigo, fica invariável | É proibido entrada / É proibida A entrada |\n| das zero horas | zero pede singular | da zero hora |\n| Poderá ocorrer desavenças | o sujeito é 'desavenças' | Poderão ocorrer |\n\n"
  "Teste do 'bastante': troque por 'muitos'. Se couber, varia (bastantes livros); se couber 'muito' (bastante cansados), não varia.", dificuldade=2)

Q("itupeva", 7, "regencia", "Regência nominal", "E",
  "Assinale a alternativa que não possui nenhum erro de regência.",
  ["A devoção à Deus é um exercício diário do cristão.", "Estou alheia sobre tudo.",
   "Não tenho dúvidas a cerca da sua inocência.", "Os alunos estão desgostosos por suas notas.",
   "Meu filho não tem nenhuma inclinação para o atletismo."],
  "Inclinação para/a: letra {G}.\n\n"
  "| Frase | Erro | Correção |\n|---|---|---|\n| devoção à Deus | Deus não aceita artigo → sem crase | devoção a Deus |\n| alheia sobre | alheio pede 'a' | alheia a tudo |\n"
  "| a cerca da | 'a cerca' é uma cerca; o certo é a locução 'acerca de' (= sobre) | acerca da sua inocência |\n| desgostosos por | desgostoso pede 'com' / 'de' | desgostosos com as notas |", dificuldade=2)

Q("itupeva", 8, "colocacao-pronominal", "Colocação pronominal (próclise, ênclise e mesóclise)", "C",
  "Analise as alternativas abaixo, marque a que possui um erro de colocação pronominal.",
  ["Diga-me como foram as festas de final de ano.", "Estava fazendo-se de desentendida para evitar problemas com o marido.",
   "Me sigam, se quiserem conhecer o mundo.", "Quero encontrar-te mais tarde.", "Suas desculpas não me convenceram."],
  "Não se inicia frase com pronome oblíquo átono: letra {G}.\n\nCorreto: 'Sigam-me, se quiserem conhecer o mundo.'\n\n"
  "| Alternativa | Por que está certa |\n|---|---|\n| A | imperativo no início → ênclise |\n| B | locução com gerúndio, sem palavra atrativa → ênclise ao gerúndio |\n"
  "| D | locução com infinitivo → ênclise ao infinitivo |\n| E | 'não' atrai → próclise |", dificuldade=1)

Q("itupeva", 9, "crase", "Crase", "C",
  "Assinale a alternativa que a crase foi empregada corretamente.",
  ["Fique à distância de pessoas problemáticas.", "O pescador foi à terra para trocar peixes por redes.",
   "Isso não se refere às alunas problemáticas.", "Cheguei à casa tarde, pois todos faltaram ao trabalho.",
   "Fui à São Paulo no último final de semana."],
  "Referir-se A + AS alunas = às: letra {G}.\n\n"
  "| Frase | Por que NÃO tem crase |\n|---|---|\n| à distância | distância indeterminada não leva artigo (crase só com distância especificada: à distância de 10 m) |\n"
  "| à terra | 'terra' oposta a bordo/mar não leva artigo |\n| à casa | 'casa' = o próprio lar, sem determinante, não leva artigo |\n| à São Paulo | 'vou a São Paulo, volto DE São Paulo' → sem artigo |\n\n"
  "Teste: troque por masculino. 'Refere-se aos alunos' → AO → crase. 'Fui a Santos' — volto de Santos, não 'da' → sem crase.", dificuldade=2)

# ── ITUPREV 2024 ─────────────────────────────────────────────────────────

Q("ituprev", 1, "interpretacao-de-texto", IEXP, "B",
  "De acordo com a reportagem, o aumento do número de músicas produzidas em 2024 se deve, principalmente, ao fato de que:",
  ["As gravadoras baratearam o processo de produção de álbuns para novos artistas.",
   "Com o advento da tecnologia, há menos dificuldades para se produzir e distribuir música atualmente.",
   "Todos os artistas da atualidade são independentes, o que facilita os processos de produção e distribuição de música.",
   "Não há custos na produção musical para artistas independentes que se utilizam das plataformas de streaming para divulgar o seu trabalho.",
   "As plataformas de streaming impulsionam mais do que as gravadoras o trabalho de artistas independentes."],
  "Primeiro parágrafo: letra {G}.\n\n"
  "'Desde que a última fase evolutiva dos aparelhos de áudio aconteceu [...] existem poucos limites [...]. Por isso, o boom da música não é surpresa: hoje, há menos dificuldade em escrever, criar, gravar e publicar'.\n\n"
  "| Alternativa | Por que cai |\n|---|---|\n| C | 'todos' — e o texto compara independentes com artistas de gravadora |\n| D | o texto diz que os custos são TRANSFERIDOS para os músicos |\n| E | o texto diz que destacar-se no streaming é 'incrivelmente complexo' |",
  dificuldade=1, **ITUPREV)

Q("ituprev", 2, "coesao-conectivos", "Referência e retomada (anáfora e catáfora)", "B",
  "Analise o papel dos pronomes que ocorrem nos seguintes excertos, retirados do texto:\n\nI. “A investigação indicou que ESSE número só vai crescer”\nII. “E existe público que consome ESSE conteúdo”\nIII. “ELES não permanecem tanto tempo no topo das paradas”\n\nSobre esses pronomes em destaque é correto afirmar que:",
  ["Desempenham papéis de coesão textual sequencial, à medida que fazem o texto progredir de parágrafo a parágrafo.",
   "Desempenham papéis de referenciação anafórica, porque retomam elementos já mencionados no texto.",
   "Desempenham papéis de referenciação catafórica, porque introduzem novos elementos no texto.",
   "Não desempenham papéis de referenciação, porque seus antecedentes são implícitos.",
   "Não desempenham papéis de coesão textual, porque não auxiliam na referenciação do texto."],
  "Os três apontam para trás: letra {G}.\n\n"
  "| Pronome | Retoma |\n|---|---|\n| esse número | as 100.000 faixas por dia |\n| esse conteúdo | a música publicada pelo celular |\n| eles | os grandes artistas |\n\n"
  "| Tipo | Direção |\n|---|---|\n| anáfora | retoma o que veio ANTES |\n| catáfora | anuncia o que vem DEPOIS (ex.: 'Só quero isto: paz.') |\n\n"
  "Dica: 'esse/essa' costuma retomar (anáfora); 'este/isto' pode anunciar (catáfora).", dificuldade=1, **ITUPREV)

Q("ituprev", 3, "coesao-conectivos", "Conectivos: valor semântico", "C",
  "Analise o sentido da oração introduzida pela locução “por mais que” no seguinte excerto: “Por mais que plataformas de streaming ofereçam aos artistas pequenos a chance de se promover e disponibilizar suas músicas, “conseguir destacar a música de alguém entre as outras 99.999 faixas enviadas naquele dia é incrivelmente complexo” [...]”.\n\nEssa oração é reescrita adequadamente, preservando seu sentido original, apenas em:",
  ["Contanto que plataformas de streaming ofereçam aos artistas pequenos a chance de se promover e disponibilizar suas músicas [...].",
   "Ao passo que plataformas de streaming ofereçam aos artistas pequenos a chance de se promover e disponibilizar suas músicas [...].",
   "Embora plataformas de streaming ofereçam aos artistas pequenos a chance de se promover e disponibilizar suas músicas [...].",
   "Desde que plataformas de streaming ofereçam aos artistas pequenos a chance de se promover e disponibilizar suas músicas [...].",
   "Visto que plataformas de streaming ofereçam aos artistas pequenos a chance de se promover e disponibilizar suas músicas [...]."],
  "'Por mais que' é concessiva = embora: letra {G}.\n\n"
  "| Conectivo | Valor |\n|---|---|\n| por mais que, embora, ainda que, mesmo que | concessão |\n| contanto que, desde que (+ subjuntivo) | condição |\n"
  "| ao passo que | proporção / contraste |\n| visto que | causa |\n\n"
  "Concessão: admite um fato (o streaming dá a chance) que não impede o outro (destacar-se é difícil).", dificuldade=1)

Q("ituprev", 4, "colocacao-pronominal", "Colocação pronominal (próclise, ênclise e mesóclise)", "B",
  "A regra gramatical que determina a colocação pronominal proclítica em “Enquanto as empresas de tecnologia e as plataformas de conteúdo SE beneficiam dessa abundância de música barata [...]” é a mesma que se aplica ao contexto em:",
  ["Ele não me chamou para ir ao bar no fim de semana.", "A moça estava desconcertada, porque seu noivo a abandonou.",
   "Ela talvez o ajudasse sem que ele pedisse.", "Ninguém se conformava com aquela situação.",
   "Só se vê o pássaro na varanda do apartamento."],
  "'Enquanto' é conjunção subordinativa e atrai o pronome; 'porque' também: letra {G}.\n\n"
  "| Alternativa | O que atrai |\n|---|---|\n| A | advérbio de negação 'não' |\n| B | conjunção subordinativa 'porque' ✔ |\n| C | advérbio 'talvez' |\n| D | pronome indefinido 'ninguém' |\n| E | palavra denotativa 'só' |\n\n"
  "Todas têm próclise; a questão pede a MESMA causa da próclise.", dificuldade=2)

Q("ituprev", 5, "pontuacao", "Vírgula", "D",
  "As vírgulas empregadas no excerto “Um relatório divulgado pela MiDiA, uma empresa de análise de dados, mostrou que cerca de 75.9 milhões de pessoas se consideram criadores de música” isolam um termo de mesmo valor sintático daquele isolado pela pontuação em:",
  ["A massa do pão crescerá, desde que a deixe descansar por uma hora.", "Foram deixados à porta da igreja sapatos velhos, sujos.",
   "As passagens áreas estão muito, muito caras.", "A menina, filha mais velha do casal, se esforçava para manter a seriedade.",
   "Desista disso, meu amigo, pois não lhe fará bem a longo prazo."],
  "'uma empresa de análise de dados' é aposto explicativo de MiDiA; 'filha mais velha do casal' é aposto de 'a menina'. Letra {G}.\n\n"
  "| Alternativa | O que a vírgula isola |\n|---|---|\n| A | oração subordinada adverbial condicional |\n| B | adjetivos em sequência |\n| C | repetição enfática |\n| D | aposto explicativo ✔ |\n| E | vocativo (chamamento) |\n\n"
  "Aposto × vocativo: aposto explica um termo da oração; vocativo chama o interlocutor e não faz parte da oração.", dificuldade=2)

Q("ituprev", 6, "classes-de-palavras", "Advérbio: classificação e circunstâncias", "D",
  "O valor que melhor descreve o sentido expresso pelo advérbio “já”, em “a facilidade que existia em 1989 já não existe mais”, é:",
  ["adição.", "possibilidade.", "negação.", "tempo.", "afirmação."],
  "'Já não existe mais' = a partir de agora não existe: letra {G}.\n\n"
  "O 'já' marca a mudança no tempo (antes existia, hoje não). A negação está no 'não', não no 'já'.\n\n"
  "| Advérbio | Valor comum |\n|---|---|\n| já, ainda, logo, agora | tempo |\n| talvez, provavelmente | dúvida/possibilidade |\n| sim, certamente | afirmação |\n| não, nunca | negação |", dificuldade=1)

Q("ituprev", 7, "classes-de-palavras", "Morfologia: classificar palavras no contexto", "C",
  "Em todas as sentenças a seguir, que ocorrem no texto, os termos em destaque são preposições, exceto em:",
  ["“Mais músicas foram lançadas por dia EM 2024 do que em todo o ano de 1989”.", "“E não vai parar POR aí”.",
   "“Os artistas ganham CERCA de $0,003 e $0,005 dólares por reprodução no Spotify”.",
   "“artistas independentes lançaram 9,5 milhões de faixas, CONTRA 1,2 milhão de artistas de gravadoras”.",
   "“De acordo COM o Spotify, 80% dos artistas têm menos de 50 ouvintes mensais”."],
  "'Cerca' é advérbio (cerca de = aproximadamente): letra {G}.\n\n"
  "Em, por, contra e com são preposições — ligam termos. 'Cerca' modifica o numeral, indicando aproximação; 'de' é que é a preposição da locução.\n\n"
  "Preposições essenciais: a, ante, após, até, com, contra, de, desde, em, entre, para, perante, por, sem, sob, sobre, trás.\n\n"
  "Não confundir: 'acerca de' (= sobre) e 'há cerca de' (= existe aproximadamente / faz aproximadamente).", dificuldade=2)

Q("ituprev", 8, "analise-sintatica", "Sujeito: tipos e oração sem sujeito", "E",
  "A única sentença em que o verbo não é impessoal se apresenta em:",
  ["Choveu a manhã inteira naquele dia.", "Já passava das nove da noite.", "Aqui não faz muito calor na primavera.",
   "Havia inúmeros problemas sem resolução.", "Evitava perguntas, mesmo com dúvidas em relação à matéria."],
  "'Evitava' tem sujeito oculto (ele/ela/eu evitava): letra {G}.\n\n"
  "| Frase | Por que é impessoal |\n|---|---|\n| Choveu | fenômeno da natureza |\n| passava das nove | tempo/hora com 'passar' |\n| faz calor | fenômeno atmosférico com 'fazer' |\n| Havia problemas | haver = existir |\n\n"
  "Teste: pergunte 'quem?' ao verbo. 'Quem evitava?' — alguém. 'Quem choveu?' — ninguém.", dificuldade=1)

Q("ituprev", 10, "concordancia", "Concordância verbal", "D",
  "A concordância verbal está incorreta apenas em:",
  ["Não só a igreja como também o príncipe pagariam impostos na província.",
   "A alegria, a satisfação, a motivação, tudo me levou à decisão de deixar o país.",
   "A maior parte dos políticos estava envolvida com corrupção.",
   "Nem eu nem ele o convidou para o jantar.", "Metade dos alunos tirou notas abaixo de seis."],
  "Sujeito composto com 'nem… nem' e pessoas diferentes: prevalece a 1ª pessoa. Letra {G}.\n\nCorreto: 'Nem eu nem ele o convidamos.'\n\n"
  "| Regra | Exemplo |\n|---|---|\n| não só… como também → plural | igreja e príncipe pagariam |\n| enumeração resumida por 'tudo' → singular com o resumo | tudo me levou |\n"
  "| coletivo partitivo + plural → singular ou plural | a maior parte dos políticos estava/estavam |\n| eu + ele → nós | convidamos |", dificuldade=2)

# ── Jaguariúna 2023 ──────────────────────────────────────────────────────

Q("jaguariuna", 1, "interpretacao-de-texto", "Discurso direto, indireto e indireto livre", "C",
  "Considere os seguintes excertos:\n\nI. “Conseguimos um pouso suave na Lua, a Índia está na Lua”, disse Sreedhara Panicker Somanath (...).\nII. “Ainda precisamos de muito mais detalhes sobre onde e quanta água existe, e saber se toda ela está congelada”, explica Akash Sinha (...)\nIII. O ex-presidente da Organização Indiana de Pesquisa Espacial K. Sivan disse que a viagem desta manhã será mais barata (...)\n\nNos excertos apresentados, ocorre discurso indireto apenas em:",
  ["I.", "II.", "III.", "I e II.", "II e III."],
  "Só III reconta a fala pela voz do narrador: letra {G}.\n\n"
  "| Discurso | Marca | Exemplo |\n|---|---|---|\n| direto | fala literal entre aspas ou travessão | I e II |\n| indireto | verbo dicendi + 'que' + fala adaptada | III: Sivan disse QUE a viagem será… |\n"
  "| indireto livre | fala do personagem misturada à do narrador, sem aspas nem 'disse que' | |\n\n"
  "Aspas e 1ª pessoa ('conseguimos', 'precisamos') denunciam o discurso direto.", dificuldade=1)

Q("jaguariuna", 2, "coesao-conectivos", "Conectivos: valor semântico", "D",
  "Considere o excerto: “Essas características tornam muito difícil operar equipamentos de exploração na região. DESSA FORMA, um pouso suave significa que o módulo não foi destruído.” No contexto apresentado, a expressão ‘dessa forma’ é empregada com a função de:",
  ["operador argumentativo de explicação.", "operador argumentativo de finalidade.", "operador argumentativo de oposição.",
   "operador argumentativo de conclusão.", "operador argumentativo de comparação."],
  "'Dessa forma' = portanto, assim: letra {G}.\n\n"
  "Premissa: a região dificulta a operação. Conclusão: pousar sem destruir já é vitória.\n\n"
  "| Valor | Operadores |\n|---|---|\n| conclusão | portanto, logo, assim, dessa forma, por isso |\n| explicação | pois, porque, já que (após ordem/afirmação) |\n"
  "| oposição | mas, porém, contudo, no entanto |\n| finalidade | para, a fim de, para que |\n\n"
  "Teste: troque por 'portanto'. Se o sentido se mantém, é conclusão.", dificuldade=1)

Q("jaguariuna", 3, "classes-de-palavras", "Morfologia: classificar palavras no contexto", "C",
  "Assinale a alternativa em que, no excerto apresentado, a palavra ‘se’ atua como conectivo oracional.",
  ["“Em missão histórica (...) a Índia se tornou o 1º país a pousar no polo sul da Lua”.",
   "“a Rússia tentou ser o 1º país a pousar no lado escuro da Lua (...) mas a sonda saiu de controle e se chocou contra a Lua.”",
   "“Ainda precisamos de muito mais detalhes sobre onde e quanta água existe, e saber se toda ela está congelada”.",
   "“O objetivo do país se tornou explorar a Lua com o menor custo possível.”",
   "“Índia se torna o 1º país a pousar no polo sul da Lua em missão histórica”."],
  "'Saber SE toda ela está congelada' — o 'se' liga a oração ao verbo saber: letra {G}.\n\n"
  "É conjunção subordinativa integrante: introduz oração que funciona como objeto (saber o quê? se está congelada).\n\n"
  "Nas outras, 'se' é pronome: parte integrante do verbo pronominal (tornar-se, chocar-se).\n\n"
  "| 'se' | Teste |\n|---|---|\n| conjunção integrante | troca por 'isso': saber isso |\n| conjunção condicional | troca por 'caso' |\n| pronome reflexivo/parte do verbo | acompanha o verbo: tornou-se |\n| partícula apassivadora | 'vende-se casa' = casa é vendida |", dificuldade=2)

Q("jaguariuna", 4, "classes-de-palavras", "Advérbio: classificação e circunstâncias", "A",
  "Considere o excerto: “Essas características tornam MUITO difícil operar equipamentos de exploração na região.” No contexto apresentado, a classificação da palavra ‘muito’, considerado o sentido que imprime ao enunciado, é:",
  ["advérbio de intensidade.", "pronome indefinido de quantidade.", "adjetivo de grau.", "substantivo comum.", "advérbio de modo."],
  "'Muito' intensifica o adjetivo 'difícil': letra {G}.\n\n"
  "| 'muito' | Classe | Exemplo |\n|---|---|---|\n| antes de adjetivo, advérbio ou verbo | advérbio de intensidade (invariável) | muito difícil, corre muito |\n"
  "| antes de substantivo | pronome indefinido (varia) | muitas crateras |\n\n"
  "Teste: se dá para pôr no plural ('muitos difícil'?), é pronome; se não dá, é advérbio.", dificuldade=1)

Q("jaguariuna", 6, "classes-de-palavras", "Morfologia: classificar palavras no contexto", "A",
  "Caso fosse ordinal, a escrita por extenso do numeral referente ao ano em “A primeira, em 2009, custou em torno de US$ 79 milhões.” seria:",
  ["dois milésimo nono.", "ducentésimo nono.", "segundo milésimo nono.", "bilésimo nono.", "bilionésimo nono."],
  "Ordinal de 2009 = dois milésimo nono: letra {G}.\n\n"
  "Na formação dos ordinais de milhar, o multiplicador fica cardinal: 2000º = dois milésimo; 3000º = três milésimo.\n\n"
  "| Número | Ordinal |\n|---|---|\n| 200º | ducentésimo |\n| 1000º | milésimo |\n| 2000º | dois milésimo |\n| 1.000.000º | milionésimo |\n\n"
  "Ducentésimo é 200º; bilionésimo é um bilhão. 'Segundo milésimo' não é a forma da norma-padrão.", dificuldade=3)

Q("jaguariuna", 7, "classes-de-palavras", "Substantivo: classificação e flexão", "D",
  "Considerando o emprego do hífen, as formas pluralizadas corretas das palavras ‘ex-presidente’ e ‘primeiro-ministro’, que ocorrem no texto, são:",
  ["exes-presidentes e primeiros-ministros.", "ex-presidentes e primeiros-ministro.", "ex-presidentes e primeiro-ministros.",
   "ex-presidentes e primeiros-ministros.", "exes-presidentes e primeiros-ministro."],
  "Plural dos compostos: letra {G}.\n\n"
  "| Composto | Regra | Plural |\n|---|---|---|\n| prefixo + substantivo | só o substantivo varia | ex-presidentes, vice-reitores |\n"
  "| numeral/adjetivo + substantivo | os dois variam | primeiros-ministros, segundas-feiras |\n| substantivo + de + substantivo | só o primeiro | pés-de-moleque (com hífen), mulas sem cabeça |\n"
  "| verbo + substantivo | só o substantivo | guarda-chuvas |\n\n"
  "Prefixo (ex-, vice-, pré-) nunca vai para o plural.", dificuldade=1)

Q("jaguariuna", 8, "regencia", "Regência verbal e transitividade", "B",
  "Considere a seguinte sentença: “Reintegraram-no ao pelotão sem mais perguntas”. O verbo \"reintegrar\", como consta na sentença dada, é:",
  ["transitivo indireto.", "transitivo direto e indireto.", "intransitivo.", "pronominal.", "transitivo direto."],
  "Reintegra-se alguém (OD) a algum lugar (OI): letra {G}.\n\n"
  "'no' = o (objeto direto, pronome oblíquo com 'n' por causa do -m do verbo); 'ao pelotão' = objeto indireto.\n\n"
  "| Pronome | Função |\n|---|---|\n| o, a, os, as (lo, no) | objeto direto |\n| lhe, lhes | objeto indireto |\n\n"
  "Não é pronominal: o pronome não é parte do verbo, é o complemento (reintegraram ELE).", dificuldade=2)

Q("jaguariuna", 9, "coesao-conectivos", "Referência e retomada (anáfora e catáfora)", "A",
  "Assinale a alternativa em que a sentença apresenta um elemento que atua como recurso coesivo referencial catafórico.",
  ["Tenho apenas um desejo para este ano: ser mais produtiva.", "Acéfalo ou acefalado é o nome dado ao animal que não tem cabeça.",
   "O tempo voa…voa!", "Se não atender às expectativas dele, será dispensado.", "Podemos ir ao cinema, já que sua reunião foi cancelada."],
  "'Um desejo' anuncia o que vem depois dos dois-pontos: letra {G}.\n\n"
  "Catáfora = o termo aponta PARA FRENTE; o referente aparece depois ('ser mais produtiva').\n\n"
  "Na D, 'dele' aponta para alguém fora da frase; na E, 'já que' é conectivo causal, não referência.\n\n"
  "Dois-pontos depois de 'isto', 'o seguinte', 'um desejo', 'uma coisa' é o sinal clássico de catáfora.", dificuldade=2)

Q("jaguariuna", 10, "verbo-tempo-modo-voz", "Vozes verbais", "D",
  "Observe as alternativas abaixo e assinale aquela que NÃO contém um verbo pronominal.",
  ["O jornaleiro penteou-se e preparou-se para mais um dia de trabalho.", "As nações envolvidas atinham-se aos fatos mais recentes.",
   "O odor do perfume espalhou-se pelo corredor.",
   "Os empreendimentos foram realocados no novo centro comercial, onde construiu-se um prédio mais moderno que o anterior.",
   "As artistas terminaram sua performance e se sentaram à beira do picadeiro."],
  "'Construiu-se um prédio' = um prédio foi construído: voz passiva sintética. Letra {G}.\n\n"
  "O 'se' ali é partícula apassivadora, não parte de verbo pronominal.\n\n"
  "Teste da passiva: troque por 'foi + particípio'. 'Construiu-se um prédio' → 'um prédio foi construído' (funciona). 'Sentaram-se' → 'foram sentadas'? (muda o sentido) → pronominal.\n\n"
  "Bônus de norma: 'onde construiu-se' deveria ser 'onde se construiu' — 'onde' atrai o pronome. A banca não cobrou isso aqui.", dificuldade=2)

# ── SAAE Amparo 2023 ─────────────────────────────────────────────────────

Q("saae", 1, "interpretacao-de-texto", IINF, "A",
  "No texto, a narradora estabelece um paralelo entre seu estado de espírito, de mansidão, e a chuva que observa pela janela. Esse paralelo é evidente no trecho:",
  ["“Estamos ocupadas ambas em fluir.”", "“É que não estou habituada a não precisar de meu próprio consolo.”",
   "“Apenas isso: chove e estou vendo a chuva.”", "“Por hábito estou procurando na chuva o que em outro momento me serviria de consolo.”",
   "“E apenas vivo de uma alegria mansa.”"],
  "'Ambas' = a narradora e a chuva, fazendo a mesma coisa: letra {G}.\n\n"
  "Paralelo é aproximar os dois termos. Só em 'Estamos ocupadas ambas em fluir' narradora e chuva aparecem juntas, iguais, no mesmo verbo.\n\n"
  "As outras falam da narradora sozinha (B, E) ou da chuva como objeto que ela observa (C, D).", dificuldade=2, **SAAE)

Q("saae", 2, "sentido-das-palavras", "Sinônimos, antônimos e reescrita com mesmo sentido", "A",
  "Considere o seguinte excerto: “Não estou sentindo nada. Mas é o contrário de um torpor.” Neste contexto, a palavra “torpor” significa:",
  ["indiferença.", "ânimo.", "sossego.", "esperança.", "vigor."],
  "Torpor = entorpecimento, apatia, indiferença: letra {G}.\n\n"
  "A narradora não sente nada, mas avisa que não é o vazio da apatia — é uma calma viva.\n\n"
  "Ânimo e vigor são antônimos de torpor. Sossego é próximo, mas positivo; torpor é inércia.", dificuldade=2, **SAAE)

Q("saae", 3, "classes-de-palavras", "Morfologia: classificar palavras no contexto", "A",
  "Considere a seguinte sentença, retirada do texto: “A chuva também não agradece nada.” Em relação às classes gramaticais, as palavras “chuva”, “também”, “não” e “nada” são, respectivamente:",
  ["substantivo, advérbio, advérbio e pronome indefinido.", "adjetivo, advérbio, advérbio e pronome indefinido.",
   "substantivo, substantivo, advérbio e pronome indefinido.", "substantivo, advérbio, preposição e pronome indefinido.",
   "substantivo, advérbio, advérbio e substantivo."],
  "Letra {G}.\n\n| Palavra | Classe | Por quê |\n|---|---|---|\n| chuva | substantivo | nomeia, vem com artigo |\n| também | advérbio (de inclusão/afirmação) | modifica o verbo |\n"
  "| não | advérbio de negação | |\n| nada | pronome indefinido | substitui 'coisa alguma' (objeto de agradecer) |", dificuldade=1)

Q("saae", 4, "classes-de-palavras", "Pronomes: classificação", "A",
  "Considere a seguinte sentença, retirada do texto: “Estou à janela e só acontece isto: vejo com olhos benéficos a chuva, e a chuva me vê de acordo comigo.” Os pronomes “isto”, “me” e “comigo” são, respectivamente, dos tipos:",
  ["pronome demonstrativo, pronome pessoal do caso oblíquo, pronome pessoal do caso oblíquo.",
   "pronome relativo, pronome pessoal do caso reto, pronome pessoal do caso oblíquo.",
   "pronome indefinido, pronome pessoal do caso reto, pronome pessoal do caso oblíquo.",
   "pronome demonstrativo, pronome possessivo, pronome pessoal do caso reto.",
   "pronome relativo, pronome pessoal do caso oblíquo, pronome pessoal do caso reto."],
  "Letra {G}.\n\n| Pronome | Tipo |\n|---|---|\n| isto | demonstrativo (e aqui catafórico: anuncia o que vem após os dois-pontos) |\n"
  "| me | pessoal oblíquo átono (objeto de 'vê') |\n| comigo | pessoal oblíquo tônico (com + mim) |\n\n"
  "Retos: eu, tu, ele, nós, vós, eles — só funcionam como sujeito. Me, te, se, o, lhe, mim, comigo são oblíquos.", dificuldade=1)

Q("saae", 5, "coesao-conectivos", "Referência e retomada (anáfora e catáfora)", "C",
  "Considere o excerto “quando fui procurá-LA, ela já se havia transformado em carne e espírito, já não existia mais como pensamento.” Neste contexto, o pronome “la” se refere à:",
  ["chuva.", "tranquila alegria.", "palavra consolo.", "angústia.", "dor."],
  "A frase anterior: 'A palavra consolo aconteceu sem eu sentir […] e quando fui procurá-la': letra {G}.\n\n"
  "O verbo ajuda: o que 'deixou de existir como pensamento' e 'se transformou em carne e espírito' é a palavra, que virou vivência.\n\n"
  "Método: procure o substantivo feminino singular mais próximo antes do pronome que faça sentido com o verbo.", dificuldade=1, **SAAE)

Q("saae", 6, "regencia", "Regência verbal e transitividade", "B",
  "Considere as seguintes sentenças, retiradas do texto:\n\nI. “A palavra consolo aconteceu sem eu sentir.”\nII. “Em pleno dia era noite.”\n\nEm relação à regência, os verbos “aconteceu” e “era”, nas sentenças dadas, são, respectivamente:",
  ["verbo transitivo direto e verbo de ligação.", "verbo intransitivo e verbo de ligação.",
   "verbo transitivo direto e verbo transitivo direto.", "verbo intransitivo e verbo intransitivo.", "verbo de ligação e verbo de ligação."],
  "Letra {G}.\n\n'Acontecer' não pede complemento: intransitivo ('sem eu sentir' é adjunto).\n\n'Era' liga o sujeito a um estado ('noite' é predicativo): verbo de ligação.\n\n"
  "Verbos de ligação típicos: ser, estar, parecer, permanecer, ficar, continuar, andar (= estar), virar (= tornar-se).\n\n"
  "Pegadinha: 'ser' também pode ser intransitivo (= existir), mas aqui atribui característica ao tempo.", dificuldade=2)

Q("saae", 7, "colocacao-pronominal", "Colocação pronominal (próclise, ênclise e mesóclise)", "D",
  "Considere os seguintes excertos:\n\nI. “Mas como é que ME arrumo com essa simples e tranquila alegria.”\nII. “Talvez seja isso ao que SE poderia chamar de estar vivo.”\n\nNeste contexto, a ordem de colocação dos pronomes “me” e “se” corresponde, respectivamente, a:",
  ["próclise e mesóclise.", "ênclise e próclise.", "mesóclise e próclise.", "próclise e próclise.", "ênclise e ênclise."],
  "Os dois vêm ANTES do verbo: letra {G}.\n\n"
  "| Colocação | Posição | Exemplo |\n|---|---|---|\n| próclise | antes do verbo | me arrumo, se poderia |\n| ênclise | depois, com hífen | arrumo-me |\n| mesóclise | no meio (futuro do presente/pretérito) | poder-se-ia |\n\n"
  "Na II, 'poderia' é futuro do pretérito, e por isso a mesóclise seria possível (poder-se-ia) — é a pegadinha. Mas o pronome relativo 'que' atrai, e a próclise é obrigatória.", dificuldade=2)

Q("saae", 8, "classes-de-palavras", "Morfologia: classificar palavras no contexto", "A",
  "Considere as seguintes palavras:\n\nI. esforçada.\nII. amanhecer.\nIII. pedante.\n\nApresenta(m) morfema flexional de gênero apenas a(s) palavra(s):",
  ["esforçada.", "amanhecer.", "pedante.", "esforçada e pedante.", "amanhecer e pedante."],
  "Só 'esforçada' tem o '-a' de feminino (esforçado/esforçada): letra {G}.\n\n"
  "| Palavra | Gênero |\n|---|---|\n| esforçada | adjetivo biforme: -o / -a é flexão de gênero |\n| amanhecer | verbo: flexiona em tempo, modo, número e pessoa, não em gênero |\n"
  "| pedante | adjetivo uniforme: o homem pedante, a mulher pedante |\n\n"
  "Uniformes comuns: -ante, -ente, -ista, -vel (pedante, inteligente, otimista, amável).", dificuldade=2)

Q("saae", 9, "ortografia-acentuacao", "Acentuação gráfica e sílaba tônica", "E",
  "Assinale a alternativa que apresenta a palavra acentuada corretamente.",
  ["conjuge.", "pêra.", "cosmopolíta.", "rúbrica.", "cripta."],
  "'Cripta' é paroxítona terminada em -a: sem acento. Letra {G}.\n\n"
  "| Errado | Certo | Regra |\n|---|---|---|\n| conjuge | cônjuge | proparoxítona: sempre acentuada |\n| pêra | pera | o Acordo de 1990 aboliu o acento diferencial de pera |\n"
  "| cosmopolíta | cosmopolita | paroxítona terminada em -a não leva acento |\n| rúbrica | rubrica | é paroxítona (ru-BRI-ca); 'rúbrica' é erro de pronúncia |", dificuldade=2)

Q("saae", 10, "crase", "Crase", "C",
  "Considere as seguintes sentenças:\n\nI. Fui à assembleia da universidade ontem.\nII. Ela entregou a carta à Pedro.\nIII. Não sei por que ela disse àquilo ao pai.\n\nO emprego da crase está correto apenas na(s) sentença(s):",
  ["I e II.", "II.", "I.", "I e III.", "I, II e III."],
  "Letra {G}, só a I.\n\n| Sentença | Análise |\n|---|---|\n| I | ir A + A assembleia → à ✔ |\n| II | Pedro é masculino: não há artigo 'a' → 'a Pedro' |\n"
  "| III | 'dizer' pede objeto direto (disse aquilo), não há preposição → 'disse aquilo' |\n\n"
  "Teste do masculino: 'fui ao congresso' → crase em 'à assembleia'. 'Àquilo' só leva crase quando o verbo pede 'a': 'refiro-me àquilo'.", dificuldade=1)

# ── São Miguel Arcanjo 2023 ──────────────────────────────────────────────

Q("sma", 1, "interpretacao-de-texto", IINF, "A",
  "No conto, a narradora discorre sobre sua convivência com outra garota em sua infância. A relação entre essas personagens é marcada por:",
  ["desagrado, já que a narradora supervaloriza negativamente todas as características e ações da outra garota.",
   "cumplicidade, uma vez que ambas as personagens são próximas e compartilham de tudo.",
   "violência, tendo em vista que a narradora se sente constantemente ameaçada pela outra garota.",
   "disputa, já que a narradora faz comparações entre ela e suas outras amigas frequentemente.",
   "indiferença, uma vez que a narradora não faz questão de ser amiga da garota de quem fala."],
  "A descrição é carregada de desagrado: letra {G}.\n\n"
  "'Gorda, baixa, sardenta', 'pura vingança', 'talento para a crueldade', 'sadismo', 'fel' — a narradora pinta a menina pelo pior lado em tudo.\n\n"
  "Cumplicidade e indiferença são o contrário; não há violência física nem disputa entre amigas — há humilhação e espera.", dificuldade=2, **SMA)

Q("sma", 2, "interpretacao-de-texto", IINF, "B",
  "Ao dizer “Mas que talento tinha para a crueldade”, a narradora considera que a garota de quem fala é cruel porque:",
  ["ela aproveitava da bondade de suas amigas.",
   "ela não dava presentes interessantes para suas amigas, não emprestava livros, nem oferecia suas balas.",
   "ela espalhava mentiras sobre suas amigas.", "ela se considerava superior, porque tinha um busto enorme.",
   "ela era falsa com suas amigas."],
  "O que vem logo antes da frase: letra {G}.\n\n"
  "Ela tinha o pai dono de livraria, mas dava cartão-postal no aniversário em vez de um livrinho; enchia os bolsos de balas e chupava 'com barulho' na frente das outras.\n\n"
  "A crueldade é ter e negar. As alternativas sobre mentira, falsidade e superioridade pelo busto não estão no texto.", dificuldade=2, **SMA)

Q("sma", 3, "sentido-das-palavras", "Sinônimos, antônimos e reescrita com mesmo sentido", "B",
  "Considere o seguinte trecho: “Comigo exerceu com calma FEROCIDADE o seu SADISMO.” As palavras em destaque podem ser substituídas, sem grande prejuízo de significado, pelas seguintes palavras, respectivamente:",
  ["pressa e perversidade.", "fereza e crueldade.", "velocidade e egoísmo.", "raiva e prazer.", "agressividade e satisfação."],
  "Letra {G}.\n\n| Palavra | Sinônimos |\n|---|---|\n| ferocidade | fereza, crueldade, selvageria |\n| sadismo | crueldade, prazer em fazer sofrer |\n\n"
  "'Prazer' (D) e 'satisfação' (E) pegam só metade do sentido de sadismo — falta o fazer sofrer. 'Calma ferocidade' é oxímoro: a crueldade é fria, não agitada.", dificuldade=2)

Q("sma", 4, "classes-de-palavras", "Morfologia: classificar palavras no contexto", "B",
  "As palavras destacadas no trecho “ELA era gorda, baixa, sardenta e de cabelos EXCESSIVAMENTE crespos, MEIO ARRUIVADOS” são, respectivamente, das seguintes categorias gramaticais:",
  ["pronome; advérbio; numeral; adjetivo.", "pronome; advérbio; advérbio; adjetivo.", "pronome; substantivo; substantivo; adjetivo.",
   "substantivo; adjetivo; substantivo; advérbio.", "pronome; advérbio; adjetivo; adjetivo."],
  "Letra {G}.\n\n| Palavra | Classe |\n|---|---|\n| ela | pronome pessoal reto |\n| excessivamente | advérbio de intensidade (modifica 'crespos') |\n"
  "| meio | advérbio (= um pouco), invariável |\n| arruivados | adjetivo |\n\n"
  "Pegadinha: 'meio' é numeral quando é metade de algo (meio quilo, meia hora). Antes de adjetivo, é advérbio e não varia: 'meio arruivados', 'meio cansada'.", dificuldade=2)

Q("sma", 5, "classes-de-palavras", "Pronomes: classificação", "D",
  "No trecho “continuava a implorar-LHE emprestados os livros que ela não lia”, a palavra em destaque se trata de um:",
  ["pronome pessoal de caso reto.", "pronome de tratamento.", "pronome demonstrativo.", "pronome pessoal de caso oblíquo.", "pronome indefinido."],
  "'Lhe' é oblíquo átono, objeto indireto (implorar a ela): letra {G}.\n\n"
  "| Caso | Pronomes |\n|---|---|\n| reto (sujeito) | eu, tu, ele, ela, nós, vós, eles |\n| oblíquo átono | me, te, se, o, a, lhe, nos, vos, os, as, lhes |\n| oblíquo tônico | mim, ti, si, ele, ela (com preposição), comigo |", dificuldade=1)

Q("sma", 7, "regencia", "Regência verbal e transitividade", "A",
  "Considere o seguinte excerto: “Mas POSSUÍA o que qualquer criança devoradora de histórias GOSTARIA de ter: um pai dono de livraria.” Em relação à regência, os verbos destacados são, respectivamente:",
  ["verbo transitivo direto; verbo transitivo indireto.", "verbo transitivo indireto; verbo intransitivo.",
   "verbo intransitivo; verbo transitivo indireto.", "verbo transitivo direto; verbo transitivo direto.", "verbo intransitivo; verbo intransitivo."],
  "Possuir algo (sem preposição); gostar DE algo: letra {G}.\n\n"
  "'Possuía o que…' → objeto direto. 'Gostaria de ter' → objeto indireto (a oração 'de ter').\n\n"
  "Teste: a preposição é exigida pelo verbo? 'Gostar' sem 'de' não existe nesse sentido → transitivo indireto.", dificuldade=1)

Q("sma", 8, "classes-de-palavras", "Substantivo: classificação e flexão", "D",
  "Considere as seguintes palavras: funil, arroz, cidadão, fóssil, cútis, peixe-boi, bem-te-vi. Assinale a alternativa que apresenta corretamente cada uma dessas palavras em sua forma pluralizada:",
  ["funils, arrozes, cidadões, fóssis, cútis, peixe-bois, bem-te-vis.", "funizes, arroz, cidadãos, fósseis, cútis, peixes-bois, bens-te-vis.",
   "funis, arroz, cidadãos, fóssis, cútis, peixes-boi, bem-te-vi.", "funis, arrozes, cidadãos, fósseis, cútis, peixes-boi, bem-te-vis.",
   "funis, arrozes, cidadões, fósseis, cútis, peixes-bois, bem-te-vi."],
  "Letra {G}.\n\n| Singular | Plural | Regra |\n|---|---|---|\n| funil | funis | -il tônico → -is |\n| fóssil | fósseis | -il átono → -eis |\n| arroz | arrozes | -z → -zes |\n"
  "| cidadão | cidadãos | -ão: decorar (cidadãos, pães, leões) |\n| cútis | cútis | paroxítona em -s é invariável |\n"
  "| peixe-boi | peixes-boi (ou peixes-bois) | substantivo que especifica o outro: só o 1º varia |\n| bem-te-vi | bem-te-vis | composto com verbo: só o último |", dificuldade=2)

Q("sma", 9, "pontuacao", "Dois-pontos, travessão e outros sinais", "C",
  "Considere a seguinte sentença: “Uma senhora tinha um cão filhote e o pai da senhora era também a mãe do filhote”. Assinale a alternativa que apresenta corretamente o uso dos sinais de pontuação:",
  ["Uma senhora, tinha um cão filhote, e o pai da senhora, era também a mãe do filhote.",
   "Uma senhora tinha um cão filhote e o pai da senhora era, também, a mãe do filhote.",
   "Uma senhora tinha um cão filhote e o pai; da senhora era também a mãe do filhote.",
   "Uma senhora tinha um cão filhote, e, o pai da senhora, era também a mãe do filhote.",
   "Uma senhora tinha um cão filhote, e o pai, da senhora era também a mãe do filhote."],
  "A pontuação desfaz o absurdo ('o pai da senhora era a mãe do filhote'): letra {G}.\n\n"
  "Com o ponto e vírgula: a senhora tinha o filhote E O PAI do filhote; a cadela da senhora era também a mãe do filhote. O ponto e vírgula separa as duas orações e 'da senhora era também a mãe' passa a falar da dona.\n\n"
  "| Alternativa | Problema |\n|---|---|\n| A | vírgula entre sujeito e verbo (2 vezes) |\n| B | sintaxe correta, mas mantém o sentido absurdo |\n| D, E | vírgula separando sujeito de verbo |\n\n"
  "É questão-charada: a banca quer a pontuação que dá SENTIDO lógico à frase.", dificuldade=3)

Q("sma", 10, "classes-de-palavras", "Adjetivo e locução adjetiva", "B",
  "Considere as sentenças: 1) “Ela correu RÁPIDO em direção à casa”; 2) “A cerveja que desce REDONDO”. As palavras destacadas, embora funcionem como advérbios de modo, são, respectivamente, das seguintes categorias gramaticais:",
  ["adjetivo e substantivo.", "adjetivo e adjetivo.", "substantivo e substantivo.", "verbo e substantivo.", "substantivo e adjetivo."],
  "Adjetivos usados como advérbio: letra {G}.\n\n"
  "Rápido e redondo são adjetivos de origem (carro rápido, mesa redonda). Aqui modificam o verbo e ficam invariáveis — é a adjetivação adverbial (ela correu rápido, não 'rápida').\n\n"
  "Outros: falar alto, custar caro, trabalhar duro, ver claro.", dificuldade=2)
