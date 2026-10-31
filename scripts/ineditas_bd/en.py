"""Inglês técnico — inéditas, no padrão de docs/avanca-sp/ingles-tecnico-padrao.md.

Textos de apoio escritos por mim, sobre BD, instalação, segurança e cloud. Os
enunciados seguem a Cesgranrio (em inglês) na maioria, com alguns no estilo
Vunesp/FCC (pergunta em português sobre texto em inglês). Cada questão traz o
`assunto` do catálogo do simulado.
"""
from base import Sequencia, Topico

SEQ_EN = Sequencia()
_kw = dict(materia="Inglês técnico Avança SP", cargo="Inglês técnico (PAS – Analista de TI)",
           sequencia=SEQ_EN)

TXT = Topico("Compreensão de texto técnico", 1, "en-compreensao",
             "Compreensão de textos técnicos: manuais, documentação, guias de instalação, artigos técnicos", **_kw)
VOC = Topico("Vocabulário técnico", 2, "en-vocabulario",
             "Vocabulário técnico em TI e glossário básico de TI em inglês", **_kw)
GRA = Topico("Gramática aplicada à leitura", 3, "en-gramatica",
             "Compreensão de textos técnicos: leitura e interpretação", **_kw)
CMD = Topico("Comandos, mensagens de erro e logs", 4, "en-comandos-erros",
             "Instruções e comandos; interpretação de mensagens de erro e logs de sistemas", **_kw)
NOR = Topico("Normas, RFCs e redação técnica", 5, "en-normas-redacao",
             "Leitura de protocolos e normas (RFCs, ISO, NIST); redação técnica", **_kw)

TOPICOS = [TXT, VOC, GRA, CMD, NOR]

A_IDEIA = "Ideia principal e finalidade do texto"
A_INFO = "Informação específica (according to the text)"
A_INF = "Inferência em texto técnico"
A_VOC = "Vocabulário em contexto (sinônimo)"
A_GHW = "Glossário de TI: hardware, redes e cloud"
A_GBD = "Glossário de TI: banco de dados e programação"
A_GSEG = "Glossário de TI: segurança da informação"
A_FALSO = "Falsos cognatos"
A_REF = "Referência pronominal"
A_CON = "Conectivos e marcadores de coesão"
A_FORM = "Formação de palavras (prefixos e sufixos)"
A_MOD = "Verbos modais e voz passiva em documentação"
A_ERR = "Mensagens de erro e logs"
A_CMD = "Comandos de sistema e instruções de instalação"
A_RFC = "RFCs e palavras-chave MUST, SHOULD e MAY"
A_NORMA = "Normas ISO e NIST"
A_RED = "Redação técnica: e-mail e relatório"

# ── Texto 1 — documentação de banco de dados ─────────────────────────────

T1 = """Transaction Isolation

(1) Transactions allow several operations to be grouped so that they either all succeed or all fail. However, when many transactions run at the same time, the database must decide how much one transaction is allowed to see of the changes made by the others. This decision is controlled by the isolation level.

(2) At the READ COMMITTED level, which is the default in PostgreSQL and SQL Server, a query sees only data that was committed before the query began. It never sees uncommitted changes from concurrent transactions. Nevertheless, two identical queries in the same transaction may return different results if another transaction commits changes between them. This phenomenon is known as a non-repeatable read.

(3) The SERIALIZABLE level provides the strictest isolation. It guarantees that the result of concurrent transactions is the same as if they had been executed one after another. This protection comes at a cost: applications using this level must be prepared to retry transactions, since the server may abort them to prevent anomalies.

(4) Developers should choose the lowest level that still guarantees correct results for their workload. Raising the isolation level unnecessarily may reduce throughput and increase the number of failed transactions."""
F1 = "Texto escrito para esta questão, no estilo da documentação do PostgreSQL e do SQL Server."
_t1 = dict(texto=T1, fonte_texto=F1)

TXT.mc(
    "The main purpose of the text is to",
    "explain how isolation levels control what concurrent transactions can see of each other's changes.",
    ["convince developers to use the SERIALIZABLE level in every application.",
     "describe the steps required to install PostgreSQL and SQL Server.",
     "compare the prices of different database management systems.",
     "report a defect in the way READ COMMITTED is implemented."],
    "Finalidade do texto: letra {G}.\n\n"
    "A pista está no fim do parágrafo 1: 'This decision is controlled by the isolation level'. O texto apresenta o problema (o que uma transação vê das outras) e depois explica dois níveis.\n\n"
    "| Distrator | Por que cai |\n|---|---|\n| convince ... every application | o parágrafo 4 diz o contrário: escolher o MENOR nível que garanta resultado correto |\n"
    "| install | não há passo de instalação |\n| prices | custo aparece como desempenho ('comes at a cost'), não preço |\n| defect | o texto descreve comportamento normal, não bug |\n\n"
    "Atalho de banca: a alternativa de finalidade certa cobre o texto inteiro; as erradas pegam uma palavra solta ('SERIALIZABLE', 'PostgreSQL').",
    assunto=A_IDEIA, dificuldade=1, **_t1,
)
TXT.mc(
    "According to paragraph 2, a non-repeatable read happens when",
    "the same query, executed twice in one transaction, returns different results because another transaction committed changes in between.",
    ["a query reads changes that another transaction has not committed yet.",
     "the server aborts a transaction to prevent anomalies.",
     "two transactions are executed one after another.",
     "the database is configured with the SERIALIZABLE level."],
    "Leitura literal do parágrafo 2: letra {G}.\n\n"
    "'two identical queries in the same transaction may return different results if another transaction commits changes between them. This phenomenon is known as a non-repeatable read.'\n\n"
    "| Anomalia | O que é | Nível que já impede |\n|---|---|---|\n| dirty read | ler dado NÃO confirmado | READ COMMITTED |\n"
    "| non-repeatable read | reler a mesma linha e achar outro valor | REPEATABLE READ |\n| phantom read | repetir a consulta e aparecerem linhas novas | SERIALIZABLE |\n\n"
    "A primeira errada descreve a dirty read, que o texto diz que NUNCA acontece em READ COMMITTED ('It never sees uncommitted changes'). É a pegadinha.",
    assunto=A_INFO, dificuldade=2, **_t1,
)
GRA.mc(
    "In paragraph 2, the word “Nevertheless” introduces an idea of",
    "contrast.",
    ["addition.", "consequence.", "exemplification.", "time sequence."],
    "Nevertheless = no entanto, mesmo assim. Letra {G}.\n\n"
    "O trecho anterior diz algo bom (não vê dado não confirmado); o seguinte faz a ressalva (mas pode ver resultados diferentes).\n\n"
    "| Ideia | Conectivos |\n|---|---|\n| contraste | however, nevertheless, nonetheless, yet, but, whereas |\n"
    "| concessão | although, even though, despite, in spite of |\n| consequência | therefore, thus, hence, consequently, as a result |\n"
    "| adição | moreover, furthermore, in addition, besides |\n| exemplo | for instance, for example, such as |\n\n"
    "Truque: 'never' dentro da palavra não tem nada a ver com 'nunca' aqui.",
    assunto=A_CON, dificuldade=1, **_t1,
)
GRA.mc(
    "In paragraph 3, the pronoun “them”, in “the server may abort them”, refers to",
    "transactions.",
    ["applications.", "anomalies.", "isolation levels.", "results."],
    "Referência: letra {G}.\n\n"
    "'applications ... must be prepared to retry transactions, since the server may abort them'. O servidor aborta (cancela) o quê? As transações que a aplicação tenta de novo.\n\n"
    "Método: pegue o verbo do pronome (abort) e teste cada candidato no plural anterior. 'Abort applications' não faz sentido técnico; 'abort anomalies' é o contrário do que o texto diz (aborta PARA evitar anomalias).\n\n"
    "Plural: them / their / they só retomam nome no plural — já elimina candidatos no singular.",
    assunto=A_REF, dificuldade=1, **_t1,
)
GRA.mc(
    "In paragraph 4, the modal verb in “Developers should choose the lowest level” expresses",
    "a recommendation.",
    ["an obligation imposed by law.", "a prohibition.", "an ability in the past.", "a certainty about the future."],
    "Modal should = deveria / é recomendável. Letra {G}.\n\n"
    "| Modal | Sentido | Em português |\n|---|---|---|\n| must | obrigação forte | tem de |\n| should | recomendação, conselho | deveria |\n"
    "| may / might | possibilidade (ou permissão) | pode, talvez |\n| can | capacidade, possibilidade | pode, consegue |\n| could | capacidade no passado / possibilidade | podia, poderia |\n"
    "| must not | proibição | não pode |\n| will | certeza / futuro | vai |\n\n"
    "No mesmo parágrafo: 'may reduce throughput' = PODE reduzir (possibilidade).",
    assunto=A_MOD, dificuldade=1, **_t1,
)
TXT.mc(
    "It can be inferred from the text that using the SERIALIZABLE level in a system with many concurrent updates",
    "may cause more transactions to be aborted and retried.",
    ["eliminates the need for transactions.", "always increases throughput.",
     "is not supported by PostgreSQL.", "makes non-repeatable reads more frequent."],
    "Inferência a partir dos parágrafos 3 e 4: letra {G}.\n\n"
    "O 3 diz que o servidor pode abortar transações no SERIALIZABLE; o 4 diz que subir o nível sem necessidade 'may ... increase the number of failed transactions'. Com muita concorrência, mais conflitos → mais abortos.\n\n"
    "| Distrator | Problema |\n|---|---|\n| eliminates transactions | o nível É de transação |\n| always increases throughput | o texto diz que pode REDUZIR |\n"
    "| not supported by PostgreSQL | o texto não diz; e é falso |\n| more non-repeatable reads | SERIALIZABLE é o mais estrito: impede |\n\n"
    "Inferência de banca não inventa: ela junta dois trechos do texto. Alternativa com 'always' costuma estar errada.",
    assunto=A_INF, dificuldade=2, **_t1,
)
VOC.mc(
    "In paragraph 4, the word “throughput” is closest in meaning to",
    "the amount of work a system completes in a given period of time.",
    ["the delay before a single response is returned.", "the size of the database files on disk.",
     "the number of users who have access to the database.", "the level of encryption applied to the data."],
    "Throughput = vazão, quantidade de trabalho por unidade de tempo (transações por segundo, MB/s). Letra {G}.\n\n"
    "| Termo | Mede | Exemplo |\n|---|---|---|\n| throughput | volume por tempo | 2.000 transações/s |\n| latency | demora de UMA resposta | 15 ms |\n"
    "| bandwidth | capacidade máxima do canal | 1 Gbps |\n\n"
    "A primeira errada é a definição de latency — o par que a banca troca.",
    assunto=A_VOC, dificuldade=2, **_t1,
)

# ── Texto 2 — guia de instalação ─────────────────────────────────────────

T2 = """Installing MySQL Server on Ubuntu

1. Update the package index:
   $ sudo apt update
2. Install the server package:
   $ sudo apt install mysql-server
3. Check whether the service is running:
   $ sudo systemctl status mysql
   If the output shows "inactive (dead)", start it with: sudo systemctl start mysql
4. Run the security script, which removes anonymous users, disables remote root login and deletes the test database:
   $ sudo mysql_secure_installation
5. Make sure that port 3306 is not exposed to the internet unless remote access is strictly required. If it is, restrict incoming connections to known IP addresses in the firewall.

Note: Do not edit the configuration files while the service is being upgraded. Back up /etc/mysql before making any changes."""
F2 = "Texto escrito para esta questão, no formato de um guia de instalação."
_t2 = dict(texto=T2, fonte_texto=F2)

CMD.mc(
    "According to the guide, the command in step 3 is used to",
    "verify whether the MySQL service is running.",
    ["install the MySQL server package.", "update the list of available packages.",
     "remove anonymous users from the server.", "open port 3306 in the firewall."],
    "Passo 3: 'Check whether the service is running' → systemctl status mysql. Letra {G}.\n\n"
    "| Comando | Faz |\n|---|---|\n| systemctl status X | mostra se o serviço está ativo (active/running) ou parado (inactive/dead) |\n"
    "| systemctl start / stop / restart X | inicia / para / reinicia |\n| systemctl enable X | faz subir no boot |\n"
    "| apt update | atualiza a LISTA de pacotes (não instala nada) |\n| apt install X | instala |\n\n"
    "'Check whether' = verificar se.",
    assunto=A_CMD, dificuldade=1, **_t2,
)
CMD.mc(
    "According to step 4, the script mysql_secure_installation does all of the following, EXCEPT",
    "open port 3306 to remote connections.",
    ["remove anonymous users.", "disable remote login for the root user.",
     "delete the test database.", "run with administrative privileges through sudo."],
    "EXCEPT = exceto: procure a que o passo 4 NÃO diz. Letra {G}.\n\n"
    "O passo 4 lista: removes anonymous users, disables remote root login, deletes the test database — e o comando começa com sudo (privilégio de administrador).\n\n"
    "Abrir a porta 3306 é o contrário do que o guia quer: o passo 5 manda NÃO expor a porta.\n\n"
    "Comando negativo (EXCEPT, NOT, INCORRECT) é 1 em cada 10 questões da Avança SP. Leia o comando duas vezes.",
    assunto=A_CMD, dificuldade=1, **_t2,
)
TXT.mc(
    "De acordo com o passo 5 do guia, a porta 3306",
    "não deve ficar exposta à internet, a menos que o acesso remoto seja estritamente necessário; nesse caso, o firewall deve aceitar apenas endereços IP conhecidos.",
    ["deve ser aberta para qualquer endereço logo após a instalação.",
     "é usada apenas pelo script de segurança do passo 4.",
     "precisa ser fechada antes de atualizar a lista de pacotes.",
     "só pode ser usada quando o serviço estiver parado."],
    "Leitura do passo 5: letra {G}.\n\n"
    "| Trecho | Tradução |\n|---|---|\n| Make sure that port 3306 is not exposed | garanta que a porta 3306 não fique exposta |\n"
    "| unless remote access is strictly required | a menos que o acesso remoto seja estritamente necessário |\n| If it is, restrict incoming connections | se for, restrinja as conexões de entrada |\n"
    "| to known IP addresses | a endereços IP conhecidos |\n\n"
    "3306 é a porta padrão do MySQL (SQL Server 1433, PostgreSQL 5432).",
    assunto=A_INFO, dificuldade=1, **_t2,
)
VOC.mc(
    "In the note, the expression “Back up” is",
    "a phrasal verb meaning to make a copy of data so that it can be restored later.",
    ["a noun meaning a copy of the data.", "an adjective describing the configuration files.",
     "a verb meaning to move files back to their original folder.", "a verb meaning to delete old configuration files."],
    "Back up (duas palavras, verbo) × backup (uma palavra, substantivo). Letra {G}.\n\n"
    "| Forma | Classe | Exemplo |\n|---|---|---|\n| back up | verbo (phrasal verb) | Back up /etc/mysql before... |\n| backup | substantivo | The backup failed. |\n"
    "| backup | adjetivo (antes de nome) | a backup server |\n\n"
    "No texto ele vem no início da frase dando uma ordem (imperativo), o que já mostra que é verbo. O mesmo padrão: log in (verbo) × login (substantivo); set up × setup; shut down × shutdown.",
    assunto=A_VOC, dificuldade=2, **_t2,
)
GRA.mc(
    "In step 5, the word “unless” can be replaced, without change in meaning, by",
    "except if.",
    ["because.", "although.", "as soon as.", "in addition."],
    "Unless = a menos que, exceto se. Letra {G}.\n\n"
    "'not exposed unless remote access is required' = não exposta, exceto se o acesso remoto for necessário.\n\n"
    "| Conectivo | Sentido |\n|---|---|\n| unless | condição negativa (a menos que) |\n| if | condição |\n| because / since | causa |\n"
    "| although / even though | concessão |\n| as soon as | tempo (assim que) |\n\n"
    "Unless já é negativo: 'unless it is required' = 'if it is not required'.",
    assunto=A_CON, dificuldade=1, **_t2,
)

# ── Texto 3 — política de senha (NIST) ───────────────────────────────────

T3 = """Password Policy — adapted from the NIST Digital Identity Guidelines (SP 800-63B)

(1) For many years, organizations required users to create passwords containing uppercase letters, digits and symbols, and to change them every 90 days. Research has shown that these rules often backfire: users respond with predictable patterns, such as "Password1!" followed by "Password2!".

(2) Current guidance therefore focuses on length rather than complexity. User-chosen passwords MUST be at least 8 characters long, and systems SHOULD accept passwords of at least 64 characters, so that users can adopt long passphrases. Every new password MUST be checked against a list of values known to be commonly used or previously compromised.

(3) Verifiers SHOULD NOT require passwords to be changed periodically. A change MUST, however, be forced whenever there is evidence that the password has been compromised. Password hints and security questions such as "What was the name of your first pet?" MUST NOT be used, since their answers can often be found on social media.

(4) Finally, passwords MUST be stored only as salted hashes computed with a function designed to be slow, which makes offline guessing attacks considerably more expensive.

In this text, the keywords MUST, MUST NOT, SHOULD and SHOULD NOT are to be interpreted as described in RFC 2119."""
F3 = "Texto escrito para esta questão, a partir das recomendações do NIST SP 800-63B."
_t3 = dict(texto=T3, fonte_texto=F3)

TXT.mc(
    "The text mainly argues that password policies should",
    "prioritize length and screening against compromised passwords over complexity rules and periodic changes.",
    ["require uppercase letters, digits and symbols in every password.",
     "force all users to change their passwords every 90 days.",
     "rely on security questions to recover forgotten passwords.",
     "store passwords in a reversible format to simplify recovery."],
    "Tese do texto: letra {G}.\n\n"
    "Parágrafo 1: as regras antigas (complexidade + troca a cada 90 dias) 'backfire'. Parágrafo 2: 'focuses on length rather than complexity' e checagem contra senhas vazadas. Parágrafo 3: SHOULD NOT exigir troca periódica.\n\n"
    "As erradas 1 e 2 são exatamente as regras que o texto critica; a 3 é proibida (MUST NOT); a 4 contradiz o parágrafo 4 (hash não é reversível).\n\n"
    "'rather than' = em vez de — conectivo que entrega a tese.",
    assunto=A_IDEIA, dificuldade=1, **_t3,
)
NOR.mc(
    "Considering the meaning of the keywords defined in RFC 2119, the sentence “systems SHOULD accept passwords of at least 64 characters” indicates that accepting such passwords is",
    "recommended, although there may be valid reasons in particular circumstances to do otherwise.",
    ["an absolute requirement of the specification.", "an absolute prohibition of the specification.",
     "truly optional, with no recommendation either way.", "the minimum length that every password must have."],
    "SHOULD na RFC 2119: recomendado. Letra {G}.\n\n"
    "| Palavra-chave | Sinônimos na RFC | Sentido |\n|---|---|---|\n| MUST | REQUIRED, SHALL | requisito absoluto |\n| MUST NOT | SHALL NOT | proibição absoluta |\n"
    "| SHOULD | RECOMMENDED | recomendado; pode haver razão válida para não seguir, desde que as implicações sejam entendidas |\n"
    "| SHOULD NOT | NOT RECOMMENDED | não recomendado, com a mesma ressalva |\n| MAY | OPTIONAL | opcional de verdade |\n\n"
    "A última errada confunde os números: o mínimo é 8 (MUST); 64 é o que o sistema deveria ACEITAR (SHOULD).",
    assunto=A_RFC, dificuldade=2, **_t3,
)
TXT.mc(
    "According to paragraph 3, a password change must be forced",
    "whenever there is evidence that the password has been compromised.",
    ["every 90 days.", "whenever the user forgets the answer to a security question.",
     "whenever the password is shorter than 64 characters.", "whenever the user adopts a long passphrase."],
    "Parágrafo 3: 'A change MUST, however, be forced whenever there is evidence that the password has been compromised.' Letra {G}.\n\n"
    "| Situação | O texto diz |\n|---|---|\n| troca periódica (90 dias) | SHOULD NOT |\n| suspeita de comprometimento | MUST forçar a troca |\n"
    "| perguntas de segurança | MUST NOT usar |\n\n"
    "'compromised' = comprometida, vazada (não 'compromissada'). 'whenever' = sempre que.",
    assunto=A_INFO, dificuldade=1, **_t3,
)
VOC.mc(
    "In paragraph 1, the verb “backfire” means",
    "to produce the opposite of the intended effect.",
    ["to start a fire in the server room.", "to work exactly as expected.",
     "to become mandatory by law.", "to be easily memorized."],
    "Backfire = sair pela culatra, ter efeito contrário. Letra {G}.\n\n"
    "O próprio texto explica logo depois dos dois-pontos: as regras de complexidade fizeram os usuários criar senhas PREVISÍVEIS ('Password1!', 'Password2!') — o contrário do que se queria.\n\n"
    "Dica de prova: quando a palavra é desconhecida, a explicação costuma vir depois de ':' ou de 'such as'. Não traduza pedaço por pedaço (back + fire).",
    assunto=A_VOC, dificuldade=2, **_t3,
)
GRA.mc(
    "In paragraph 3, the word “their”, in “since their answers can often be found on social media”, refers to",
    "password hints and security questions.",
    ["verifiers.", "users' passwords.", "social media platforms.", "compromised passwords."],
    "Referência: letra {G}.\n\n"
    "'Password hints and security questions ... MUST NOT be used, since their answers can often be found on social media.' As RESPOSTAS de quê aparecem nas redes sociais? Das perguntas de segurança (o nome do primeiro pet).\n\n"
    "their = deles/delas (plural). O referente é o sujeito da mesma frase, que vem antes do pronome.",
    assunto=A_REF, dificuldade=2, **_t3,
)
TXT.mc(
    "Infere-se do parágrafo 4 que armazenar senhas com uma função de hash rápida e sem salt",
    "tornaria mais baratos os ataques de adivinhação offline, caso a base de senhas vazasse.",
    ["impediria qualquer ataque de adivinhação, por ser irreversível.",
     "é a prática recomendada pelo texto para sistemas com muitos usuários.",
     "permitiria recuperar a senha original do usuário sem custo.",
     "só é proibida quando a senha tem menos de 8 caracteres."],
    "Inferência pelo contrário do que o texto manda: letra {G}.\n\n"
    "O texto exige hash com salt e função LENTA porque isso 'makes offline guessing attacks considerably more expensive'. Tirar as duas proteções faz o ataque ficar barato.\n\n"
    "| Proteção | Contra o quê |\n|---|---|\n| salt (valor aleatório por senha) | tabelas pré-calculadas (rainbow tables) e senhas iguais com o mesmo hash |\n"
    "| função lenta (bcrypt, scrypt, Argon2, PBKDF2) | força bruta offline: cada tentativa custa caro |\n\n"
    "Hash não se 'descriptografa': o atacante testa candidatos e compara. Por isso a terceira errada cai.",
    assunto=A_INF, dificuldade=2, **_t3,
)
VOC.mc(
    "In paragraph 4, the expression “salted hashes” refers to",
    "hash values computed after a random value is added to each password.",
    ["passwords encrypted with the user's public key.", "passwords stored in plain text with a fixed prefix.",
     "a single hash shared by all users who chose the same password.", "passwords compressed to save disk space."],
    "Salt = valor aleatório, diferente para cada usuário, juntado à senha antes do hash. Letra {G}.\n\n"
    "Efeito: duas pessoas com a senha '123456' ficam com hashes DIFERENTES — a quarta errada é justamente o que o salt evita.\n\n"
    "| Termo | Significado |\n|---|---|\n| hash | resumo de tamanho fixo, de mão única |\n| salt | aleatório guardado junto do hash |\n"
    "| encryption | cifragem reversível com chave |\n| plain text | texto em claro |",
    assunto=A_GSEG, dificuldade=2, **_t3,
)

# ── Texto 4 — cloud e virtualização ──────────────────────────────────────

T4 = """Containers and Virtual Machines

(1) Virtual machines (VMs) and containers are both used to run applications in isolated environments, but they achieve isolation at different levels. A VM emulates a complete computer, including its own operating system kernel, on top of a hypervisor. Containers, on the other hand, share the kernel of the host and isolate only the application and its dependencies.

(2) Because they do not boot a full operating system, containers start in seconds and consume less memory, which allows a single server to host many more of them. VMs, although heavier, offer stronger isolation. That is why they remain the preferred choice when workloads from different customers must run on the same physical hardware.

(3) In cloud computing, the two technologies are frequently combined: providers run customer containers inside lightweight VMs, obtaining the density of containers together with the security boundary of a hypervisor.

(4) For database servers, containers are widely adopted in development and testing environments. In production, however, administrators must ensure that data is written to persistent volumes; otherwise, it will be lost when the container is removed."""
F4 = "Texto escrito para esta questão, no estilo de artigo técnico sobre cloud computing."
_t4 = dict(texto=T4, fonte_texto=F4)

TXT.mc(
    "The text is mainly intended to",
    "compare virtual machines and containers and show how they can be used together.",
    ["prove that containers have replaced virtual machines in cloud computing.",
     "teach readers how to install a hypervisor.",
     "argue that databases should never run in containers.",
     "describe the history of operating system kernels."],
    "Finalidade: letra {G}.\n\n"
    "Parágrafo 1 compara; 2 mostra vantagens de cada um; 3 mostra os dois combinados; 4 aplica a banco de dados.\n\n"
    "| Distrator | Por que cai |\n|---|---|\n| replaced | o 3 diz que são COMBINADOS, e o 2 que VMs seguem preferidas em multi-cliente |\n"
    "| install a hypervisor | não há instrução |\n| never run in containers | o 4 diz que é comum em desenvolvimento e possível em produção com volume persistente |\n| history | não há história |",
    assunto=A_IDEIA, dificuldade=1, **_t4,
)
TXT.mc(
    "According to paragraph 1, the main difference between VMs and containers is that",
    "each VM runs its own operating system kernel, while containers share the kernel of the host.",
    ["containers run their own kernel, while VMs share the kernel of the host.",
     "VMs do not provide any isolation between applications.",
     "containers can only run on physical servers, never in the cloud.",
     "VMs isolate only the application and its dependencies."],
    "Parágrafo 1: letra {G}.\n\n"
    "| | VM | Container |\n|---|---|---|\n| kernel | próprio (SO completo) | compartilha o do host |\n| roda sobre | hypervisor | runtime de container (Docker, containerd) |\n"
    "| inicia em | minutos | segundos |\n| isolamento | mais forte | mais leve |\n\n"
    "A primeira errada inverte os dois — a troca preferida da banca. A última atribui à VM o que o texto diz do container ('isolate only the application and its dependencies').\n\n"
    "'on the other hand' = por outro lado (contraste).",
    assunto=A_INFO, dificuldade=1, **_t4,
)
GRA.mc(
    "In paragraph 2, the word “although”, in “VMs, although heavier, offer stronger isolation”, introduces",
    "a concession.",
    ["a cause.", "a result.", "a condition.", "an addition."],
    "Although = embora. Concessão: admite um ponto contra (são mais pesadas) sem negar a ideia principal (isolam melhor). Letra {G}.\n\n"
    "| Ideia | Inglês | Português |\n|---|---|---|\n| concessão | although, though, even though, despite, in spite of | embora, apesar de |\n"
    "| causa | because, since, as, due to | porque, devido a |\n| resultado | so, therefore, thus | então, portanto |\n| condição | if, unless, provided that | se, a menos que, desde que |\n\n"
    "Despite e in spite of vêm com substantivo ou -ing (despite being heavier); although vem com oração ou adjetivo.",
    assunto=A_CON, dificuldade=1, **_t4,
)
TXT.mc(
    "Based on paragraph 4, a database running in a container without a persistent volume",
    "will lose its data when the container is removed.",
    ["will automatically copy its data to the host's kernel.",
     "cannot be used in development environments.",
     "becomes faster and keeps its data permanently.",
     "must run inside a virtual machine to start."],
    "Parágrafo 4: 'data is written to persistent volumes; otherwise, it will be lost when the container is removed.' Letra {G}.\n\n"
    "otherwise = caso contrário. Sem volume persistente, os dados moram na camada gravável do container, que some junto com ele.\n\n"
    "| Termo | Significado |\n|---|---|\n| persistent volume | armazenamento que sobrevive ao container |\n| ephemeral | efêmero, apagado com o container |\n"
    "| to remove a container | apagar o container (docker rm) |",
    assunto=A_INF, dificuldade=1, **_t4,
)
VOC.mc(
    "In paragraph 1, a “hypervisor” is",
    "the software layer that creates and runs virtual machines on a physical host.",
    ["a container that shares the kernel of the host.", "a network device that filters incoming traffic.",
     "a database that stores the configuration of each VM.", "the physical processor of the server."],
    "Hypervisor = monitor de máquinas virtuais. Letra {G}.\n\n"
    "| Tipo | Roda sobre | Exemplos |\n|---|---|---|\n| tipo 1 (bare metal) | direto no hardware | VMware ESXi, Microsoft Hyper-V, KVM, Xen |\n"
    "| tipo 2 (hosted) | sobre um SO | VirtualBox, VMware Workstation |\n\n"
    "Glossário de cloud do edital: VM, hypervisor, container, IaaS / PaaS / SaaS, scalability (escalabilidade), elasticity, region e availability zone.",
    assunto=A_GHW, dificuldade=1, **_t4,
)
GRA.mc(
    "The suffixes in the words “isolation” and “environments” (paragraph 1) are used to form",
    "nouns.",
    ["adverbs.", "adjectives.", "verbs in the past tense.", "comparative forms."],
    "-tion e -ment formam substantivos. Letra {G}.\n\n"
    "| Sufixo | Forma | Exemplo do texto / da área |\n|---|---|---|\n| -tion, -sion, -ment, -ness, -ity | substantivo | isolation, environment, availability |\n"
    "| -ly | advérbio | frequently, widely |\n| -ful, -less, -able, -ive, -al, -ent | adjetivo | reliable, physical, persistent |\n"
    "| -ed | passado / particípio | adopted, combined |\n| -er, -est | comparativo / superlativo | heavier, stronger |\n| -ize, -ify | verbo | virtualize, optimize, verify |\n\n"
    "No mesmo texto: heavier e stronger levam -er (comparativo); frequently e widely levam -ly (advérbio).",
    assunto=A_FORM, dificuldade=1, **_t4,
)

# ── Mensagens de erro, logs e comandos ───────────────────────────────────

CMD.mc(
    "A MySQL client displays the following message:\n\nERROR 1045 (28000): Access denied for user 'app'@'10.0.0.5' (using password: YES)\n\nThis message indicates that",
    "the server rejected the login of user app connecting from host 10.0.0.5, even though a password was supplied.",
    ["user app is logged in but has no permission to read a specific table.",
     "the password field was left empty when connecting.",
     "the server at 10.0.0.5 has run out of disk space.",
     "the database named app does not exist on the server."],
    "Leitura da mensagem: letra {G}.\n\n"
    "| Pedaço | Significado |\n|---|---|\n| Access denied for user | autenticação recusada |\n| 'app'@'10.0.0.5' | no MySQL a conta é usuário + host de ORIGEM |\n"
    "| using password: YES | uma senha foi enviada (NO = sem senha) |\n\n"
    "Causas típicas: senha errada, ou a conta existe só como 'app'@'localhost' e não para aquele host.\n\n"
    "A primeira errada é o erro de AUTORIZAÇÃO (o MySQL responde com 'command denied ... for table'), não de login. Banco inexistente dá 'Unknown database'.",
    assunto=A_ERR, dificuldade=2,
)
CMD.mc(
    "A PostgreSQL application logged the following error:\n\nERROR: duplicate key value violates unique constraint \"cliente_email_key\"\nDETAIL: Key (email)=(ana@exemplo.com) already exists.\n\nThe most accurate interpretation is that",
    "the INSERT or UPDATE failed because another row already has the e-mail ana@exemplo.com.",
    ["the table cliente was deleted while the command was running.",
     "the e-mail column accepts duplicates, but the key was too long.",
     "the user does not have permission to write to the table cliente.",
     "the database ran out of space to create a new index."],
    "Leitura: letra {G}.\n\n"
    "| Pedaço | Significado |\n|---|---|\n| duplicate key value | valor de chave repetido |\n| violates unique constraint | viola a restrição UNIQUE |\n"
    "| \"cliente_email_key\" | nome da restrição (padrão do PostgreSQL: tabela_coluna_key) |\n| DETAIL: Key (email)=(...) already exists | qual valor já existe |\n\n"
    "Correções possíveis: não inserir o repetido, ou usar INSERT ... ON CONFLICT (email) DO NOTHING / DO UPDATE.\n\n"
    "Permissão negada no PostgreSQL é 'permission denied for table cliente'.",
    assunto=A_ERR, dificuldade=2,
)
CMD.mc(
    "Consider the following line from a server log:\n\n2026-10-07 03:12:44 WARN [backup-job] Disk usage at 92% on /var/lib/mysql; job will be skipped if usage exceeds 95%.\n\nAccording to the log entry,",
    "the backup has not been skipped yet, but it will be if disk usage goes above 95%.",
    ["the backup failed because the disk is completely full.",
     "disk usage on /var/lib/mysql has reached 95%.",
     "the backup job was cancelled at 03:12:44.",
     "the warning refers to memory usage, not to disk usage."],
    "Leitura do log: letra {G}.\n\n"
    "| Pedaço | Significado |\n|---|---|\n| WARN | aviso — abaixo de ERROR e de FATAL/CRITICAL |\n| Disk usage at 92% | uso de disco em 92% |\n"
    "| will be skipped if usage exceeds 95% | SERÁ pulado SE passar de 95% (condição futura) |\n\n"
    "Níveis de log, do menos ao mais grave: TRACE, DEBUG, INFO, WARN, ERROR, FATAL.\n\n"
    "'skip' = pular; 'exceed' = exceder. Todas as erradas afirmam como fato o que o log põe como condição.",
    assunto=A_ERR, dificuldade=1,
)
CMD.mc(
    "In a Linux terminal, the command df -h is used to",
    "display used and available disk space per file system, in human-readable units such as M and G.",
    ["delete a directory and all of its files.", "list the processes that are running.",
     "change the permissions of a file.", "show the configuration of the network interfaces."],
    "df = disk free; -h = human-readable. Letra {G}.\n\n"
    "| Comando | Faz |\n|---|---|\n| df -h | espaço livre/usado por sistema de arquivos |\n| du -sh pasta | tamanho de uma pasta |\n"
    "| rm -r pasta | apaga recursivamente |\n| ps aux / top | processos |\n| chmod / chown | permissões / dono |\n| ip a (antigo: ifconfig) | interfaces de rede |\n\n"
    "No Windows, o equivalente de 'ver interfaces' é ipconfig.",
    assunto=A_CMD, dificuldade=1,
)
CMD.mc(
    "On Windows, the command ipconfig /all displays",
    "detailed network configuration of each adapter, such as IP address, DNS servers and physical (MAC) address.",
    ["the list of running processes and their memory usage.", "the result of a disk integrity check.",
     "the rules configured in the Windows firewall.", "the route that packets take to reach a remote host."],
    "ipconfig /all: letra {G}.\n\n"
    "| Windows | Linux | Faz |\n|---|---|---|\n| ipconfig /all | ip a | configuração de rede |\n| tasklist | ps | processos |\n"
    "| chkdsk | fsck | verifica o disco |\n| tracert | traceroute | rota até um host |\n| ping | ping | testa se o host responde |\n| netstat -an | ss -tan | conexões e portas |\n\n"
    "'Physical address' é o nome que o ipconfig dá ao endereço MAC.",
    assunto=A_CMD, dificuldade=1,
)

# ── Falsos cognatos ──────────────────────────────────────────────────────

VOC.mc(
    "Na frase “The migration will eventually be completed, after all tables are copied”, a palavra “eventually” significa",
    "por fim, depois de algum tempo.",
    ["eventualmente, isto é, talvez.", "imediatamente.", "ocasionalmente, de vez em quando.", "anteriormente."],
    "Falso cognato: eventually = finalmente, no fim das contas. Letra {G}.\n\n"
    "| Inglês | Significa | NÃO significa |\n|---|---|---|\n| eventually | por fim | eventualmente (= occasionally, possibly) |\n"
    "| actually | na verdade | atualmente (= currently, nowadays) |\n| pretend | fingir | pretender (= intend) |\n| library | biblioteca | livraria (= bookstore) |\n"
    "| push | empurrar (no Git: enviar commits) | puxar (= pull) |\n| data | dados | data do calendário (= date) |\n| support | dar suporte, aceitar | suportar no sentido de tolerar (= stand) |\n\n"
    "Na frase, 'after all tables are copied' confirma: acontece no fim.",
    assunto=A_FALSO, dificuldade=1,
)
VOC.mc(
    "Em “Actually, the index was never used by the query planner”, a palavra “Actually” pode ser traduzida por",
    "na verdade.",
    ["atualmente.", "atualizado.", "ativamente.", "neste exato momento."],
    "Actually = na verdade, de fato. Letra {G}.\n\n"
    "'Atualmente' em inglês é currently ou nowadays. 'Atualizado' é updated.\n\n"
    "A frase corrige uma suposição: na verdade, o otimizador nunca usou o índice — e então o índice só custa espaço e escrita.\n\n"
    "Outros falsos cognatos de TI: to realize (perceber, não realizar), to assist (ajudar), to attend (comparecer), to record (gravar).",
    assunto=A_FALSO, dificuldade=1,
)
VOC.mc(
    "Na frase “Do not pretend the backup worked; check the restore log”, o verbo “pretend” significa",
    "fingir.",
    ["pretender.", "planejar.", "prever.", "desejar."],
    "Pretend = fingir. Letra {G}.\n\n"
    "'Não finja que o backup funcionou; confira o log da restauração.' — backup que nunca foi restaurado em teste não é backup confiável.\n\n"
    "'Pretender' em inglês é to intend ou to plan. 'Prever' é to predict / to forecast.",
    assunto=A_FALSO, dificuldade=1,
)

# ── Glossário de TI ──────────────────────────────────────────────────────

VOC.mc(
    "In database terminology, a named set of SQL statements that is stored in the database and executed when it is explicitly called, possibly with parameters, is a",
    "stored procedure.",
    ["view.", "index.", "trigger.", "schema."],
    "Stored procedure = procedimento armazenado. Letra {G}.\n\n"
    "| Termo | O que é |\n|---|---|\n| stored procedure | código guardado no banco, executado quando CHAMADO (CALL / EXEC) |\n"
    "| trigger | código executado AUTOMATICAMENTE por um evento (INSERT, UPDATE, DELETE) |\n| view | consulta salva que funciona como tabela virtual |\n"
    "| index | estrutura que acelera buscas |\n| schema | agrupamento lógico de objetos (ou a estrutura do banco) |\n\n"
    "A diferença que a banca cobra: procedure é chamada; trigger dispara sozinho.",
    assunto=A_GBD, dificuldade=1,
)
VOC.mc(
    "In the sentence “A trigger fires before each INSERT on the orders table”, the verb “fires” means that the trigger",
    "is executed automatically when the event occurs.",
    ["is deleted from the database.", "must be called manually by the user.",
     "blocks all access to the orders table.", "is converted into a stored procedure."],
    "Fire, no contexto de trigger = disparar. Letra {G}.\n\n"
    "| Expressão | Sentido |\n|---|---|\n| the trigger fires | o gatilho dispara |\n| BEFORE INSERT | antes da inserção (pode alterar NEW) |\n"
    "| AFTER UPDATE | depois da atualização (auditoria) |\n| FOR EACH ROW | uma vez por linha afetada |\n\n"
    "Contraste com a procedure, que precisa ser chamada (called / executed).",
    assunto=A_GBD, dificuldade=1,
)
VOC.mc(
    "Which term refers to a logical subdivision of an IP network, such as 192.168.10.0/24?",
    "Subnet.",
    ["Router.", "Firewall.", "Proxy.", "Hub."],
    "Subnet = sub-rede. Letra {G}.\n\n"
    "| Termo | O que é |\n|---|---|\n| subnet | parte de uma rede IP definida pela máscara (/24 = 255.255.255.0) |\n| router | equipamento que encaminha pacotes entre redes |\n"
    "| firewall | filtra tráfego por regras |\n| proxy | intermediário entre cliente e servidor |\n| gateway | saída da rede (geralmente o roteador) |\n\n"
    "Glossário de redes do edital: LAN, WAN, IP address, subnet, routing, firewall.",
    assunto=A_GHW, dificuldade=1,
)
VOC.mc(
    "In programming, a loop is",
    "a structure that repeats a block of instructions while a condition holds or for each element of a collection.",
    ["a variable whose value cannot change.", "an error that stops the program.",
     "a function that returns no value.", "a comment ignored by the compiler."],
    "Loop = laço de repetição (for, while). Letra {G}.\n\n"
    "| Termo | Significado |\n|---|---|\n| loop | repetição |\n| variable / constant | variável / constante |\n| function / method | função / método |\n"
    "| bug | erro no código |\n| exception | erro tratável em tempo de execução |\n| comment | comentário |\n| API | interface para um programa usar outro |\n\n"
    "Infinite loop = laço que nunca termina.",
    assunto=A_GBD, dificuldade=1,
)
VOC.mc(
    "Malicious software that encrypts the victim's files and demands a payment in exchange for the decryption key is called",
    "ransomware.",
    ["spyware.", "worm.", "adware.", "rootkit."],
    "Ransom = resgate. Letra {G}.\n\n"
    "| Termo | O que faz |\n|---|---|\n| ransomware | sequestra dados (cifra) e pede resgate |\n| spyware | espiona e coleta informação |\n"
    "| worm | se replica sozinho pela rede |\n| adware | exibe propaganda |\n| rootkit | esconde a presença do invasor no sistema |\n| trojan | se disfarça de programa legítimo |\n\n"
    "Contra ransomware, o que salva o banco é backup offline e testado (a regra 3-2-1).",
    assunto=A_GSEG, dificuldade=1,
)
VOC.mc(
    "In information security, “authentication” is the process of",
    "verifying the identity of a user or system.",
    ["deciding which resources an identified user is allowed to access.",
     "recording every action performed by users.", "converting data into an unreadable format.",
     "making a copy of data to restore it later."],
    "Authentication = provar quem você é. Letra {G}.\n\n"
    "| Termo | Pergunta que responde |\n|---|---|\n| authentication (autenticação) | quem é você? |\n| authorization (autorização) | o que você pode fazer? |\n"
    "| accounting / auditing | o que você fez? |\n| encryption | cifrar |\n| backup | cópia de segurança |\n\n"
    "A primeira errada é a definição de authorization — o par que mais cai.",
    assunto=A_GSEG, dificuldade=1,
)

# ── Normas, RFCs, redação técnica e voz passiva ──────────────────────────

NOR.mc(
    "In RFC 2119, the phrase “MUST NOT” means that the described behavior is",
    "an absolute prohibition of the specification.",
    ["recommended, but optional.", "allowed only in test environments.",
     "truly optional.", "required in every implementation."],
    "MUST NOT = SHALL NOT = proibição absoluta. Letra {G}.\n\n"
    "| Palavra-chave | Sentido |\n|---|---|\n| MUST / REQUIRED / SHALL | obrigatório |\n| MUST NOT / SHALL NOT | proibido |\n"
    "| SHOULD / RECOMMENDED | recomendado |\n| SHOULD NOT / NOT RECOMMENDED | não recomendado |\n| MAY / OPTIONAL | opcional |\n\n"
    "A RFC 2119 define essas palavras para que as outras RFCs (HTTP, TLS, SMTP) as usem com sentido exato, sempre em maiúsculas.",
    assunto=A_RFC, dificuldade=1,
)
NOR.mc(
    "The NIST Cybersecurity Framework 2.0 organizes cybersecurity outcomes into six functions: Govern, Identify, Protect, Detect, Respond and Recover. Restoring the company's databases from backups after a ransomware attack belongs mainly to the function",
    "Recover.",
    ["Identify.", "Detect.", "Govern.", "Protect."],
    "Recover = restaurar as operações depois do incidente. Letra {G}.\n\n"
    "| Função | Exemplo em banco de dados |\n|---|---|\n| Govern | política e papéis de segurança |\n| Identify | inventário de bancos e dados sensíveis |\n"
    "| Protect | controle de acesso, criptografia, backup |\n| Detect | auditoria, alerta de acesso anômalo |\n| Respond | conter o ataque, isolar o servidor |\n| Recover | restaurar do backup, voltar a operar |\n\n"
    "Fazer o backup é Protect; usar o backup para voltar é Recover.",
    assunto=A_NORMA, dificuldade=2,
)
NOR.mc(
    "ISO/IEC 27001 is an international standard that specifies requirements for",
    "establishing, implementing, maintaining and continually improving an information security management system (ISMS).",
    ["designing normalized relational databases.", "measuring software quality in agile projects.",
     "managing IT services, such as the service desk.", "protecting personal data under Brazilian law."],
    "ISO/IEC 27001 = requisitos de um SGSI (ISMS em inglês). Letra {G}.\n\n"
    "| Norma / lei | Assunto |\n|---|---|\n| ISO/IEC 27001 | requisitos do sistema de gestão de segurança da informação (certificável) |\n"
    "| ISO/IEC 27002 | guia de controles de segurança |\n| ISO/IEC 20000 | gestão de serviços de TI |\n| ISO/IEC 25010 | qualidade de software |\n| LGPD (Lei 13.709/2018) | proteção de dados pessoais no Brasil |\n\n"
    "'continually improving' remete ao ciclo PDCA (Plan-Do-Check-Act).",
    assunto=A_NORMA, dificuldade=1,
)
NOR.mc(
    "Which sentence is the most appropriate to open a formal e-mail reporting an incident to a software vendor?",
    "I am writing to report a failure in the replication service that began at 2:00 a.m. today.",
    ["Hey guys, your stuff broke again!!!", "Replication dead. Fix it ASAP.",
     "As you probably know, nothing in your product works.", "I wanna tell you that the system is kinda down."],
    "Registro formal: letra {G}.\n\n"
    "A abertura formal diz o motivo do e-mail logo de cara ('I am writing to...'), com fato, hora e serviço afetado.\n\n"
    "| Informal | Formal |\n|---|---|\n| Hey guys | Dear Sir or Madam / Dear support team |\n| wanna, kinda | want to, somewhat |\n"
    "| ASAP | at your earliest convenience / as soon as possible |\n| Fix it. | Could you please investigate...? |\n| Thanks! | Kind regards / Best regards |\n\n"
    "Fórmulas úteis: 'Please find attached the log file.' / 'I look forward to your reply.'",
    assunto=A_RED, dificuldade=1,
)
NOR.mc(
    "In a technical report, which sentence is written in the passive voice?",
    "The data is replicated to two regions every hour.",
    ["The system replicates the data to two regions every hour.",
     "We replicate the data to two regions every hour.",
     "Replicate the data to two regions every hour.",
     "The administrator should replicate the data every hour."],
    "Voz passiva = to be + particípio (is replicated). Letra {G}.\n\n"
    "| Frase | Voz |\n|---|---|\n| The data is replicated... | passiva: o foco é no dado, não em quem replica |\n| The system replicates... | ativa |\n"
    "| Replicate the data... | imperativo (instrução) |\n| should replicate | ativa com modal |\n\n"
    "Documentação técnica usa muito a passiva: 'The file is created automatically', 'Errors are logged to...'. Passiva com modal: 'Backups must be tested'.",
    assunto=A_MOD, dificuldade=1,
)
