from base import AF3, AF3b, Topico

T = Topico("Segurança de dados", 7, "bd-seguranca-dados",
           "Segurança de dados: controle de acesso, auditoria, criptografia e boas práticas de proteção de informações")

T.mc(
    "Uma aplicação monta a consulta concatenando o texto digitado pelo usuário, conforme o trecho abaixo. Se o atacante digitar no campo login o valor ' OR '1'='1' -- , o efeito mais provável é",
    "a condição do WHERE passar a ser sempre verdadeira e o restante da consulta ser comentado, permitindo entrar sem saber a senha.",
    ["o SGBD recusar a consulta por erro de sintaxe, bloqueando o ataque.",
     "a senha do usuário ser criptografada automaticamente.",
     "a consulta retornar apenas o usuário de login vazio.",
     "a tabela USUARIO ser apagada."],
    "Login ' OR '1'='1' -- : letra {G}.\n\n"
    "A consulta montada fica:\n\nSELECT * FROM USUARIO WHERE login = '' OR '1'='1' -- ' AND senha = '...'\n\n"
    "— a aspa digitada FECHA a string do login;\n\n— OR '1'='1' torna o WHERE verdadeiro para todas as linhas;\n\n— o -- comenta o resto, inclusive a verificação de senha.\n\n"
    "A aplicação recebe linhas e considera o login válido — em geral entra como o PRIMEIRO usuário da tabela, muitas vezes o administrador.\n\n"
    "Apagar a tabela seria outra carga útil ('; DROP TABLE ...), não essa.\n\n"
    "Defesa: consulta parametrizada (prepared statement), em que o valor digitado vai separado do comando e nunca é interpretado como SQL.",
    formato="codigo", dificuldade=2,
    codigo="sql = \"SELECT * FROM USUARIO WHERE login = '\" + login +\n      \"' AND senha = '\" + senha + \"'\";",
)
T.mc(
    "A medida mais eficaz para prevenir ataques de SQL injection em uma aplicação que acessa banco de dados é",
    "usar consultas parametrizadas (prepared statements), nas quais os valores informados pelo usuário são enviados separados do comando SQL.",
    ["esconder as mensagens de erro do banco de dados.",
     "trocar aspas simples por aspas duplas na entrada do usuário.",
     "usar HTTPS na comunicação entre navegador e servidor.",
     "criptografar a coluna de senha no banco."],
    "Prevenir SQL injection: letra {G}, consulta parametrizada.\n\n"
    "SELECT * FROM USUARIO WHERE login = ? AND senha_hash = ?\n\n"
    "O comando é enviado ao SGBD com marcadores; os valores vão SEPARADOS e são tratados sempre como DADO, nunca como código. Uma aspa digitada vira só um caractere do login.\n\n"
    "As outras não resolvem: esconder erro só atrapalha o atacante (ainda há injection 'cega'); trocar aspas é filtro frágil, contornável; HTTPS protege o trânsito, não a consulta; criptografar a senha não impede o OR '1'='1'.\n\n"
    "Camadas complementares: conta da aplicação com menor privilégio, validação de entrada (lista do que é permitido), stored procedures sem SQL dinâmico concatenado e WAF.",
    dificuldade=1,
)
T.mc(
    "O recurso Transparent Data Encryption (TDE), disponível no SQL Server, protege os dados",
    "em repouso, criptografando os arquivos de dados, de log e os backups, de forma transparente para as aplicações.",
    ["em trânsito entre a aplicação e o servidor, substituindo o TLS.",
     "contra consultas de usuários autorizados, que passam a ver os dados cifrados.",
     "apenas nas colunas marcadas, que ficam ilegíveis inclusive para o DBA.",
     "contra SQL injection, ao validar os comandos recebidos."],
    "O que o TDE protege: letra {G} — dados EM REPOUSO.\n\n"
    "O SGBD cifra as páginas ao gravá-las em disco e as decifra ao ler para a memória. Quem rouba o arquivo .mdf, .ldf ou o .bak não consegue anexá-lo nem restaurá-lo em outro servidor sem o certificado.\n\n"
    "O que o TDE NÃO faz:\n\n— não cifra o tráfego de rede (isso é TLS);\n\n— não esconde nada de quem tem permissão: o SELECT devolve texto claro;\n\n— não protege contra DBA nem contra SQL injection.\n\n"
    "| Recurso (SQL Server) | Protege |\n|---|---|\n| TDE | arquivos e backups em disco |\n| TLS | dados na rede |\n| Always Encrypted | colunas cifradas no CLIENTE; o servidor e o DBA não veem o texto claro |\n| Dynamic Data Masking | só MASCARA na exibição; não cifra |\n\n"
    "Pegadinha operacional: sem backup do certificado do TDE, o backup do banco não restaura em lugar nenhum.",
    dificuldade=2,
)
T.mc(
    "Uma organização precisa garantir que o número do cartão de crédito armazenado no SQL Server não possa ser lido nem pelos administradores do banco de dados, ficando os dados cifrados no servidor e sendo decifrados apenas pela aplicação cliente autorizada. O recurso adequado é o",
    "Always Encrypted.",
    ["Transparent Data Encryption (TDE).", "Dynamic Data Masking.", "Row-Level Security.", "backup com compressão."],
    "Nem o DBA pode ler: letra {G}, Always Encrypted.\n\n"
    "As chaves ficam com o CLIENTE (no driver da aplicação, com chave mestra em cofre ou certificado). O SQL Server só recebe e armazena dados cifrados — na memória do servidor também ficam cifrados.\n\n"
    "TDE cifra o disco, mas o DBA consulta e vê texto claro. Dynamic Data Masking mostra 'XXXX-XXXX-XXXX-1234' para usuários sem permissão UNMASK, mas o dado está em claro no banco e um privilegiado vê tudo. Row-Level Security filtra LINHAS, não protege colunas.\n\n"
    "Custo do Always Encrypted: limita consultas sobre a coluna (não dá para fazer LIKE nem somar valores cifrados).",
    dificuldade=3,
)
T.mc(
    "No SQL Server, o recurso que exibe parcialmente os dados sensíveis — por exemplo, mostrando apenas os quatro últimos dígitos do CPF — para usuários sem permissão especial, sem alterar os dados armazenados, é o",
    "Dynamic Data Masking.",
    ["Transparent Data Encryption.", "Always Encrypted.", "SQL Server Audit.", "Change Data Capture."],
    "Mostrar só parte do dado, sem mudar o armazenado: letra {G}, Dynamic Data Masking.\n\n"
    "ALTER TABLE cliente ALTER COLUMN cpf ADD MASKED WITH (FUNCTION = 'partial(0,\"XXX.XXX.XXX-\",2)');\n\n"
    "Quem não tem a permissão UNMASK vê o valor mascarado; quem tem vê o real.\n\n"
    "Limites: é recurso de EXIBIÇÃO, não de segurança forte. O dado está em claro no disco e no backup, e um usuário com acesso de consulta pode inferir valores com WHERE (cpf LIKE '123%'). Serve para tela de atendimento e relatório, não substitui criptografia.\n\n"
    "Change Data Capture registra alterações para integração; Audit registra eventos.",
    dificuldade=2,
)
T.mc(
    "Em um sistema multiempresa que compartilha a mesma tabela de PEDIDOS, deseja-se que cada usuário veja somente as linhas da sua própria empresa, com o filtro aplicado pelo SGBD a qualquer consulta, mesmo que a aplicação esqueça de incluir o WHERE. O recurso adequado é",
    "a segurança em nível de linha (Row-Level Security), com uma política de filtro por empresa.",
    ["o mascaramento dinâmico de dados na coluna empresa_id.",
     "a criptografia transparente do arquivo de dados.",
     "um índice clusterizado na coluna empresa_id.",
     "a revogação do privilégio SELECT na tabela para todos os usuários."],
    "Cada usuário vê só as linhas da sua empresa, imposto pelo banco: letra {G}, Row-Level Security.\n\n"
    "SQL Server: CREATE SECURITY POLICY com uma função de predicado. PostgreSQL: ALTER TABLE pedidos ENABLE ROW LEVEL SECURITY + CREATE POLICY ... USING (empresa_id = current_setting('app.empresa')::int).\n\n"
    "Daí em diante, todo SELECT, UPDATE e DELETE recebe o filtro automaticamente.\n\n"
    "| Recurso | Restringe |\n|---|---|\n| GRANT / REVOKE | objeto inteiro (tabela, view) e colunas |\n| view | colunas e linhas, se o usuário só acessar pela view |\n"
    "| Row-Level Security | LINHAS, em qualquer acesso direto |\n| Data Masking | exibição de colunas |\n\n"
    "Índice é desempenho, não segurança. Revogar SELECT de todos impede o uso do sistema.",
    dificuldade=2,
)
T.mc(
    "Para armazenar as senhas dos usuários de um sistema em uma tabela do banco de dados, a prática recomendada é",
    "gravar um hash da senha gerado por algoritmo próprio para senhas e lento por projeto (como bcrypt, scrypt, Argon2 ou PBKDF2), com salt único por usuário.",
    ["gravar a senha criptografada com AES, guardando a chave na mesma tabela.",
     "gravar o hash MD5 da senha, sem salt, por ser rápido.",
     "gravar a senha em texto claro em uma coluna com Dynamic Data Masking.",
     "gravar a senha codificada em Base64."],
    "Armazenar senha: letra {G}.\n\n"
    "Senha não precisa ser DECIFRADA, só VERIFICADA: calcula-se o hash do que o usuário digitou e compara-se com o armazenado. Por isso usa-se hash (irreversível), não criptografia (reversível).\n\n"
    "— SALT único por usuário: dois usuários com a mesma senha têm hashes diferentes, e tabelas pré-calculadas (rainbow tables) deixam de funcionar;\n\n"
    "— algoritmo LENTO (bcrypt, Argon2, PBKDF2): torna a força bruta cara.\n\n"
    "| Prática | Problema |\n|---|---|\n| MD5 ou SHA-1 sem salt | rápido demais e quebrado por rainbow table |\n| AES com a chave junto | quem rouba a tabela leva a chave |\n"
    "| Base64 | é CODIFICAÇÃO, não segurança: decodifica-se em um segundo |\n| texto claro mascarado | a máscara só esconde na tela |",
    dificuldade=2,
)
T.mc(
    "O recurso nativo do Microsoft SQL Server para registrar eventos de segurança e de acesso — como logins com falha, alterações de permissões e consultas a tabelas sensíveis —, gravando-os em arquivo, no log de segurança ou no log de aplicação do Windows, é o",
    "SQL Server Audit.",
    ["SQL Server Agent.", "Query Store.", "Database Mail.", "Log Shipping."],
    "Auditoria nativa no SQL Server: letra {G}, SQL Server Audit.\n\n"
    "Montagem em duas partes:\n\n"
    "1. SERVER AUDIT — define o DESTINO (arquivo, Windows Security Log, Application Log);\n\n"
    "2. AUDIT SPECIFICATION — define O QUE registrar: no nível do servidor (FAILED_LOGIN_GROUP, alteração de logins) ou do banco (SELECT, UPDATE em dbo.salarios por qualquer usuário).\n\n"
    "Equivalentes: no MySQL, Enterprise Audit ou o plugin audit do Percona/MariaDB; no PostgreSQL, a extensão pgaudit.\n\n"
    "Query Store registra DESEMPENHO; Agent agenda jobs; Log Shipping é alta disponibilidade.",
    dificuldade=2,
)
T.mc(
    "Para manter uma trilha de auditoria das alterações de salário na tabela FUNCIONARIO — registrando o valor antigo, o novo, o usuário e a data —, uma solução implementada no próprio banco de dados é",
    "um trigger AFTER UPDATE que grava esses dados em uma tabela de auditoria.",
    ["uma view que exibe apenas a coluna salário.",
     "um índice na coluna salário.",
     "uma restrição CHECK que impede alterações no salário.",
     "uma função escalar que calcula o salário médio."],
    "Registrar antes, depois, quem e quando: letra {G}, trigger de auditoria.\n\n"
    "Exemplo em T-SQL:\n\nCREATE TRIGGER trg_aud_salario ON FUNCIONARIO AFTER UPDATE AS\nINSERT INTO AUD_SALARIO (matricula, salario_antigo, salario_novo, usuario, data_hora)\nSELECT d.matricula, d.salario, i.salario, SUSER_SNAME(), SYSDATETIME()\nFROM deleted d JOIN inserted i ON i.matricula = d.matricula\nWHERE d.salario <> i.salario;\n\n"
    "O trigger dispara qualquer que seja o caminho da alteração: aplicação, script ou ferramenta.\n\n"
    "Para a auditoria ser confiável, quem é auditado não pode ter permissão de apagar ou alterar a tabela de auditoria — segregação de funções.\n\n"
    "Alternativas prontas: temporal tables (SQL Server 2016+), Change Data Capture, SQL Server Audit.",
    dificuldade=2,
)
T.mc(
    "Para que a comunicação entre a aplicação e o servidor de banco de dados não possa ser interceptada e lida na rede, deve-se",
    "habilitar criptografia da conexão com TLS (SSL), exigindo-a no servidor e configurando os clientes para validar o certificado.",
    ["ativar o Transparent Data Encryption.", "usar Dynamic Data Masking em todas as colunas.",
     "trocar a porta padrão do SGBD.", "aplicar hash em todos os dados antes de gravá-los."],
    "Proteger o dado EM TRÂNSITO: letra {G}, TLS.\n\n"
    "| Estado do dado | Proteção |\n|---|---|\n| em trânsito (rede) | TLS: Encrypt=True e certificado no SQL Server; require_secure_transport no MySQL; ssl e hostssl no pg_hba.conf do PostgreSQL |\n"
    "| em repouso (disco) | TDE, criptografia de disco ou de tablespace |\n| em uso (memória e consulta) | Always Encrypted, enclaves |\n\n"
    "Validar o certificado no cliente importa: sem isso, um atacante no meio pode se passar pelo servidor.\n\n"
    "Trocar a porta é obscuridade, não proteção. Hash em todos os dados os tornaria inúteis para consulta.",
    dificuldade=1,
)
T.mc(
    "Segundo a Lei Geral de Proteção de Dados Pessoais (LGPD — Lei nº 13.709/2018), é classificado como dado pessoal sensível o dado sobre",
    "origem racial ou étnica, convicção religiosa, opinião política, saúde, vida sexual, dado genético ou biométrico, quando vinculado a uma pessoa natural.",
    ["nome completo e endereço residencial.", "número de CPF e data de nascimento.",
     "faturamento de uma pessoa jurídica.", "endereço de e-mail corporativo de uma empresa."],
    "Dado pessoal sensível na LGPD: letra {G} (art. 5º, II).\n\n"
    "| Categoria (art. 5º) | Exemplos |\n|---|---|\n| dado pessoal | nome, CPF, endereço, e-mail, IP — identifica ou torna identificável uma pessoa natural |\n"
    "| dado pessoal SENSÍVEL | origem racial ou étnica, religião, opinião política, filiação sindical, saúde, vida sexual, genético, biométrico |\n| dado anonimizado | não permite identificar o titular — fica fora da LGPD |\n\n"
    "Dado de PESSOA JURÍDICA não é dado pessoal. Nome e CPF são pessoais, mas não sensíveis.\n\n"
    "Para o DBA, sensível significa mais controle: criptografia, acesso restrito, auditoria de quem consultou.",
    dificuldade=1,
)
T.mc(
    "Para disponibilizar uma base de clientes à equipe de desenvolvimento, o DBA substituiu nome e CPF por códigos aleatórios, mantendo em outra tabela, sob acesso restrito, a correspondência entre os códigos e os titulares. Segundo a LGPD, essa técnica é a",
    "pseudonimização, e os dados continuam sendo dados pessoais.",
    ["anonimização, e os dados deixam de ser pessoais.",
     "criptografia homomórfica.",
     "eliminação definitiva dos dados.",
     "portabilidade dos dados."],
    "Troca por código, com tabela de correspondência guardada à parte: letra {G}, pseudonimização.\n\n"
    "| Técnica | Dá para voltar ao titular? | Status na LGPD |\n|---|---|---|\n"
    "| pseudonimização (art. 13, §4º) | SIM, com a informação adicional mantida separada | continua dado pessoal |\n"
    "| anonimização (art. 5º, XI) | não, por meios razoáveis | deixa de ser dado pessoal |\n\n"
    "Como a tabela de correspondência existe, a reidentificação é possível — logo, não é anonimização.\n\n"
    "Para ambiente de desenvolvimento e teste, o ideal é mascaramento irreversível ou dados sintéticos: copiar a produção 'como está' para o dev é vazamento.",
    dificuldade=2,
)
T.fixa(
    "Relacione cada controle de segurança ao pilar da segurança da informação que ele protege prioritariamente.\n\n1. Criptografia dos dados sensíveis\n2. Hash para verificar se um arquivo de backup foi alterado\n3. Replicação do banco em outro datacenter\n\nA associação correta é:",
    ["1 – confidencialidade; 2 – integridade; 3 – disponibilidade.",
     "1 – integridade; 2 – confidencialidade; 3 – disponibilidade.",
     "1 – disponibilidade; 2 – integridade; 3 – confidencialidade.",
     "1 – confidencialidade; 2 – disponibilidade; 3 – integridade.",
     "1 – integridade; 2 – disponibilidade; 3 – confidencialidade."],
    "A",
    "Controle × pilar: letra A.\n\n"
    "| Pilar | Pergunta | Controles típicos em banco |\n|---|---|---|\n"
    "| CONFIDENCIALIDADE | só quem pode, lê? | criptografia, GRANT/REVOKE, mascaramento |\n"
    "| INTEGRIDADE | o dado está correto e não foi alterado indevidamente? | hash e checksum, constraints, transações, auditoria |\n"
    "| DISPONIBILIDADE | está acessível quando precisa? | replicação, cluster, backup, site de contingência |\n\n"
    "Hash não esconde nada: qualquer mudança no arquivo muda o hash, então ele DETECTA alteração — é integridade. Replicação mantém o serviço no ar se um datacenter cair.\n\n"
    "Completam o quadro: autenticidade (é quem diz ser?) e não repúdio (não pode negar que fez), garantidos por assinatura digital.",
    dificuldade=1,
)
T.mc(
    "Uma consultoria recomendou criar a view VW_FUNCIONARIO_PUBLICO, contendo apenas nome, cargo e ramal, conceder SELECT nessa view aos usuários do setor de atendimento e não conceder acesso à tabela FUNCIONARIO, que contém salário e CPF. Essa medida",
    "restringe o acesso às colunas sensíveis, aplicando o princípio do menor privilégio por meio de uma visão.",
    ["é ineficaz, pois quem tem SELECT na view tem automaticamente SELECT na tabela-base.",
     "duplica fisicamente os dados de FUNCIONARIO, aumentando o risco de vazamento.",
     "impede que a tabela FUNCIONARIO receba novos registros.",
     "só funciona se a view for materializada."],
    "View como controle de acesso: letra {G}.\n\n"
    "O usuário recebe SELECT na VIEW e nenhum privilégio na tabela. Ele consulta nome, cargo e ramal, e não há caminho para salário e CPF.\n\n"
    "Funciona por causa do encadeamento de propriedade (ownership chaining no SQL Server; mecanismo equivalente nos demais): se a view e a tabela têm o mesmo dono, o SGBD confere a permissão só na view.\n\n"
    "A view comum não copia dado, não bloqueia INSERT de quem tem permissão na tabela e não precisa ser materializada.\n\n"
    "Alternativa com o mesmo efeito: permissão por COLUNA — GRANT SELECT (nome, cargo, ramal) ON FUNCIONARIO TO atendimento.",
    dificuldade=2,
)
T.mc(
    "Entre as práticas a seguir, a que NÃO é recomendada para proteger um servidor de banco de dados é",
    "expor a porta do SGBD diretamente à internet, para facilitar o acesso remoto dos desenvolvedores.",
    ["manter o SGBD e o sistema operacional atualizados com os patches de segurança.",
     "desabilitar contas padrão e recursos não utilizados.",
     "restringir por firewall quais endereços podem se conectar ao banco.",
     "exigir senhas fortes e autenticação multifator para contas administrativas."],
    "Qual NÃO é recomendada? Letra {G}.\n\n"
    "Porta 1433, 3306 ou 5432 aberta para a internet recebe varredura e força bruta em minutos — é uma das causas mais comuns de banco sequestrado por ransomware. "
    "Acesso remoto se faz por VPN, bastion host ou túnel SSH, nunca expondo o SGBD.\n\n"
    "As demais são hardening básico:\n\n— patches em dia;\n\n— desabilitar o que não se usa (contas padrão como sa, xp_cmdshell, bancos de exemplo);\n\n"
    "— firewall com lista de origens permitidas;\n\n— senha forte e MFA para quem administra.",
    formato="negativa", dificuldade=1,
)
T.fixa(
    "Sobre auditoria em bancos de dados, analise as afirmativas a seguir.",
    AF3, "C",
    "Quais estão certas? Letra C: I e II.\n\n"
    "I — certa. A trilha de auditoria responde quem, o quê, quando e de onde.\n\n"
    "II — certa. Se o próprio DBA auditado pode apagar o log, a auditoria não vale como prova. Os registros vão para destino protegido (outro servidor, SIEM, log de segurança do Windows) com acesso segregado.\n\n"
    "III — errada. Auditar tudo gera volume enorme, custo de desempenho e registros que ninguém lê. Audita-se o que importa: logins com falha, mudanças de permissão, DDL, acesso a tabelas sensíveis, ações de contas privilegiadas.",
    afirmacoes=[
        "A auditoria permite identificar quem executou determinada operação, quando e a partir de onde.",
        "Os registros de auditoria devem ser protegidos contra alteração e exclusão, inclusive por parte dos administradores auditados.",
        "A boa prática é auditar todas as consultas SELECT de todas as tabelas, pois o volume de registros não afeta o desempenho.",
    ],
    formato="afirmacoes",
)
T.mc(
    "Para proteger os arquivos de backup de um banco do SQL Server que contém dados pessoais, o DBA decidiu usar BACKUP DATABASE ... WITH ENCRYPTION. Para que esses backups possam ser restaurados no futuro, inclusive em outro servidor, é indispensável",
    "guardar com segurança, em local separado dos backups, uma cópia do certificado (ou chave assimétrica) usado na criptografia, com sua chave privada.",
    ["desabilitar a criptografia antes de cada restauração.",
     "armazenar o certificado no mesmo arquivo do backup.",
     "usar o modelo de recuperação SIMPLE.",
     "compactar o backup com ZIP antes de copiá-lo."],
    "Backup criptografado: letra {G}.\n\n"
    "Sem o certificado, o backup é um arquivo ilegível para sempre — inclusive para você. É o caso clássico de servidor que morre levando junto o único certificado.\n\n"
    "BACKUP CERTIFICATE cert_backup TO FILE = '...cer'\n  WITH PRIVATE KEY (FILE = '...pvk', ENCRYPTION BY PASSWORD = '...');\n\n"
    "Guardar o certificado junto com o backup anula a proteção: quem leva um leva o outro. O certificado vai para um cofre de chaves, outro local, com senha custodiada.\n\n"
    "O mesmo vale para o TDE: sem o certificado, não se restaura o banco em outro servidor.",
    dificuldade=2,
)
T.mc(
    "Para proteger grandes volumes de dados armazenados no banco, os sistemas normalmente usam criptografia simétrica, como o AES. A principal razão dessa escolha é que a criptografia simétrica",
    "é muito mais rápida que a assimétrica, sendo adequada para cifrar grandes volumes de dados.",
    ["dispensa o gerenciamento de chaves.", "usa um par de chaves pública e privada.",
     "é irreversível, como uma função hash.", "só pode ser quebrada com acesso físico ao servidor."],
    "Por que AES para dados volumosos: letra {G}, desempenho.\n\n"
    "| | Simétrica (AES) | Assimétrica (RSA, ECC) |\n|---|---|---|\n| chaves | uma, compartilhada | par pública/privada |\n"
    "| velocidade | alta | centenas de vezes mais lenta |\n| uso típico | cifrar os dados (TDE, coluna, backup) | trocar e proteger a chave simétrica; assinatura digital |\n\n"
    "Arquitetura do TDE, por exemplo: os dados são cifrados com uma chave simétrica (DEK, AES-256), e a DEK é protegida por um certificado (assimétrico). Cada uma faz o que sabe fazer melhor.\n\n"
    "A simétrica PRECISA de gestão de chaves — guardar, girar, proteger. Irreversível é hash, não criptografia.",
    dificuldade=1,
)
T.fixa(
    "Sobre controle de acesso em bancos de dados, analise as afirmativas a seguir.",
    AF3b, "C",
    "Quais estão certas? Letra C: I e III.\n\n"
    "I — certa. Autenticação (quem você é) vem antes da autorização (o que você pode). O SGBD primeiro valida o login e depois confere as permissões em cada objeto.\n\n"
    "II — errada. Contas compartilhadas destroem a rastreabilidade: a auditoria registra 'admin' e não se sabe qual pessoa agiu. Cada pessoa tem conta nominal.\n\n"
    "III — certa. Revisão periódica de acessos remove permissões acumuladas e contas de quem saiu — muitos incidentes vêm de conta órfã.",
    afirmacoes=[
        "A autenticação verifica a identidade do usuário, e a autorização define o que esse usuário pode fazer no banco depois de autenticado.",
        "O uso de uma única conta administrativa compartilhada entre os DBAs facilita a auditoria, pois concentra os registros em um só usuário.",
        "As permissões concedidas devem ser revisadas periodicamente, removendo acessos de usuários desligados ou que mudaram de função.",
    ],
    formato="afirmacoes",
)
T.mc(
    "Uma stored procedure do SQL Server recebe o nome de uma cidade no parâmetro @cidade e executa o código abaixo. Sobre a segurança dessa procedure, é correto afirmar que",
    "ela continua vulnerável a SQL injection, pois concatena a entrada em SQL dinâmico; o correto é usar sp_executesql com parâmetro.",
    ["ela é imune a SQL injection, pois todo código dentro de stored procedure é seguro.",
     "ela só seria vulnerável se a tabela CLIENTE não tivesse chave primária.",
     "a vulnerabilidade é eliminada se o usuário tiver apenas permissão EXECUTE.",
     "o EXEC impede a execução de mais de um comando por chamada."],
    "Procedure com SQL dinâmico concatenado: letra {G}, continua vulnerável.\n\n"
    "Stored procedure só protege quando o parâmetro é usado COMO PARÂMETRO (WHERE cidade = @cidade). Ao concatenar o texto e executar com EXEC, volta-se ao problema da aplicação: "
    "a entrada Santos'; DROP TABLE CLIENTE; -- vira código.\n\n"
    "Correção em T-SQL:\n\nEXEC sp_executesql\n  N'SELECT * FROM CLIENTE WHERE cidade = @c',\n  N'@c VARCHAR(40)',\n  @c = @cidade;\n\n"
    "Permissão só de EXECUTE não ajuda: o código injetado roda no contexto da procedure. E o EXEC executa lotes com vários comandos.\n\n"
    "Atalho: o perigo é CONCATENAR entrada em comando, seja na aplicação, seja dentro do banco.",
    formato="codigo", dificuldade=3,
    codigo="DECLARE @sql NVARCHAR(500);\nSET @sql = 'SELECT * FROM CLIENTE WHERE cidade = ''' + @cidade + '''';\nEXEC (@sql);",
)
