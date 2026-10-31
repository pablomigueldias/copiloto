from base import AF3, AF3b, Topico

T = Topico("Conceitos, arquitetura e tipos de SGBD", 1, "bd-conceitos-arquitetura",
           "Banco de dados: conceitos, arquitetura, modelos de dados e tipos de SGBD (SQL Server, MySQL ou similares)")

T.mc(
    "Na arquitetura de três esquemas (ANSI/SPARC) de um sistema de banco de dados, o nível que descreve a estrutura de armazenamento físico do banco, incluindo detalhes de organização dos arquivos e caminhos de acesso, é o nível",
    "interno.",
    ["externo.", "conceitual.", "de visão.", "de aplicação."],
    "Qual nível da arquitetura ANSI/SPARC descreve o armazenamento físico? Letra {G}: o nível INTERNO.\n\n"
    "| Nível | Descreve | Quem enxerga |\n|---|---|---|\n"
    "| externo (visão) | a parte do banco que interessa a cada grupo de usuários | usuário, aplicação |\n"
    "| conceitual (lógico) | a estrutura do banco inteiro: entidades, tipos, relacionamentos, restrições — sem detalhe físico | projetista, DBA |\n"
    "| interno (físico) | como os dados ficam gravados: arquivos, páginas, índices, caminhos de acesso | SGBD, DBA |\n\n"
    "'Visão' é outro nome do nível externo; 'de aplicação' não é nível da arquitetura.\n\n"
    "Atalho: externo = o que EU vejo; conceitual = o que EXISTE; interno = como está GRAVADO.",
    dificuldade=1,
)
T.mc(
    "Um DBA criou um novo índice e moveu os arquivos de dados de uma tabela para outro disco, sem que fosse preciso alterar o esquema conceitual nem as aplicações que acessam o banco. Esse cenário ilustra a",
    "independência física de dados.",
    ["independência lógica de dados.", "redundância controlada de dados.",
     "integridade referencial.", "atomicidade das transações."],
    "Mudou o armazenamento, e o esquema conceitual e as aplicações não perceberam. Letra {G}: independência FÍSICA.\n\n"
    "| Independência | Muda-se | Sem precisar mudar |\n|---|---|---|\n"
    "| física | o nível interno: índice, arquivo, disco, organização | o esquema conceitual |\n"
    "| lógica | o esquema conceitual: nova coluna, nova tabela | os esquemas externos e as aplicações |\n\n"
    "A independência lógica é a mais difícil de conseguir, porque as aplicações dependem diretamente da estrutura lógica. "
    "A física é a mais comum: criar índice é rotina e nenhum SELECT precisa ser reescrito.\n\n"
    "Atalho: mexeu em disco, arquivo ou índice → física. Mexeu em tabela ou coluna → lógica.",
)
T.mc(
    "Em um SGBD relacional, o componente que armazena as descrições das tabelas, colunas, tipos de dados, restrições, índices e permissões — isto é, os metadados do banco — é o",
    "catálogo do sistema (dicionário de dados).",
    ["log de transações.", "buffer de dados.", "otimizador de consultas.", "gerenciador de bloqueios."],
    "Onde ficam os metadados? Letra {G}: no catálogo do sistema, também chamado de dicionário de dados.\n\n"
    "O banco é autodescritivo: a definição da estrutura fica dentro dele, consultável por SQL. "
    "No padrão SQL isso aparece como INFORMATION_SCHEMA; no SQL Server, também nas views sys.tables, sys.columns; no PostgreSQL, em pg_catalog.\n\n"
    "| Componente | Função |\n|---|---|\n"
    "| log de transações | registra as alterações para desfazer e refazer (recuperação) |\n"
    "| buffer | mantém páginas de dados em memória |\n"
    "| otimizador | escolhe o plano de execução da consulta |\n"
    "| gerenciador de bloqueios | controla a concorrência entre transações |",
    dificuldade=1,
)
T.mc(
    "Em comparação com o armazenamento de dados em arquivos isolados por aplicação, a abordagem de banco de dados NÃO oferece, como vantagem,",
    "a eliminação da necessidade de cópias de segurança, já que o SGBD impede a perda de dados.",
    ["o controle da redundância de dados.", "o compartilhamento de dados entre vários usuários e aplicações.",
     "a imposição de restrições de integridade.", "a restrição de acesso não autorizado."],
    "Qual NÃO é vantagem da abordagem de banco de dados? Letra {G}.\n\n"
    "Nenhum SGBD dispensa backup. Ele protege contra falha de transação e queda de energia (por meio do log), mas não contra disco destruído, "
    "exclusão acidental, ransomware ou incêndio. Backup continua sendo obrigação do DBA.\n\n"
    "As outras quatro são as vantagens clássicas (Elmasri e Navathe): controle de redundância, compartilhamento, restrições de integridade, "
    "controle de acesso — e ainda backup e recuperação como SERVIÇO oferecido pelo SGBD, o que é diferente de dispensá-lo.\n\n"
    "Atalho: em questão de NÃO, a alternativa absoluta ('elimina a necessidade', 'impede qualquer') costuma ser a errada.",
    formato="negativa", dificuldade=1,
)
T.mc(
    "Ao receber uma consulta SQL, o SGBD analisa diferentes formas de executá-la — ordem das junções, uso ou não de índices, algoritmos de junção — e escolhe a de menor custo estimado. O componente responsável por essa escolha é o",
    "otimizador de consultas.",
    ["gerenciador de recuperação.", "catálogo do sistema.", "pré-compilador de DML embutida.", "gerenciador de buffer."],
    "Quem escolhe COMO executar a consulta? Letra {G}: o otimizador de consultas.\n\n"
    "SQL é declarativa: você diz O QUE quer, e o otimizador decide o caminho. O resultado da decisão é o PLANO DE EXECUÇÃO — "
    "o mesmo que o DBA lê com EXPLAIN (MySQL, PostgreSQL) ou com o plano de execução do SQL Server Management Studio.\n\n"
    "Os otimizadores modernos são baseados em CUSTO e usam as ESTATÍSTICAS das tabelas (quantas linhas, distribuição dos valores). "
    "Por isso estatística desatualizada gera plano ruim — assunto de tuning.",
)
T.mc(
    "A linguagem procedural estendida do Microsoft SQL Server, usada para escrever stored procedures, funções e triggers com variáveis, laços e tratamento de erros, é a",
    "Transact-SQL (T-SQL).",
    ["PL/SQL.", "PL/pgSQL.", "SQL/PSM do MySQL, chamada MyPL.", "SQL*Plus."],
    "Dialeto procedural do SQL Server: letra {G}, Transact-SQL.\n\n"
    "| SGBD | Linguagem procedural |\n|---|---|\n"
    "| Microsoft SQL Server | Transact-SQL (T-SQL) |\n"
    "| Oracle | PL/SQL |\n"
    "| PostgreSQL | PL/pgSQL |\n"
    "| MySQL / MariaDB | segue o padrão SQL/PSM, sem nome comercial próprio |\n\n"
    "'MyPL' não existe. SQL*Plus é a ferramenta de linha de comando do Oracle, não uma linguagem.\n\n"
    "Pista de T-SQL em questão: variáveis com @ (DECLARE @total INT), TRY...CATCH, TOP, IDENTITY.",
    dificuldade=1,
)
T.mc(
    "No MySQL, o mecanismo de armazenamento (storage engine) padrão nas versões atuais, que oferece suporte a transações ACID, bloqueio em nível de linha e chaves estrangeiras, é o",
    "InnoDB.",
    ["MyISAM.", "MEMORY.", "CSV.", "ARCHIVE."],
    "Engine do MySQL com transação e chave estrangeira: letra {G}, InnoDB — o padrão desde o MySQL 5.5.\n\n"
    "| Engine | Transação | FK | Bloqueio | Uso |\n|---|---|---|---|---|\n"
    "| InnoDB | sim | sim | linha | padrão, uso geral |\n"
    "| MyISAM | não | não | tabela inteira | legado, leitura intensa |\n"
    "| MEMORY | não | não | tabela | dados temporários em RAM, somem ao reiniciar |\n"
    "| CSV / ARCHIVE | não | não | — | troca de arquivo / histórico compactado |\n\n"
    "Pegadinha frequente: MyISAM foi o padrão antigo e NÃO tem transação nem FK. Uma tabela MyISAM ignora a cláusula FOREIGN KEY em silêncio.",
)
T.mc(
    "No Microsoft SQL Server, o banco de dados de sistema usado como modelo para a criação de todo novo banco de dados da instância — de modo que objetos e configurações nele definidos são copiados para os bancos criados depois — é o",
    "model.",
    ["master.", "msdb.", "tempdb.", "resource."],
    "Banco que serve de molde para os novos: letra {G}, model.\n\n"
    "| Banco de sistema | Guarda |\n|---|---|\n"
    "| master | configuração da instância, logins, lista de bancos — sem ele a instância não sobe |\n"
    "| model | o modelo copiado a cada CREATE DATABASE |\n"
    "| msdb | jobs e alertas do SQL Server Agent, histórico de backup e restore |\n"
    "| tempdb | objetos temporários (#tabelas, ordenações); é recriado a cada reinício |\n"
    "| resource | objetos de sistema, somente leitura, oculto |\n\n"
    "Atalho: master manda, model molda, msdb agenda, tempdb é descartável.",
)
T.fixa(
    "Sobre os bancos de dados de sistema do Microsoft SQL Server, analise as afirmativas a seguir.",
    AF3, "C",
    "Quais afirmativas sobre os bancos de sistema estão certas? Letra C: I e II.\n\n"
    "I — certa. O tempdb é recriado do zero a cada reinício do serviço; não faz sentido fazer backup dele.\n\n"
    "II — certa. O msdb guarda os jobs do SQL Server Agent e o histórico de backup e restore — por isso é ele que se consulta para saber quando foi o último backup.\n\n"
    "III — errada. Sem o master a instância nem inicia: ele guarda a configuração, os logins e a localização de todos os bancos. Ele deve entrar na rotina de backup.",
    afirmacoes=[
        "O tempdb é recriado a cada reinicialização da instância, e os objetos temporários nele criados não sobrevivem ao reinício.",
        "O msdb armazena, entre outras informações, os jobs do SQL Server Agent e o histórico de operações de backup e restauração.",
        "O master pode ser excluído sem impacto para a instância, pois guarda apenas cópias de segurança dos demais bancos.",
    ],
    formato="afirmacoes",
)
T.fixa(
    "Uma tabela de um banco de dados relacional possui 7 colunas e armazena 1.250 linhas. Na terminologia do modelo relacional, o grau e a cardinalidade dessa relação são, respectivamente,",
    ["7 e 1.250.", "1.250 e 7.", "7 e 7.", "1.250 e 1.250.", "8.750 e 7."],
    "A",
    "Grau e cardinalidade da relação com 7 colunas e 1.250 linhas: letra A, 7 e 1.250.\n\n"
    "| Termo do modelo relacional | Equivale a |\n|---|---|\n"
    "| relação | tabela |\n| tupla | linha |\n| atributo | coluna |\n"
    "| GRAU | número de ATRIBUTOS (colunas) |\n| CARDINALIDADE | número de TUPLAS (linhas) |\n"
    "| domínio | conjunto de valores permitidos para um atributo |\n\n"
    "B inverte os dois — é a pegadinha. 8.750 é o número de células, que não tem nome no modelo.\n\n"
    "Atalho: Grau = Grade de colunas; Cardinalidade = Contagem de linhas.\n\n"
    "Cuidado: 'cardinalidade' também se usa no MER para a razão do relacionamento (1:1, 1:N, N:N). Contexto de TABELA → número de linhas.",
    formato="calculo", dificuldade=1,
)
T.mc(
    "Assinale a alternativa que associa corretamente cada categoria de banco de dados NoSQL a um produto representativo dela.",
    "Chave-valor: Redis; documentos: MongoDB; família de colunas: Cassandra; grafos: Neo4j.",
    ["Chave-valor: MongoDB; documentos: Redis; família de colunas: Neo4j; grafos: Cassandra.",
     "Chave-valor: Cassandra; documentos: Neo4j; família de colunas: Redis; grafos: MongoDB.",
     "Chave-valor: Neo4j; documentos: Cassandra; família de colunas: MongoDB; grafos: Redis.",
     "Chave-valor: Redis; documentos: Cassandra; família de colunas: MongoDB; grafos: Neo4j."],
    "Associação NoSQL × produto: letra {G}.\n\n"
    "| Categoria | Produto típico | Bom para |\n|---|---|---|\n"
    "| chave-valor | Redis, DynamoDB | cache, sessão, busca por chave exata |\n"
    "| documentos | MongoDB, CouchDB | registros JSON de estrutura variável |\n"
    "| família de colunas | Cassandra, HBase | escrita massiva, tabelas largas e esparsas |\n"
    "| grafos | Neo4j | relacionamentos percorridos com frequência |\n\n"
    "A última alternativa errada acerta Redis e Neo4j e troca só os dois do meio — é a armadilha de quem decorou metade.",
)
T.mc(
    "Segundo o teorema CAP, aplicado a sistemas de banco de dados distribuídos, quando ocorre uma partição na rede o sistema",
    "precisa escolher entre manter a consistência e manter a disponibilidade.",
    ["consegue garantir simultaneamente consistência, disponibilidade e tolerância a partição.",
     "deixa de ser tolerante a partição, mas mantém consistência e disponibilidade.",
     "perde automaticamente as propriedades ACID de todas as transações já confirmadas.",
     "passa a operar apenas em modo somente leitura, por exigência do teorema."],
    "Teorema CAP com partição na rede: letra {G}.\n\n"
    "C = Consistency (todos os nós veem o mesmo dado), A = Availability (todo pedido recebe resposta), P = Partition tolerance (o sistema sobrevive a falha de comunicação entre nós).\n\n"
    "Num sistema distribuído a partição VAI acontecer, então P não é opcional. Quando ela ocorre, ou o sistema recusa responder até sincronizar (fica consistente, perde disponibilidade — CP), "
    "ou responde com o dado que tem (fica disponível, pode devolver dado velho — AP).\n\n"
    "A primeira alternativa errada é a negação do teorema. A que fala em 'somente leitura' inventa uma regra; isso seria só uma das estratégias possíveis.\n\n"
    "Exemplos comuns em prova: MongoDB e HBase costumam ser citados como CP; Cassandra e DynamoDB como AP.",
    dificuldade=3,
)
T.mc(
    "Muitos bancos de dados NoSQL distribuídos adotam o modelo BASE em lugar das propriedades ACID. Nesse modelo, a característica segundo a qual as réplicas podem divergir temporariamente, mas convergem para o mesmo valor se não houver novas atualizações, é chamada de",
    "consistência eventual.",
    ["atomicidade parcial.", "isolamento serializável.", "durabilidade adiada.", "consistência forte."],
    "Réplicas que divergem e depois convergem: letra {G}, consistência eventual (o E de BASE).\n\n"
    "BASE = Basically Available, Soft state, Eventual consistency. É a resposta 'AP' do teorema CAP: prioriza responder sempre, aceitando que uma leitura logo após a escrita veja o valor antigo.\n\n"
    "| ACID (relacional) | BASE (muitos NoSQL) |\n|---|---|\n"
    "| consistência forte: leu, está atualizado | consistência eventual |\n| pessimista: bloqueia | otimista: replica depois |\n"
    "| escala vertical | escala horizontal |\n\n"
    "Exemplo do dia a dia: o número de curtidas de uma postagem pode aparecer diferente em dois celulares por alguns segundos.",
)
T.mc(
    "Considere dois ambientes de banco de dados de uma empresa: o primeiro registra as vendas no caixa, com milhares de pequenas transações por minuto; o segundo atende à diretoria, com consultas que agregam anos de histórico de vendas. Esses ambientes correspondem, respectivamente, a sistemas",
    "OLTP e OLAP.",
    ["OLAP e OLTP.", "OLTP e OLTP, diferindo apenas no volume de dados.", "ETL e OLTP.", "OLAP e ETL."],
    "Caixa registrando vendas × diretoria analisando histórico: letra {G}, OLTP e OLAP.\n\n"
    "| | OLTP (transacional) | OLAP (analítico) |\n|---|---|---|\n"
    "| operação típica | INSERT, UPDATE, SELECT de poucas linhas | SELECT com SUM, GROUP BY sobre milhões |\n"
    "| dados | atuais | históricos |\n| modelagem | normalizada (3FN) | dimensional (estrela, floco de neve) |\n"
    "| usuários | muitos, operacionais | poucos, gerenciais |\n| prioridade | tempo de resposta e integridade | velocidade de consulta agregada |\n\n"
    "ETL não é tipo de sistema, é o processo que leva dados do OLTP para o data warehouse do OLAP.\n\n"
    "Atalho: T de Transação (balcão); A de Análise (diretoria).",
    dificuldade=1,
)
T.mc(
    "As portas TCP padrão do Microsoft SQL Server (instância padrão), do MySQL e do PostgreSQL são, respectivamente,",
    "1433, 3306 e 5432.",
    ["3306, 1433 e 5432.", "1521, 3306 e 5432.", "1433, 5432 e 3306.", "5432, 1433 e 3306."],
    "Portas padrão: letra {G} — SQL Server 1433, MySQL 3306, PostgreSQL 5432.\n\n"
    "| SGBD | Porta padrão |\n|---|---|\n| SQL Server (instância padrão) | 1433 TCP; o SQL Server Browser usa 1434 UDP |\n"
    "| MySQL / MariaDB | 3306 |\n| PostgreSQL | 5432 |\n| Oracle (listener) | 1521 |\n| MongoDB | 27017 |\n\n"
    "1521 é a do Oracle — distrator clássico.\n\n"
    "Instância NOMEADA do SQL Server usa porta dinâmica por padrão, descoberta via SQL Server Browser — por isso firewall de SQL Server às vezes libera também a 1434/UDP.",
    dificuldade=1,
)
T.mc(
    "Em uma organização, o profissional responsável por autorizar o acesso ao banco de dados, coordenar e monitorar seu uso, garantir backup e recuperação e adquirir recursos de software e hardware necessários ao SGBD é o",
    "administrador de banco de dados (DBA).",
    ["projetista de banco de dados.", "analista de sistemas.", "usuário final paramétrico.", "programador de aplicações."],
    "Quem autoriza acesso, monitora, faz backup e cuida dos recursos? Letra {G}: o DBA.\n\n"
    "| Papel | Responsabilidade |\n|---|---|\n"
    "| DBA | acesso e permissões, desempenho, backup e recuperação, instalação e atualização do SGBD |\n"
    "| projetista de BD | identificar os dados e modelar a estrutura (MER, esquema) antes de o banco existir |\n"
    "| analista de sistemas | levantar requisitos dos usuários e especificar as transações |\n"
    "| programador | implementar as aplicações que usam o banco |\n"
    "| usuário paramétrico | usa transações prontas (o caixa de banco, o atendente) |\n\n"
    "É exatamente o recorte do cargo do edital: administração, tuning, backup e segurança são o dia a dia do DBA.",
    dificuldade=1,
)
T.mc(
    "Sobre visões (views) em bancos de dados relacionais, é correto afirmar que uma visão comum",
    "é uma tabela virtual definida por uma consulta, cujo resultado é obtido das tabelas-base no momento em que a visão é consultada.",
    ["armazena fisicamente uma cópia dos dados das tabelas-base, atualizada a cada COMMIT.",
     "não pode ser usada para restringir o acesso de usuários a determinadas colunas.",
     "só pode ser criada sobre uma única tabela, sem junções.",
     "elimina a necessidade de índices nas tabelas-base."],
    "O que é uma view comum? Letra {G}: tabela virtual; guarda a CONSULTA, não os dados.\n\n"
    "Cada vez que alguém faz SELECT na view, o SGBD executa a consulta que a define sobre as tabelas-base.\n\n"
    "Quem armazena fisicamente o resultado é a VISÃO MATERIALIZADA (PostgreSQL, Oracle; no SQL Server, 'indexed view') — e ela não se atualiza 'a cada COMMIT' por definição; depende de REFRESH ou de manutenção automática.\n\n"
    "Views servem justamente para SEGURANÇA: dá-se GRANT SELECT na view que mostra só nome e cidade, e não na tabela que tem salário. "
    "Podem ter junções, agregações e subconsultas. E não dispensam índice — a consulta da view usa os índices das tabelas-base.",
)
T.mc(
    "Uma empresa precisa de uma edição gratuita do Microsoft SQL Server para colocar em produção um sistema pequeno. Considerando as edições do produto, a escolha adequada é a edição",
    "Express, que é gratuita e pode ser usada em produção, mas tem limites, como o tamanho máximo de 10 GB por banco de dados.",
    ["Developer, que é gratuita e tem todos os recursos da Enterprise, sendo indicada para produção.",
     "Enterprise, que é gratuita para órgãos públicos.",
     "Standard, que é gratuita para até 50 usuários.",
     "Express, que é gratuita e não tem limite de tamanho de banco nem de memória."],
    "Edição gratuita do SQL Server para PRODUÇÃO: letra {G}, Express — com limite de 10 GB por banco (além de limite de CPU e memória).\n\n"
    "| Edição | Custo | Produção? |\n|---|---|---|\n"
    "| Express | gratuita | sim, com limites (10 GB por banco) |\n"
    "| Developer | gratuita | NÃO — só desenvolvimento e teste, apesar de ter todos os recursos da Enterprise |\n"
    "| Standard | paga | sim |\n| Enterprise | paga | sim, todos os recursos |\n\n"
    "A pegadinha é a Developer: é gratuita e completa, mas a licença proíbe produção. A outra Express errada nega o limite que a define.",
)
T.mc(
    "O modelo de dados em que os registros são organizados em uma estrutura de árvore, na qual cada registro filho possui exatamente um registro pai, é o modelo",
    "hierárquico.",
    ["em rede.", "relacional.", "orientado a objetos.", "de documentos."],
    "Árvore, um pai por filho: letra {G}, modelo hierárquico (o IMS da IBM é o exemplo histórico).\n\n"
    "| Modelo | Estrutura |\n|---|---|\n"
    "| hierárquico | árvore: cada filho tem UM pai |\n"
    "| em rede (CODASYL) | grafo: um registro pode ter VÁRIOS pais |\n"
    "| relacional | tabelas ligadas por valores (chaves), sem ponteiros físicos |\n"
    "| orientado a objetos | objetos com atributos, métodos e herança |\n"
    "| documentos (NoSQL) | documentos JSON aninhados |\n\n"
    "A diferença entre hierárquico e rede é o número de pais. Os dois navegam por ponteiros; o relacional liga pelo VALOR da chave — por isso é independente do caminho de acesso.",
    dificuldade=1,
)
T.fixa(
    "Analise as afirmativas a seguir sobre sistemas gerenciadores de banco de dados.",
    AF3b, "C",
    "Quais estão certas? Letra C: I e III.\n\n"
    "I — certa. MySQL e PostgreSQL são livres; o SQL Server é proprietário da Microsoft (com edições gratuitas, mas licença proprietária).\n\n"
    "II — errada. Desde 2017 o SQL Server roda também em Linux e em contêineres Docker.\n\n"
    "III — certa. SQL é padrão ISO/ANSI, mas cada SGBD tem extensões próprias: TOP no SQL Server e LIMIT no MySQL e PostgreSQL para limitar linhas; "
    "IDENTITY no SQL Server e AUTO_INCREMENT no MySQL para chave automática.",
    afirmacoes=[
        "MySQL e PostgreSQL são SGBDs de código aberto, enquanto o Microsoft SQL Server é um produto proprietário.",
        "O Microsoft SQL Server só pode ser instalado em sistemas operacionais Windows.",
        "Embora a SQL seja padronizada, cada SGBD possui extensões próprias, como TOP no SQL Server e LIMIT no MySQL para limitar o número de linhas retornadas.",
    ],
    formato="afirmacoes",
)
