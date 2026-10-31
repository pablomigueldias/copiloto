from base import AF3, AF3b, Topico

T = Topico("Administração: instalação, usuários e integridade", 3, "bd-administracao",
           "Administração de banco de dados: instalação, configuração, gerenciamento de usuários e permissões, integridade e consistência de dados")

T.mc(
    "Durante a instalação do Microsoft SQL Server, o administrador deve escolher o modo de autenticação. Ao selecionar o modo misto (Mixed Mode), a instância passa a aceitar",
    "tanto a autenticação do Windows quanto logins do próprio SQL Server com usuário e senha, sendo necessário definir a senha da conta sa.",
    ["somente logins do SQL Server, desativando a autenticação do Windows.",
     "somente a autenticação do Windows, com a conta sa desabilitada permanentemente.",
     "autenticação apenas por certificados digitais emitidos pela Microsoft.",
     "conexões sem senha a partir da rede local."],
    "Modo misto no SQL Server: letra {G}.\n\n"
    "| Modo | Aceita |\n|---|---|\n"
    "| Windows Authentication (padrão, recomendado) | só contas do Windows / Active Directory |\n"
    "| Mixed Mode | contas do Windows E logins SQL (usuário e senha guardados no SQL Server) |\n\n"
    "No modo misto o instalador exige senha forte para a conta 'sa' (system administrator), que é membro de sysadmin. "
    "Boa prática: desabilitar ou renomear o 'sa' e usar logins nominais — é o primeiro alvo de ataque de força bruta.",
    dificuldade=1,
)
T.mc(
    "No Microsoft SQL Server, a diferença entre login e usuário (user) é que",
    "o login é a identidade no nível da instância (servidor), e o usuário é a identidade dentro de um banco de dados, normalmente mapeada a um login.",
    ["login e usuário são sinônimos, usados indistintamente em T-SQL.",
     "o usuário é criado no nível da instância, e o login, dentro de cada banco de dados.",
     "o login só existe na autenticação do Windows, e o usuário só na autenticação SQL.",
     "o usuário dá acesso a todos os bancos da instância, e o login a apenas um."],
    "Login × usuário no SQL Server: letra {G}.\n\n"
    "Duas portas, em sequência:\n\n"
    "1. LOGIN (CREATE LOGIN) — entra na INSTÂNCIA. Fica no master.\n\n"
    "2. USER (CREATE USER ... FOR LOGIN ...) — entra num BANCO específico. Fica no próprio banco.\n\n"
    "CREATE LOGIN ana WITH PASSWORD = 'S3nh@Forte!';\nUSE vendas;\nCREATE USER ana FOR LOGIN ana;\nALTER ROLE db_datareader ADD MEMBER ana;\n\n"
    "Com login e sem user, Ana conecta no servidor mas recebe erro ao abrir o banco vendas. Permissões em tabelas são dadas ao USER, dentro do banco.",
)
T.mc(
    "O comando SQL que concede ao usuário analista a permissão de consultar e inserir dados na tabela VENDAS é",
    "GRANT SELECT, INSERT ON VENDAS TO analista;",
    ["GRANT analista ON VENDAS TO SELECT, INSERT;",
     "REVOKE SELECT, INSERT ON VENDAS FROM analista;",
     "ALLOW SELECT, INSERT ON VENDAS FOR analista;",
     "GRANT SELECT, INSERT TO VENDAS ON analista;"],
    "Sintaxe do GRANT: letra {G}.\n\n"
    "GRANT <privilégios> ON <objeto> TO <usuário ou papel>;\nREVOKE <privilégios> ON <objeto> FROM <usuário ou papel>;\n\n"
    "Repare nas preposições: GRANT ... TO, REVOKE ... FROM. ALLOW não existe em SQL. A alternativa com REVOKE faz o contrário (retira).\n\n"
    "GRANT e REVOKE formam a DCL (Data Control Language). No SQL Server existe ainda o DENY.",
    dificuldade=1,
)
T.mc(
    "O DBA executou: GRANT SELECT ON CLIENTES TO maria WITH GRANT OPTION; Com isso, a usuária maria",
    "pode consultar a tabela CLIENTES e também conceder a permissão SELECT sobre ela a outros usuários.",
    ["pode consultar, alterar e excluir dados de CLIENTES.",
     "recebe todos os privilégios de administrador do banco.",
     "pode consultar CLIENTES, mas não pode repassar essa permissão.",
     "passa a ser dona (owner) da tabela CLIENTES."],
    "WITH GRANT OPTION: letra {G}.\n\n"
    "Quem recebe o privilégio com GRANT OPTION pode REPASSÁ-LO. Só o privilégio recebido — Maria repassa SELECT, não UPDATE.\n\n"
    "O cuidado vem na revogação: no padrão SQL, REVOKE ... CASCADE retira o privilégio de Maria e de todos a quem ela repassou; "
    "REVOKE GRANT OPTION FOR ... tira só o direito de repassar. No SQL Server, revogar de quem já repassou exige CASCADE, senão o comando falha.\n\n"
    "Pelo princípio do menor privilégio, GRANT OPTION deve ser exceção.",
)
T.mc(
    "No Microsoft SQL Server, um usuário pertence a um papel que recebeu GRANT SELECT na tabela SALARIOS, mas o próprio usuário recebeu DENY SELECT nessa mesma tabela. Ao tentar consultá-la, ele",
    "terá o acesso negado, pois DENY prevalece sobre GRANT.",
    ["conseguirá consultar, pois a permissão do papel prevalece sobre a individual.",
     "conseguirá consultar, pois GRANT sempre prevalece sobre DENY.",
     "conseguirá consultar apenas as linhas inseridas por ele.",
     "provocará erro de sintaxe, pois GRANT e DENY não podem coexistir no mesmo objeto."],
    "GRANT pelo papel + DENY individual: letra {G}, acesso negado.\n\n"
    "No SQL Server existem três estados de permissão:\n\n"
    "| Comando | Efeito |\n|---|---|\n| GRANT | concede |\n| REVOKE | remove o GRANT ou o DENY (volta ao neutro) |\n| DENY | proíbe explicitamente, e vence qualquer GRANT, venha de onde vier |\n\n"
    "Isso permite: 'todo o papel financeiro lê tudo, menos o estagiário na tabela de salários'.\n\n"
    "Exceção: membros de sysadmin ignoram DENY.\n\n"
    "Cuidado: REVOKE ≠ DENY. REVOKE só desfaz; se o usuário ainda receber GRANT por um papel, continua acessando.",
)
T.mc(
    "No Microsoft SQL Server, para permitir que um usuário leia os dados de todas as tabelas de um banco sem poder alterá-los, o DBA pode incluí-lo no papel fixo de banco de dados",
    "db_datareader.",
    ["db_datawriter.", "db_owner.", "db_ddladmin.", "sysadmin."],
    "Ler todas as tabelas sem alterar: letra {G}, db_datareader.\n\n"
    "| Papel fixo | Nível | Permite |\n|---|---|---|\n"
    "| db_datareader | banco | SELECT em todas as tabelas e views |\n"
    "| db_datawriter | banco | INSERT, UPDATE e DELETE em todas as tabelas |\n"
    "| db_ddladmin | banco | DDL: criar e alterar objetos |\n"
    "| db_owner | banco | tudo no banco |\n"
    "| sysadmin | servidor (instância) | tudo na instância |\n\n"
    "Pegadinha de nível: sysadmin é papel de SERVIDOR, não de banco.",
    dificuldade=1,
)
T.mc(
    "No MySQL, o comando que cria um usuário chamado relatorio que só pode se conectar a partir da própria máquina do servidor é",
    "CREATE USER 'relatorio'@'localhost' IDENTIFIED BY 'senha_forte';",
    ["CREATE USER 'relatorio'@'%' IDENTIFIED BY 'senha_forte';",
     "CREATE LOGIN relatorio WITH PASSWORD = 'senha_forte';",
     "CREATE ROLE relatorio FROM 'localhost';",
     "ADD USER relatorio HOST localhost PASSWORD 'senha_forte';"],
    "Usuário do MySQL restrito à própria máquina: letra {G}.\n\n"
    "No MySQL a conta é o PAR usuário@host:\n\n"
    "| Host | Conecta de |\n|---|---|\n| 'localhost' | só da própria máquina |\n| '192.168.0.%' | da sub-rede |\n| '%' | de qualquer lugar |\n\n"
    "'relatorio'@'localhost' e 'relatorio'@'%' são DUAS contas diferentes, com senhas e permissões separadas.\n\n"
    "CREATE LOGIN ... WITH PASSWORD é sintaxe do SQL Server. Depois de criar a conta no MySQL: GRANT SELECT ON vendas.* TO 'relatorio'@'localhost';",
)
T.mc(
    "No PostgreSQL, o arquivo de configuração que define quais hosts podem se conectar, a quais bancos, com quais usuários e por qual método de autenticação é o",
    "pg_hba.conf.",
    ["postgresql.conf.", "my.cnf.", "pg_ident.conf, que define a porta e a memória do servidor.", "sqlnet.ora."],
    "Quem pode conectar, de onde e como (PostgreSQL): letra {G}, pg_hba.conf (host-based authentication).\n\n"
    "| Arquivo | SGBD | Função |\n|---|---|---|\n"
    "| postgresql.conf | PostgreSQL | parâmetros do servidor: porta, memória (shared_buffers), listen_addresses, log |\n"
    "| pg_hba.conf | PostgreSQL | regras de acesso: tipo de conexão, banco, usuário, endereço, método (scram-sha-256, md5, trust) |\n"
    "| pg_ident.conf | PostgreSQL | mapeia usuário do sistema operacional para usuário do banco |\n"
    "| my.cnf / my.ini | MySQL | configuração do servidor |\n| sqlnet.ora | Oracle | rede do cliente/servidor |\n\n"
    "Pegadinha: liberar acesso remoto no PostgreSQL exige mexer NOS DOIS — listen_addresses no postgresql.conf e uma linha no pg_hba.conf.",
)
T.mc(
    "Após a instalação do Microsoft SQL Server, o administrador precisa habilitar o protocolo TCP/IP da instância, alterar a conta de serviço e reiniciar o serviço do mecanismo de banco de dados. A ferramenta própria para essas tarefas é o",
    "SQL Server Configuration Manager.",
    ["SQL Server Profiler.", "Database Engine Tuning Advisor.", "SQL Server Agent.", "Data Quality Client."],
    "Protocolos de rede, contas de serviço e serviços do SQL Server: letra {G}, SQL Server Configuration Manager.\n\n"
    "| Ferramenta | Serve para |\n|---|---|\n"
    "| Configuration Manager | serviços, contas de serviço, protocolos (TCP/IP, Named Pipes), portas |\n"
    "| SSMS (Management Studio) | administração geral e consultas |\n"
    "| SQL Server Agent | agendar jobs (backup, manutenção) |\n"
    "| Profiler / Extended Events | capturar o que o servidor executa |\n"
    "| Database Engine Tuning Advisor | sugerir índices a partir de uma carga |\n\n"
    "Detalhe de prova: na edição Express o TCP/IP vem DESABILITADO por padrão — conexão remota falha até habilitar no Configuration Manager.",
)
T.mc(
    "No Microsoft SQL Server, o componente que executa tarefas agendadas, como backups noturnos e rotinas de manutenção de índices, além de disparar alertas e notificações a operadores, é o",
    "SQL Server Agent.",
    ["SQL Server Browser.", "tempdb.", "Query Store.", "SQL Server Configuration Manager."],
    "Agendamento de backup e manutenção: letra {G}, SQL Server Agent.\n\n"
    "O Agent é um serviço à parte do mecanismo de banco. Ele executa JOBS (passos em T-SQL, PowerShell etc.) em AGENDAS e dispara ALERTAS para OPERADORES. Jobs e histórico ficam no msdb.\n\n"
    "Detalhes que caem:\n\n"
    "— a edição Express NÃO tem SQL Server Agent; o agendamento lá se faz pelo Agendador de Tarefas do Windows chamando sqlcmd;\n\n"
    "— Maintenance Plans (backup, reindexação, verificação de integridade) rodam como jobs do Agent.\n\n"
    "O Browser informa a porta das instâncias nomeadas; o Query Store guarda histórico de planos.",
)
T.mc(
    "Na instalação de um SGBD, a definição do collation (agrupamento) da instância ou do banco de dados determina",
    "as regras de ordenação e de comparação de textos, como sensibilidade a maiúsculas e minúsculas e a acentos.",
    ["o algoritmo de compressão usado nos arquivos de backup.",
     "o número máximo de conexões simultâneas.",
     "o intervalo entre os checkpoints do log de transações.",
     "o tamanho da página de dados em disco."],
    "Collation: letra {G}.\n\n"
    "Ele decide se 'jose' = 'José' = 'JOSE' numa comparação e em que ordem os nomes saem no ORDER BY.\n\n"
    "Lendo o nome de um collation do SQL Server, Latin1_General_CI_AS:\n\n"
    "| Sufixo | Significa |\n|---|---|\n| CI / CS | Case Insensitive / Case Sensitive (maiúsculas) |\n| AI / AS | Accent Insensitive / Accent Sensitive (acentos) |\n\n"
    "Com CI_AS, 'jose' = 'JOSE', mas 'jose' ≠ 'josé'.\n\n"
    "É escolha de instalação que dá trabalho mudar depois: bancos e a tempdb com collations diferentes geram erro de conflito em junções e tabelas temporárias.",
)
T.mc(
    "Sobre as restrições PRIMARY KEY e UNIQUE em uma tabela relacional, é correto afirmar que",
    "uma tabela pode ter várias restrições UNIQUE, mas apenas uma PRIMARY KEY, e a chave primária não aceita valores nulos.",
    ["uma tabela pode ter várias PRIMARY KEY, mas apenas uma restrição UNIQUE.",
     "a restrição UNIQUE não aceita valores nulos em nenhum SGBD.",
     "a PRIMARY KEY permite valores repetidos, desde que não sejam nulos.",
     "as duas restrições são equivalentes e intercambiáveis em qualquer situação."],
    "PRIMARY KEY × UNIQUE: letra {G}.\n\n"
    "| | PRIMARY KEY | UNIQUE |\n|---|---|---|\n"
    "| quantas por tabela | UMA | várias |\n| aceita NULL? | nunca | sim (o SQL Server aceita UM NULL; PostgreSQL e MySQL, vários) |\n"
    "| cria índice? | sim (no SQL Server, clusterizado por padrão) | sim (não clusterizado) |\n| pode ser referenciada por FK? | sim | sim |\n\n"
    "Uso típico: id como PRIMARY KEY, CPF e e-mail como UNIQUE.",
)
T.mc(
    "A restrição de integridade que garante que o valor de uma coluna pertença ao conjunto de valores permitidos para ela — por exemplo, que a coluna sexo aceite apenas 'F' ou 'M', ou que um salário seja positivo — é a integridade",
    "de domínio.",
    ["de entidade.", "referencial.", "transacional.", "de autenticação."],
    "Valor dentro do conjunto permitido: letra {G}, integridade de domínio.\n\n"
    "| Integridade | Garante | Implementada com |\n|---|---|---|\n"
    "| de domínio | valor válido para a coluna | tipo de dado, CHECK, NOT NULL, DEFAULT |\n"
    "| de entidade | toda linha identificável | PRIMARY KEY (única e não nula) |\n"
    "| referencial | FK aponta para algo que existe | FOREIGN KEY |\n"
    "| semântica / de negócio | regra que as anteriores não expressam | trigger, procedure, aplicação |\n\n"
    "Exemplo: salario DECIMAL(10,2) CHECK (salario > 0).",
    dificuldade=1,
)
T.mc(
    "Ao definir a coluna data_cadastro DATE DEFAULT CURRENT_DATE em uma tabela, o efeito é que",
    "quando um INSERT não informar valor para data_cadastro, o SGBD gravará a data corrente nessa coluna.",
    ["a coluna passa a não aceitar alterações por UPDATE.",
     "a coluna sempre recebe a data corrente, mesmo quando o INSERT informar outro valor.",
     "a coluna passa a ser chave primária da tabela.",
     "a coluna é recalculada automaticamente a cada consulta."],
    "DEFAULT: letra {G} — só entra quando o valor é OMITIDO.\n\n"
    "INSERT INTO cliente (nome) VALUES ('Ana');  -- data_cadastro = hoje\nINSERT INTO cliente (nome, data_cadastro) VALUES ('Bia', '2025-01-10');  -- vale 2025-01-10\n\n"
    "DEFAULT não bloqueia UPDATE nem sobrescreve valor informado. Se o INSERT mandar NULL explícito, grava NULL (a não ser que a coluna seja NOT NULL).\n\n"
    "No SQL Server, o equivalente costuma ser DEFAULT GETDATE().",
    dificuldade=1,
)
T.mc(
    "Em uma transação, o comando SAVEPOINT permite",
    "marcar um ponto intermediário, para o qual é possível desfazer parte da transação com ROLLBACK TO SAVEPOINT, sem desfazê-la por inteiro.",
    ["confirmar definitivamente as alterações feitas até aquele ponto.",
     "gravar um backup completo do banco no meio da transação.",
     "liberar todos os bloqueios obtidos pela transação.",
     "iniciar uma nova transação independente da atual."],
    "SAVEPOINT: letra {G}.\n\n"
    "BEGIN;\n  INSERT INTO pedido ...;\n  SAVEPOINT antes_itens;\n  INSERT INTO item ...;  -- falhou a validação\n  ROLLBACK TO SAVEPOINT antes_itens;  -- desfaz só o item\nCOMMIT;  -- o pedido fica\n\n"
    "SAVEPOINT não confirma nada: até o COMMIT tudo pode ser desfeito. No SQL Server a sintaxe é SAVE TRANSACTION nome e ROLLBACK TRANSACTION nome.\n\n"
    "Comandos de controle de transação (DTL/TCL): BEGIN, COMMIT, ROLLBACK, SAVEPOINT.",
)
T.mc(
    "A transação T1 bloqueou a linha A e aguarda a linha B; ao mesmo tempo, a transação T2 bloqueou a linha B e aguarda a linha A. Diante desse impasse, os SGBDs relacionais como SQL Server, MySQL (InnoDB) e PostgreSQL normalmente",
    "detectam o deadlock e escolhem uma das transações como vítima, desfazendo-a para que a outra prossiga.",
    ["mantêm as duas transações esperando indefinidamente até intervenção manual do DBA.",
     "confirmam as duas transações com os valores que cada uma leu.",
     "desfazem as duas transações e reiniciam o serviço do banco.",
     "convertem automaticamente o nível de isolamento para READ UNCOMMITTED."],
    "Duas transações esperando uma pela outra: deadlock. Letra {G}.\n\n"
    "O SGBD tem um detector de deadlock que encontra o ciclo de espera, escolhe uma VÍTIMA (em geral a que custa menos desfazer), faz ROLLBACK dela e devolve um erro à aplicação "
    "(no SQL Server, erro 1205). A outra segue normalmente.\n\n"
    "A aplicação deve tratar o erro e repetir a transação.\n\n"
    "Como reduzir deadlocks: acessar as tabelas sempre na mesma ordem, manter transações curtas, ter índices que evitem varrer e bloquear linhas demais.",
)
T.fixa(
    "Sobre o gerenciamento de usuários e permissões em SGBDs, analise as afirmativas a seguir.",
    AF3, "C",
    "Quais estão certas? Letra C: I e II.\n\n"
    "I — certa. Papéis (roles) agrupam permissões: dá-se o GRANT ao papel e põe-se o usuário no papel. Trocar a função de alguém é trocar o papel, não refazer dezenas de GRANTs.\n\n"
    "II — certa. Menor privilégio: a conta da aplicação recebe só o que a aplicação usa.\n\n"
    "III — errada. Conectar a aplicação como sa (SQL Server) ou root (MySQL) é o oposto do menor privilégio: uma SQL injection passa a ter poder de apagar o banco inteiro ou ler qualquer tabela.",
    afirmacoes=[
        "O uso de papéis (roles) facilita a administração, pois as permissões são concedidas ao papel e os usuários herdam as permissões dos papéis de que participam.",
        "Pelo princípio do menor privilégio, cada conta deve receber apenas as permissões necessárias para executar suas tarefas.",
        "É recomendável que as aplicações se conectem ao banco usando a conta administrativa (como sa ou root), para evitar erros de permissão.",
    ],
    formato="afirmacoes",
)
T.mc(
    "Entre as atribuições a seguir, a que NÃO é responsabilidade típica do administrador de banco de dados (DBA) é",
    "desenvolver as telas e a interface gráfica do sistema utilizado pelos usuários finais.",
    ["definir e executar a política de backup e recuperação.",
     "conceder e revogar permissões de acesso aos dados.",
     "monitorar o desempenho e ajustar índices e configurações do SGBD.",
     "instalar, configurar e aplicar atualizações no SGBD."],
    "Qual NÃO é tarefa de DBA? Letra {G}: interface gráfica é trabalho do desenvolvedor de aplicação.\n\n"
    "As demais são justamente as linhas do edital do cargo: backup e recuperação, usuários e permissões, tuning e desempenho, instalação e configuração.\n\n"
    "Atalho: DBA cuida do banco (dados, acesso, desempenho, disponibilidade); o que o usuário final vê na tela é da aplicação.",
    formato="negativa", dificuldade=1,
)
T.mc(
    "Para verificar a integridade física e lógica de um banco de dados no Microsoft SQL Server — detectando, por exemplo, páginas corrompidas e inconsistências na alocação —, o administrador deve executar o comando",
    "DBCC CHECKDB.",
    ["DBCC SHRINKFILE.", "UPDATE STATISTICS.", "BACKUP LOG.", "sp_who2."],
    "Verificar corrupção no SQL Server: letra {G}, DBCC CHECKDB.\n\n"
    "| Comando | Faz |\n|---|---|\n"
    "| DBCC CHECKDB | verifica a integridade física e lógica de todo o banco |\n"
    "| DBCC SHRINKFILE | reduz arquivo de dados ou de log (uso esporádico; fragmenta índices) |\n"
    "| UPDATE STATISTICS | atualiza estatísticas para o otimizador |\n"
    "| BACKUP LOG | backup do log de transações |\n| sp_who2 | lista sessões e bloqueios ativos |\n\n"
    "CHECKDB entra nos planos de manutenção, de preferência antes do backup: backup de um banco corrompido guarda a corrupção.",
)
T.fixa(
    "Considere o script executado no SQL Server:\n\nCREATE ROLE financeiro;\nGRANT SELECT, UPDATE ON PAGAMENTOS TO financeiro;\nALTER ROLE financeiro ADD MEMBER joao;\nREVOKE UPDATE ON PAGAMENTOS FROM financeiro;\n\nSobre o que João pode fazer na tabela PAGAMENTOS, analise as afirmativas, considerando que ele não recebeu nenhuma outra permissão.",
    AF3b, "A",
    "O que sobra para João depois do REVOKE? Letra A: só a afirmativa I.\n\n"
    "O papel financeiro recebe SELECT e UPDATE; João entra no papel e herda os dois; depois o UPDATE é retirado DO PAPEL — logo, de todos os seus membros.\n\n"
    "I — certa: SELECT continua.\n\nII — errada: o UPDATE foi revogado do papel.\n\n"
    "III — errada: DELETE nunca foi concedido.\n\n"
    "Atalho: usuário herda do papel o que o papel tem AGORA. Mexeu no papel, mexeu em todos os membros.",
    afirmacoes=[
        "João pode consultar a tabela PAGAMENTOS.",
        "João pode alterar registros de PAGAMENTOS, pois recebeu UPDATE antes do REVOKE.",
        "João pode excluir registros de PAGAMENTOS, pois pertence a um papel com permissões na tabela.",
    ],
    formato="afirmacoes",
)
