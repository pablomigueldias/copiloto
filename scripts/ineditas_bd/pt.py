"""Língua portuguesa — inéditas, pela norma-padrão e pelo Manual de Redação da Presidência da República (3ª ed., 2018)."""
from base import Sequencia, Topico

SEQ_PT = Sequencia()
_kw = dict(materia="Português Avança SP", cargo="Língua Portuguesa (nível superior)", sequencia=SEQ_PT)

SIN = Topico("Análise sintática", 1, "pt-analise-sintatica", "Análise sintática", **_kw)
COL = Topico("Colocação pronominal", 2, "pt-colocacao-pronominal", "Colocação pronominal", **_kw)
FIG = Topico("Figuras de linguagem", 3, "pt-figuras-de-linguagem", "Figuras de Linguagem", **_kw)
RED = Topico("Redação oficial", 4, "pt-redacao-oficial",
             "Redação oficial: atributos da redação oficial, pronomes de tratamento, tipos de documentos", **_kw)
REG = Topico("Regência verbal e nominal", 5, "pt-regencia", "Regência verbal e nominal", **_kw)
PON = Topico("Pontuação", 6, "pt-pontuacao", "Pontuação", **_kw)
CRA = Topico("Crase", 7, "pt-crase", "Crase", **_kw)
CON = Topico("Concordância verbal e nominal", 8, "pt-concordancia", "Concordância verbal e nominal", **_kw)

TOPICOS = [SIN, COL, FIG, RED, REG, PON, CRA, CON]

# ── Análise sintática ──
SIN.mc(
    "Na oração “Faltaram dois candidatos à prova de ontem.”, o sujeito é",
    "“dois candidatos”, sujeito simples posposto ao verbo.",
    ["oculto, identificável pela desinência do verbo.", "indeterminado, pois não se sabe quem faltou.",
     "inexistente, pois o verbo faltar é impessoal.", "“à prova de ontem”, por indicar o que faltou."],
    "Quem faltou? Letra {G}: “dois candidatos”.\n\n"
    "Para achar o sujeito, pergunte ao verbo 'o que / quem faltou?' → dois candidatos. Ele vem DEPOIS do verbo (posposto), e o verbo concorda com ele no plural: faltaram.\n\n"
    "Teste da concordância: troque por singular — 'Faltou um candidato à prova'. O verbo acompanhou, então é o sujeito.\n\n"
    "Faltar NÃO é impessoal (impessoais são haver no sentido de existir, fazer e haver indicando tempo, verbos de fenômeno da natureza). "
    "“À prova de ontem” é complemento (adjunto adverbial / objeto indireto, conforme a análise), nunca sujeito, porque vem com preposição.\n\n"
    "Atalho: sujeito não começa com preposição.",
    dificuldade=1,
)
SIN.mc(
    "Assinale a alternativa em que há oração sem sujeito.",
    "Havia muitos processos acumulados na mesa do analista.",
    ["Existiam muitos processos acumulados na mesa do analista.", "Os servidores chegaram cedo à repartição.",
     "Aconteceram falhas graves no sistema durante a migração.", "Precisa-se de técnicos com experiência em banco de dados."],
    "Oração sem sujeito: letra {G}.\n\n"
    "Haver no sentido de EXISTIR é impessoal: não tem sujeito e fica na 3ª pessoa do singular. 'Muitos processos' é objeto direto. Por isso o certo é 'havia muitos processos', nunca 'haviam'.\n\n"
    "| Frase | Sujeito |\n|---|---|\n| Existiam muitos processos | muitos processos (existir TEM sujeito e concorda) |\n"
    "| Os servidores chegaram | os servidores |\n| Aconteceram falhas graves | falhas graves (posposto) |\n"
    "| Precisa-se de técnicos | INDETERMINADO (verbo + preposição + se) — existe sujeito, só não é identificado |\n\n"
    "Principais orações sem sujeito: haver = existir ou indicando tempo ('há dois anos'); fazer indicando tempo ou clima ('faz frio', 'faz três meses'); fenômenos da natureza (chover, ventar, anoitecer).\n\n"
    "Sujeito indeterminado ≠ oração sem sujeito: é a pegadinha da última alternativa.",
    dificuldade=2,
)
SIN.mc(
    "No período “A obediência às normas de segurança é obrigatória para todos os servidores.”, o termo “às normas de segurança” exerce a função sintática de",
    "complemento nominal.",
    ["objeto indireto.", "adjunto adnominal.", "agente da passiva.", "adjunto adverbial."],
    "“Às normas de segurança” completando “obediência”: letra {G}, complemento nominal.\n\n"
    "O termo completa um SUBSTANTIVO (obediência), e não um verbo. Complemento de nome = complemento nominal.\n\n"
    "Compare:\n\n— 'Os servidores OBEDECEM às normas' → completa VERBO → objeto indireto;\n\n— 'A OBEDIÊNCIA às normas' → completa NOME → complemento nominal.\n\n"
    "Complemento nominal × adjunto adnominal (a dúvida mais cobrada): com substantivo abstrato, o complemento nominal tem sentido PASSIVO (as normas SÃO obedecidas); "
    "o adjunto adnominal tem sentido ATIVO ou de posse ('a obediência DOS SERVIDORES' — os servidores obedecem → adjunto adnominal).\n\n"
    "Atalho: o termo preposicionado ligado a adjetivo ou advérbio é sempre complemento nominal ('útil AO PROJETO', 'favoravelmente À PROPOSTA').",
    dificuldade=3,
)

# ── Colocação pronominal ──
COL.mc(
    "Assinale a alternativa em que a colocação do pronome oblíquo átono está de acordo com a norma-padrão.",
    "Não me informaram o novo prazo de entrega do sistema.",
    ["Não informaram-me o novo prazo de entrega do sistema.", "Me informaram ontem o novo prazo de entrega do sistema.",
     "Quem informou-me o prazo foi o coordenador do projeto.", "Espero que informem-me o novo prazo ainda hoje."],
    "Colocação pronominal: letra {G}.\n\n"
    "Palavra NEGATIVA (não, nunca, ninguém, nada) atrai o pronome para antes do verbo: PRÓCLISE. 'Não me informaram.'\n\n"
    "| Frase errada | Por quê | Correção |\n|---|---|---|\n"
    "| Não informaram-me | 'não' atrai o pronome | Não me informaram |\n"
    "| Me informaram ontem | não se inicia período com pronome átono | Informaram-me ontem |\n"
    "| Quem informou-me | pronome interrogativo ou relativo atrai | Quem me informou |\n"
    "| Espero que informem-me | conjunção subordinativa ('que') atrai | Espero que me informem |\n\n"
    "Fatores de próclise: palavras negativas, pronomes relativos, interrogativos e indefinidos, conjunções subordinativas, advérbios sem vírgula depois ('Aqui se trabalha').",
    dificuldade=1,
)
COL.mc(
    "Considerando a norma-padrão, a forma correta de colocar o pronome “lhe” junto ao verbo “enviar” no futuro do presente, em início de oração e sem palavra atrativa, é",
    "Enviar-lhe-emos o relatório até sexta-feira.",
    ["Enviaremos-lhe o relatório até sexta-feira.", "Lhe enviaremos o relatório até sexta-feira.",
     "Enviaremo-lhe o relatório até sexta-feira.", "Enviar-emos-lhe o relatório até sexta-feira."],
    "Futuro do presente, início de oração, sem atrativo: letra {G}, MESÓCLISE.\n\n"
    "Com verbo no futuro do presente ou no futuro do pretérito, a norma proíbe a ênclise. Sem palavra atrativa, o pronome entra NO MEIO do verbo, entre o infinitivo e a terminação:\n\n"
    "enviar + emos → enviar-lhe-emos\nfar + ia → far-se-ia\nentregar + ei → entregar-lhe-ei\n\n"
    "Se houver palavra atrativa, vira próclise: 'Não lhe enviaremos', 'Logo lhe enviaremos'.\n\n"
    "'Enviaremos-lhe' é ênclise ao futuro (proibida). 'Lhe enviaremos' inicia período com átono (proibido na norma, embora comum na fala).",
    dificuldade=2,
)
COL.mc(
    "Assinale a alternativa que apresenta colocação pronominal em DESACORDO com a norma-padrão.",
    "Os documentos tinham sido entregues-lhe pela manhã.",
    ["Avise-me assim que o servidor voltar a funcionar.", "Ninguém nos comunicou a mudança de horário.",
     "Os relatórios que lhe enviei estavam incompletos.", "Tudo se resolveu depois da atualização do sistema."],
    "Colocação em DESACORDO: letra {G}.\n\n"
    "Nunca se coloca pronome átono depois de PARTICÍPIO. Em locução com particípio, o pronome vai junto ao verbo auxiliar: 'Os documentos tinham-lhe sido entregues' ou 'lhe tinham sido entregues' (havendo atrativo).\n\n"
    "As demais estão corretas:\n\n— 'Avise-me': ênclise no imperativo afirmativo, início de oração;\n\n— 'Ninguém nos comunicou': pronome indefinido negativo atrai;\n\n"
    "— 'que lhe enviei': pronome relativo atrai;\n\n— 'Tudo se resolveu': pronome indefinido 'tudo' atrai.\n\n"
    "Regras de 'nunca': nunca ênclise a particípio; nunca ênclise a futuro (use mesóclise); nunca pronome átono iniciando período.",
    formato="negativa", dificuldade=2,
)

# ── Figuras de linguagem ──
FIG.mc(
    "Em “Na biblioteca do órgão, li Machado de Assis inteiro durante as férias.”, ocorre a figura de linguagem denominada",
    "metonímia, pois o autor é usado no lugar de sua obra.",
    ["metáfora, pois há comparação implícita entre o autor e a biblioteca.", "hipérbole, pois há exagero intencional.",
     "eufemismo, pois se suaviza uma ideia desagradável.", "antítese, pois há oposição de ideias."],
    "“Li Machado de Assis”: letra {G}, metonímia.\n\n"
    "Ninguém lê uma pessoa — lê os LIVROS dela. Metonímia é trocar um termo por outro com o qual mantém relação real, de proximidade:\n\n"
    "| Relação | Exemplo |\n|---|---|\n| autor pela obra | li Machado de Assis |\n| continente pelo conteúdo | bebeu dois copos |\n"
    "| marca pelo produto | comprei um Gillette |\n| parte pelo todo | não tem um teto onde morar |\n| lugar pelos habitantes | o Brasil votou |\n\n"
    "Metáfora é diferente: a relação é de SEMELHANÇA, uma comparação sem 'como' ('aquele servidor é uma máquina').\n\n"
    "Atalho: há ligação real e lógica entre os termos → metonímia; há só parecença → metáfora.",
    dificuldade=1,
)
FIG.mc(
    "Na frase “Já pedi um milhão de vezes que os arquivos sejam salvos na rede!”, predomina a figura de linguagem",
    "hipérbole.", ["eufemismo.", "ironia.", "prosopopeia.", "pleonasmo."],
    "“Um milhão de vezes”: letra {G}, hipérbole — exagero intencional para dar ênfase.\n\n"
    "| Figura | Mecanismo | Exemplo |\n|---|---|---|\n| hipérbole | exagero | morri de rir; esperei uma eternidade |\n"
    "| eufemismo | suavização | ele nos deixou (morreu); faltou com a verdade (mentiu) |\n| ironia | diz o contrário do que pensa | que pontualidade! (para quem chegou atrasado) |\n"
    "| prosopopeia | dá ação ou sentimento humano a seres inanimados | o sistema reclamou da carga |\n| pleonasmo | repetição de ideia | subir para cima (vicioso); vi com meus próprios olhos (de reforço) |\n\n"
    "Hipérbole e eufemismo são opostos: um aumenta, o outro atenua.",
    dificuldade=1,
)

# ── Redação oficial ──
RED.mc(
    "Em um ofício dirigido a um Ministro de Estado, tratado por Vossa Excelência, a concordância está de acordo com o Manual de Redação da Presidência da República em:",
    "Informamos que Vossa Excelência será recebido pelo Diretor e poderá apresentar seu parecer.",
    ["Informamos que Vossa Excelência sereis recebido pelo Diretor e podereis apresentar vosso parecer.",
     "Informamos que Vossa Excelência será recebido pelo Diretor e poderá apresentar vosso parecer.",
     "Informamos que Vossa Excelência serás recebido pelo Diretor e poderás apresentar teu parecer.",
     "Informamos que Vossa Excelência será recebida pelo Diretor e poderá apresentar seu parecer."],
    "Concordância com pronome de tratamento: letra {G}.\n\n"
    "Embora começados por 'Vossa', os pronomes de tratamento levam verbo e pronomes possessivos na 3ª PESSOA: 'Vossa Excelência será... SEU parecer' — nunca 'sereis', 'vosso', 'teu'.\n\n"
    "O adjetivo concorda com o SEXO da pessoa, não com 'Excelência': ao Ministro, 'Vossa Excelência está ocupado'; à Ministra, 'está ocupada'. "
    "Por isso 'será recebida' está errada aqui: o destinatário é um Ministro (homem).\n\n"
    "Vossa × Sua: 'Vossa Excelência' quando se fala COM a autoridade; 'Sua Excelência' quando se fala DELA ('Sua Excelência, o Ministro, chegou').",
    dificuldade=2,
)
RED.mc(
    "Segundo o Manual de Redação da Presidência da República (3ª edição), o fecho adequado para comunicações oficiais dirigidas a autoridade de hierarquia SUPERIOR à do remetente é",
    "Respeitosamente,", ["Atenciosamente,", "Cordialmente,", "Sem mais para o momento,", "Cordiais saudações,"],
    "Fecho para autoridade superior: letra {G}, Respeitosamente.\n\n"
    "O Manual prevê apenas dois fechos para as comunicações oficiais:\n\n"
    "| Destinatário | Fecho |\n|---|---|\n| hierarquia SUPERIOR (inclusive o Presidente da República) | Respeitosamente, |\n| MESMA hierarquia ou INFERIOR | Atenciosamente, |\n\n"
    "Comunicações a autoridades estrangeiras seguem o rito do Ministério das Relações Exteriores.\n\n"
    "'Sem mais para o momento', 'Cordialmente' e 'Cordiais saudações' não estão previstos e ferem a concisão e a padronização.",
    dificuldade=1,
)
RED.mc(
    "O atributo da redação oficial que exige a ausência de impressões individuais de quem comunica, já que o texto é feito em nome do serviço público e se dirige ao público ou a outros órgãos, é a",
    "impessoalidade.", ["concisão.", "clareza.", "formalidade.", "coesão."],
    "Sem impressões individuais, em nome do serviço público: letra {G}, impessoalidade.\n\n"
    "Atributos da redação oficial segundo o Manual (3ª ed.):\n\n"
    "| Atributo | Significa |\n|---|---|\n| clareza e precisão | o texto tem um só sentido, sem ambiguidade |\n| objetividade | ir direto ao ponto |\n"
    "| concisão | o máximo de informação com o mínimo de palavras |\n| coesão e coerência | ideias encadeadas e não contraditórias |\n"
    "| impessoalidade | quem fala é o serviço público; sem opinião pessoal nem tom íntimo |\n| formalidade e padronização | norma-padrão, tratamento adequado e formato uniforme |\n\n"
    "Exemplo de falta de impessoalidade: 'Eu acho que o pedido do senhor é justo'. Impessoal: 'O pedido atende aos requisitos'.",
    dificuldade=1,
)

# ── Regência ──
REG.mc(
    "Assinale a alternativa em que a regência verbal está de acordo com a norma-padrão.",
    "O novo sistema implica mudanças na rotina dos servidores.",
    ["Os candidatos aspiram o cargo de analista de banco de dados.", "Esqueci do prazo de entrega do relatório.",
     "O técnico não obedeceu o manual de instalação.", "Chegamos no escritório às oito horas."],
    "Regência verbal: letra {G}.\n\n"
    "IMPLICAR no sentido de 'acarretar' é transitivo DIRETO: implica mudanças (sem 'em'). 'Implicar em' é uso coloquial que as bancas condenam.\n\n"
    "| Frase errada | Regra | Correção |\n|---|---|---|\n"
    "| aspiram o cargo | aspirar = DESEJAR pede 'a' (aspirar = respirar é direto) | aspiram ao cargo |\n"
    "| Esqueci do prazo | esquecer sem pronome é direto; com pronome, pede 'de' | Esqueci o prazo / Esqueci-me do prazo |\n"
    "| obedeceu o manual | obedecer (e desobedecer) pede 'a' | obedeceu ao manual |\n"
    "| Chegamos no escritório | verbos de movimento pedem 'a' | Chegamos ao escritório |",
    dificuldade=2,
)
REG.mc(
    "Considerando a regência do verbo “assistir”, a frase que está de acordo com a norma-padrão é:",
    "Todos os analistas assistiram ao treinamento sobre o novo SGBD.",
    ["Todos os analistas assistiram o treinamento sobre o novo SGBD.", "O treinamento foi assistido por todos os analistas.",
     "Todos os analistas assistiram-no durante a manhã, referindo-se ao treinamento.", "Todos os analistas assistiram em um treinamento sobre o novo SGBD."],
    "Assistir = ver, presenciar: letra {G}, assistiram AO treinamento.\n\n"
    "| Sentido de assistir | Regência | Exemplo |\n|---|---|---|\n| ver, presenciar | indireto, com 'a' | assisti ao jogo |\n"
    "| ajudar, dar assistência | direto (ou indireto) | o médico assistiu o paciente |\n| caber, ser direito de | indireto, com 'a' | esse direito assiste ao servidor |\n| morar (arcaico) | com 'em' | assistia em Santos |\n\n"
    "Consequências que caem em prova: como é transitivo indireto, no sentido de 'ver' não admite voz passiva ('foi assistido por' é condenado) "
    "e não aceita 'o/a' como complemento — usa-se 'a ele': 'assistiram a ele', não 'assistiram-no'.",
    dificuldade=2,
)
REG.mc(
    "Assinale a alternativa correta quanto à regência do verbo “preferir”.",
    "A equipe prefere trabalhar remotamente a enfrentar o trânsito diário.",
    ["A equipe prefere mais trabalhar remotamente do que enfrentar o trânsito diário.", "A equipe prefere trabalhar remotamente do que enfrentar o trânsito diário.",
     "A equipe prefere muito mais trabalhar remotamente que enfrentar o trânsito diário.", "A equipe prefere trabalhar remotamente em vez de que enfrentar o trânsito diário."],
    "Preferir: letra {G}.\n\n"
    "Na norma-padrão, prefere-se uma coisa A outra: preferir algo A algo.\n\n"
    "— Não se usa 'do que': ele é termo de comparação, e 'preferir' já contém a ideia de 'mais'.\n\n"
    "— Não se usa 'mais' nem 'muito mais' antes: seria redundância (pleonasmo vicioso).\n\n"
    "Prefiro café a chá.\nPrefiro estudar a sair.\nPrefiro o PostgreSQL ao MySQL. (a + o = ao)\n\n"
    "Atalho: preferir combina com 'a', nunca com 'do que'.",
    dificuldade=1,
)

# ── Pontuação ──
PON.mc(
    "Assinale a alternativa em que a pontuação está de acordo com a norma-padrão.",
    "Senhores servidores, a reunião sobre o novo sistema começará às 14h.",
    ["Senhores servidores a reunião sobre o novo sistema, começará às 14h.", "Os servidores do setor de TI, participarão da reunião às 14h.",
     "A reunião, sobre o novo sistema começará às 14h.", "Os servidores, que trabalham no setor de TI participarão da reunião."],
    "Pontuação: letra {G}.\n\n"
    "'Senhores servidores' é VOCATIVO (chamamento); o vocativo é sempre separado por vírgula.\n\n"
    "| Frase errada | Erro |\n|---|---|\n| Senhores servidores a reunião..., começará | falta a vírgula do vocativo e há vírgula entre sujeito e verbo |\n"
    "| Os servidores do setor de TI, participarão | vírgula entre sujeito e verbo |\n| A reunião, sobre o novo sistema começará | separa o nome do seu complemento e, de quebra, o sujeito do verbo |\n"
    "| Os servidores, que trabalham no setor de TI participarão | abriu a oração explicativa e não fechou: falta a vírgula depois de 'TI' |\n\n"
    "Regras de ouro: nunca separar sujeito do verbo; termo intercalado abre e fecha; vocativo sempre entre vírgulas (ou seguido de vírgula, no início).",
    dificuldade=1,
)
PON.mc(
    "Considere as frases:\n\nI. Os analistas que concluíram o curso receberão certificado.\nII. Os analistas, que concluíram o curso, receberão certificado.\n\nSobre elas, é correto afirmar que",
    "em I, apenas parte dos analistas concluiu o curso; em II, todos os analistas concluíram o curso.",
    ["as duas frases têm exatamente o mesmo sentido; as vírgulas são facultativas.", "em I, todos os analistas concluíram o curso; em II, apenas parte deles.",
     "a frase II está incorreta, pois não se usa vírgula antes de 'que'.", "a frase I está incorreta, pois a oração 'que concluíram o curso' exige vírgulas."],
    "Com e sem vírgula antes do 'que': letra {G}.\n\n"
    "| Frase | Oração adjetiva | Sentido |\n|---|---|---|\n| I, sem vírgulas | RESTRITIVA | restringe: só os analistas que concluíram (há outros que não concluíram) |\n"
    "| II, com vírgulas | EXPLICATIVA | explica algo de TODOS: os analistas — todos eles — concluíram |\n\n"
    "As duas estão gramaticalmente corretas; o que muda é o sentido. Por isso a vírgula aqui não é facultativa.\n\n"
    "Teste: a explicativa pode ser retirada sem mudar quem recebe o certificado ('Os analistas receberão certificado' — todos). A restritiva, não.",
    dificuldade=2,
)

# ── Crase ──
CRA.mc(
    "Assinale a alternativa em que o acento indicativo de crase está empregado corretamente.",
    "O relatório foi entregue à diretora antes do prazo.",
    ["O relatório foi entregue à Vossa Senhoria antes do prazo.", "O sistema começou à funcionar ontem.",
     "Enviamos o documento à todos os setores.", "O pagamento será feito à prazo."],
    "Crase: letra {G}.\n\n"
    "'Entregar algo A alguém' (preposição) + 'A diretora' (artigo feminino) = À diretora. Teste com masculino: 'entregue AO diretor' → no feminino, crase.\n\n"
    "| Frase errada | Regra |\n|---|---|\n| à Vossa Senhoria | não há crase antes de pronomes de tratamento (exceto senhora, senhorita, dona) |\n"
    "| à funcionar | nunca antes de VERBO |\n| à todos | nunca antes de pronome indefinido e de palavra masculina |\n| à prazo | nunca antes de palavra masculina ('a prazo', 'a pé', 'a cavalo') |\n\n"
    "Atalho: troque a palavra feminina por uma masculina. Se aparecer 'ao', há crase; se aparecer só 'a', não há.",
    dificuldade=1,
)
CRA.mc(
    "Assinale a alternativa em que o acento indicativo de crase está empregado INCORRETAMENTE.",
    "A partir de segunda-feira, o atendimento será feito das 8h às 17h, de segunda à sexta-feira.",
    ["A reunião começará às 14h.", "À medida que os testes avançavam, os erros diminuíam.",
     "Os servidores dirigiram-se à sala de reuniões.", "O sistema estará disponível às segundas e quartas-feiras."],
    "Crase INCORRETA: letra {G}.\n\n"
    "'De segunda A sexta-feira': quando o primeiro termo vem sem artigo ('de', e não 'da'), o segundo também vem sem: só preposição, sem crase. "
    "Com artigo nos dois, há crase: 'DA segunda À sexta-feira'. A frase acerta em 'das 8h às 17h' (com artigo: das... às...).\n\n"
    "As demais estão certas:\n\n— 'às 14h': hora determinada leva crase;\n\n— 'À medida que': locução conjuntiva feminina;\n\n"
    "— 'dirigiram-se à sala': dirigir-se A + A sala;\n\n— 'às segundas e quartas-feiras': dias da semana no plural com artigo, ideia de repetição.\n\n"
    "'A partir de' nunca tem crase: 'partir' é verbo.\n\n"
    "Atalho do paralelismo: de... a (sem crase); da... à (com crase).",
    formato="negativa", dificuldade=3,
)

# ── Concordância ──
CON.mc(
    "Assinale a alternativa em DESACORDO com a norma-padrão quanto à concordância.",
    "Fazem três meses que o novo sistema foi implantado.",
    ["Mais de um servidor faltou à reunião de ontem.", "Deve haver soluções mais simples para esse problema.",
     "A maioria dos candidatos chegou cedo ao local de prova.", "Seguem anexas as planilhas solicitadas."],
    "Concordância em DESACORDO: letra {G}.\n\n"
    "FAZER indicando tempo decorrido é IMPESSOAL: fica no singular. 'Faz três meses', 'fazia dois anos'.\n\n"
    "As demais estão corretas:\n\n"
    "— 'Mais de um servidor faltou': com 'mais de um', o verbo fica no singular (o plural só se impõe com reciprocidade ou repetição: 'mais de um servidor se cumprimentaram');\n\n"
    "— 'Deve haver soluções': haver (existir) impessoal transmite a impessoalidade ao auxiliar — 'deve haver', nunca 'devem haver';\n\n"
    "— 'A maioria dos candidatos chegou': com coletivo partitivo, singular ou plural são aceitos;\n\n"
    "— 'Seguem anexas as planilhas': 'anexo' é adjetivo e concorda (anexas, femininas e plurais).",
    formato="negativa", dificuldade=2,
)
CON.mc(
    "Assinale a alternativa correta quanto à concordância nominal.",
    "É proibida a entrada de pessoas não autorizadas na sala dos servidores.",
    ["É proibida entrada de pessoas não autorizadas na sala dos servidores.", "Seguem anexo os relatórios de desempenho.",
     "As informações estavam meias incompletas.", "Os documentos foram bastante revisados e estavam bastantes claros."],
    "Concordância nominal: letra {G}.\n\n"
    "Com 'é proibido', 'é necessário', 'é bom': se o substantivo vem COM artigo ou determinante, o adjetivo concorda ('é proibida A entrada'); "
    "sem determinante, fica no masculino singular ('é proibido entrada'). Por isso 'é proibida entrada', sem o artigo, está errada.\n\n"
    "| Frase errada | Regra | Correção |\n|---|---|---|\n| anexo os relatórios | 'anexo' é adjetivo e concorda | anexos os relatórios |\n"
    "| meias incompletas | 'meio' = um pouco é ADVÉRBIO, invariável | meio incompletas |\n| bastantes claros | 'bastante' antes de adjetivo é advérbio, invariável | bastante claros |\n\n"
    "Atalho: meio, bastante, menos, só (= somente) modificando ADJETIVO não variam; modificando SUBSTANTIVO, variam ('bastantes documentos', 'meia hora').",
    dificuldade=2,
)
