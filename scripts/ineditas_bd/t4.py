from base import AF3, AF3b, TABELAS, Topico, confere, roda

T = Topico("SQL e programação de banco", 4, "bd-sql-programacao",
           "SQL e programação de banco: consultas, junções, stored procedures, triggers e funções")

BASE = "Considere as tabelas a seguir.\n\n" + TABELAS + "\n\n"

T.mc(
    BASE + "Quantas linhas são retornadas pela consulta abaixo?",
    "5", ["4", "6", "3", "20"],
    "Quantas linhas o INNER JOIN devolve? Letra {G}: 5.\n\n"
    "INNER JOIN devolve uma linha para cada PAR que satisfaz o ON. Os 5 pedidos têm cliente válido, então saem 5 linhas: Ana aparece duas vezes (pedidos 10 e 11), Carla duas (13 e 14), Bruno uma.\n\n"
    "Diego não tem pedido e SOME do INNER JOIN. O pedido 13 tem valor NULL, mas o ON compara cliente_id, então ele entra.\n\n"
    "Pegadinhas: 4 é o número de clientes; 6 seria o LEFT JOIN (Diego com NULL); 20 é o produto cartesiano (4 × 5) — o que sai quando se esquece o ON.",
    formato="codigo",
    codigo="SELECT c.nome, p.id\nFROM CLIENTE c\nINNER JOIN PEDIDO p ON p.cliente_id = c.id;",
    verificar=confere("SELECT count(*) FROM CLIENTE c INNER JOIN PEDIDO p ON p.cliente_id = c.id", [(5,)]),
)
T.mc(
    BASE + "A consulta abaixo retorna",
    "apenas Diego.",
    ["Ana, Bruno e Carla.", "nenhuma linha, pois p.id nunca é nulo na tabela PEDIDO.",
     "apenas Carla, por causa do pedido de valor nulo.", "todos os clientes."],
    "LEFT JOIN + WHERE p.id IS NULL: letra {G}, só Diego.\n\n"
    "O LEFT JOIN mantém TODOS os clientes; quem não tem pedido aparece com as colunas de PEDIDO preenchidas com NULL. "
    "O WHERE p.id IS NULL filtra justamente essas linhas: clientes SEM pedido.\n\n"
    "A alternativa que diz 'p.id nunca é nulo' é a pegadinha: na tabela não é, mas o NULL é CRIADO pelo LEFT JOIN para quem não casou.\n\n"
    "Carla não sai: o pedido 13 tem valor NULL, mas p.id = 13.\n\n"
    "Padrão para decorar — 'quem não tem': LEFT JOIN ... WHERE <PK da direita> IS NULL. Equivale a NOT EXISTS.",
    formato="codigo",
    codigo="SELECT c.nome\nFROM CLIENTE c\nLEFT JOIN PEDIDO p ON p.cliente_id = c.id\nWHERE p.id IS NULL;",
    verificar=confere("SELECT c.nome FROM CLIENTE c LEFT JOIN PEDIDO p ON p.cliente_id = c.id WHERE p.id IS NULL", [("Diego",)]),
)
T.mc(
    BASE + "O resultado da consulta abaixo é",
    "uma linha: Ana, 350.",
    ["três linhas: Ana 350, Bruno 80 e Carla 40.", "duas linhas: Ana 350 e Bruno 80.",
     "uma linha: Ana, 250.", "um erro, pois HAVING não pode usar função de agregação."],
    "GROUP BY com HAVING SUM(valor) > 100: letra {G}.\n\n"
    "Agrupando por cliente: Ana 100 + 250 = 350; Bruno 80; Carla NULL + 40 = 40 (SUM ignora NULL). Só Ana passa no filtro > 100.\n\n"
    "WHERE × HAVING:\n\n"
    "| Cláusula | Filtra | Pode usar agregação? |\n|---|---|---|\n| WHERE | LINHAS, antes de agrupar | não |\n| HAVING | GRUPOS, depois de agrupar | sim |\n\n"
    "Escrever WHERE SUM(p.valor) > 100 dá erro — é o motivo de o HAVING existir.\n\n"
    "'Ana, 250' é quem leu MAX em vez de SUM.",
    formato="codigo",
    codigo="SELECT c.nome, SUM(p.valor) AS total\nFROM CLIENTE c\nJOIN PEDIDO p ON p.cliente_id = c.id\nGROUP BY c.nome\nHAVING SUM(p.valor) > 100;",
    verificar=confere("SELECT c.nome, SUM(p.valor) FROM CLIENTE c JOIN PEDIDO p ON p.cliente_id=c.id GROUP BY c.nome HAVING SUM(p.valor) > 100", [("Ana", 350)]),
)
T.fixa(
    BASE + "Os três valores retornados pela consulta abaixo são, respectivamente,",
    ["5, 4 e 3.", "5, 5 e 3.", "5, 4 e 5.", "4, 4 e 3.", "5, 5 e 5."],
    "A",
    "COUNT(*), COUNT(valor) e COUNT(DISTINCT cliente_id): letra A, 5, 4 e 3.\n\n"
    "| Expressão | Conta | Resultado |\n|---|---|---|\n"
    "| COUNT(*) | todas as linhas | 5 |\n| COUNT(valor) | linhas com valor NÃO nulo (o pedido 13 sai) | 4 |\n"
    "| COUNT(DISTINCT cliente_id) | clientes diferentes que têm pedido (1, 2, 3) | 3 |\n\n"
    "Regra de ouro: toda função de agregação IGNORA NULL, exceto COUNT(*), que conta linhas. Por isso AVG(valor) aqui dá 470 / 4 = 117,5, e não 470 / 5.",
    formato="codigo", dificuldade=2,
    codigo="SELECT COUNT(*), COUNT(valor), COUNT(DISTINCT cliente_id)\nFROM PEDIDO;",
    verificar=confere("SELECT COUNT(*), COUNT(valor), COUNT(DISTINCT cliente_id) FROM PEDIDO", [(5, 4, 3)]),
)
T.fixa(
    BASE + "O valor retornado pela consulta abaixo é",
    ["94", "117,5", "100", "117", "470"],
    "B",
    "AVG(valor) com um NULL na coluna: letra B, 117,5.\n\n"
    "AVG ignora o NULL tanto na soma quanto na CONTAGEM: (100 + 250 + 80 + 40) / 4 = 470 / 4 = 117,5.\n\n"
    "94 é a armadilha: 470 / 5, tratando o NULL como zero. Para obter esse número de propósito, seria preciso AVG(COALESCE(valor, 0)).\n\n"
    "Atalho: NULL não é zero. É 'desconhecido', e a agregação o deixa de fora.",
    formato="codigo", dificuldade=2,
    codigo="SELECT AVG(valor) FROM PEDIDO;",
    verificar=confere("SELECT AVG(valor) FROM PEDIDO", [(117.5,)]),
)
T.mc(
    BASE + "A consulta abaixo retorna",
    "nenhuma linha.",
    ["apenas o pedido 13.", "os pedidos 10, 11, 12 e 14.", "todos os cinco pedidos.", "um erro de sintaxe."],
    "WHERE valor = NULL: letra {G}, nenhuma linha.\n\n"
    "Qualquer comparação com NULL usando =, <> ou > dá DESCONHECIDO (nem verdadeiro, nem falso), e o WHERE só deixa passar o que é VERDADEIRO. Não é erro de sintaxe: roda e devolve vazio.\n\n"
    "O certo é: WHERE valor IS NULL (devolveria o pedido 13); o contrário é IS NOT NULL.\n\n"
    "Lógica de três valores do SQL: VERDADEIRO, FALSO e DESCONHECIDO. NULL = NULL também é desconhecido.",
    formato="codigo",
    codigo="SELECT id FROM PEDIDO WHERE valor = NULL;",
    verificar=confere("SELECT id FROM PEDIDO WHERE valor = NULL", []),
)
T.mc(
    BASE + "A consulta abaixo retorna os nomes dos clientes que",
    "não possuem nenhum pedido: apenas Diego.",
    ["possuem pelo menos um pedido: Ana, Bruno e Carla.", "possuem pedido de valor nulo: apenas Carla.",
     "possuem mais de um pedido: Ana e Carla.", "moram em Santos: Ana e Carla."],
    "NOT IN com subconsulta: letra {G}.\n\n"
    "A subconsulta devolve os cliente_id que têm pedido: 1, 1, 2, 3, 3. NOT IN pega quem NÃO está nessa lista: o cliente 4, Diego.\n\n"
    "Três jeitos de responder 'clientes sem pedido':\n\n"
    "1. WHERE id NOT IN (SELECT cliente_id FROM PEDIDO)\n\n"
    "2. WHERE NOT EXISTS (SELECT 1 FROM PEDIDO p WHERE p.cliente_id = c.id)\n\n"
    "3. LEFT JOIN ... WHERE p.id IS NULL\n\n"
    "Cuidado com o NOT IN: se a subconsulta devolver algum NULL, o resultado inteiro fica VAZIO (comparar com NULL dá desconhecido). NOT EXISTS não tem esse problema — por isso é o preferido.",
    formato="codigo",
    codigo="SELECT nome\nFROM CLIENTE\nWHERE id NOT IN (SELECT cliente_id FROM PEDIDO);",
    verificar=confere("SELECT nome FROM CLIENTE WHERE id NOT IN (SELECT cliente_id FROM PEDIDO)", [("Diego",)]),
)
T.fixa(
    BASE + "As consultas Q1 e Q2 abaixo retornam, respectivamente, quantas linhas?",
    ["3 e 4", "3 e 3", "4 e 4", "4 e 3", "2 e 4"],
    "A",
    "UNION × UNION ALL: letra A, 3 e 4.\n\n"
    "As cidades dos clientes são Santos, Campinas, Santos, Sorocaba (4 valores, 3 distintos).\n\n"
    "Q1 usa UNION, que REMOVE duplicatas: Santos, Campinas, Sorocaba → 3.\n\nQ2 usa UNION ALL, que mantém tudo: 4.\n\n"
    "Detalhe: o UNION remove duplicatas também DENTRO de cada SELECT, não só entre eles. Por isso Santos, que se repete no próprio CLIENTE, aparece uma vez.\n\n"
    "Desempenho: UNION ALL é mais rápido, porque não precisa ordenar ou fazer hash para achar repetidos. Se não há duplicata possível, prefira UNION ALL.",
    formato="codigo",
    codigo="-- Q1\nSELECT cidade FROM CLIENTE WHERE id <= 2\nUNION\nSELECT cidade FROM CLIENTE WHERE id >= 3;\n\n-- Q2\nSELECT cidade FROM CLIENTE WHERE id <= 2\nUNION ALL\nSELECT cidade FROM CLIENTE WHERE id >= 3;",
    verificar=lambda: (
        confere("SELECT count(*) FROM (SELECT cidade FROM CLIENTE WHERE id <= 2 UNION SELECT cidade FROM CLIENTE WHERE id >= 3)", [(3,)])(),
        confere("SELECT count(*) FROM (SELECT cidade FROM CLIENTE WHERE id <= 2 UNION ALL SELECT cidade FROM CLIENTE WHERE id >= 3)", [(4,)])(),
    ),
)
T.mc(
    "No Microsoft SQL Server, a consulta que retorna os três pedidos de maior valor é",
    "SELECT TOP 3 id, valor FROM PEDIDO ORDER BY valor DESC;",
    ["SELECT id, valor FROM PEDIDO ORDER BY valor DESC LIMIT 3;",
     "SELECT TOP 3 id, valor FROM PEDIDO ORDER BY valor ASC;",
     "SELECT id, valor FROM PEDIDO WHERE ROWNUM <= 3 ORDER BY valor DESC;",
     "SELECT MAX(3) id, valor FROM PEDIDO;"],
    "Três maiores no SQL Server: letra {G}, TOP 3 com ORDER BY ... DESC.\n\n"
    "| SGBD | Limitar linhas |\n|---|---|\n| SQL Server | SELECT TOP 3 ... |\n| MySQL, PostgreSQL | ... LIMIT 3 |\n"
    "| Oracle (antigo) | WHERE ROWNUM <= 3 |\n| padrão SQL (SQL Server 2012+, PostgreSQL, Oracle 12c+) | ... OFFSET 0 ROWS FETCH NEXT 3 ROWS ONLY |\n\n"
    "LIMIT é do MySQL e do PostgreSQL — não roda no SQL Server. ORDER BY ASC traria os três MENORES. "
    "Sem ORDER BY, TOP devolve 3 linhas quaisquer: a ordem de uma tabela não é garantida.",
    dificuldade=1,
)
T.fixa(
    "Na execução lógica de uma consulta SQL que usa SELECT, FROM, WHERE, GROUP BY, HAVING e ORDER BY, a ordem em que as cláusulas são avaliadas é",
    ["FROM, WHERE, GROUP BY, HAVING, SELECT, ORDER BY.",
     "SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY.",
     "FROM, SELECT, WHERE, GROUP BY, ORDER BY, HAVING.",
     "WHERE, FROM, HAVING, GROUP BY, SELECT, ORDER BY.",
     "FROM, GROUP BY, WHERE, HAVING, ORDER BY, SELECT."],
    "A",
    "Ordem LÓGICA de avaliação: letra A.\n\n"
    "1. FROM (e JOINs) — monta as linhas de origem\n\n2. WHERE — filtra linhas\n\n3. GROUP BY — agrupa\n\n4. HAVING — filtra grupos\n\n5. SELECT — calcula as colunas e os apelidos\n\n6. ORDER BY — ordena (e depois TOP/LIMIT)\n\n"
    "Isso explica dois comportamentos que caem em prova:\n\n"
    "— o apelido criado no SELECT NÃO pode ser usado no WHERE (o WHERE roda antes), mas PODE no ORDER BY (que roda depois);\n\n"
    "— agregação não cabe no WHERE porque os grupos ainda não existem.\n\n"
    "A segunda alternativa é a ordem em que se ESCREVE, não a em que se avalia.",
    dificuldade=2,
)
T.mc(
    "Um analista executou, sem perceber, o comando abaixo em produção:\n\nUPDATE FUNCIONARIO SET salario = salario * 1.10;\n\nO efeito do comando é",
    "aumentar em 10% o salário de todos os funcionários da tabela.",
    ["gerar erro, pois o UPDATE exige cláusula WHERE.",
     "aumentar em 10% apenas o salário do primeiro funcionário da tabela.",
     "não alterar nada até que seja executado um SELECT de confirmação.",
     "aumentar o salário apenas dos funcionários cujo salário não seja nulo, zerando os demais."],
    "UPDATE sem WHERE: letra {G} — atinge TODAS as linhas.\n\n"
    "O WHERE é opcional em UPDATE e DELETE. Sem ele, o comando vale para a tabela inteira. Não há erro nem confirmação.\n\n"
    "Detalhe da última alternativa: salário NULL × 1,10 continua NULL — não vira zero.\n\n"
    "Defesas: rodar dentro de transação (BEGIN ... conferir ... COMMIT ou ROLLBACK); testar o WHERE antes com SELECT; no MySQL, o modo --safe-updates recusa UPDATE/DELETE sem WHERE pela chave.\n\n"
    "E se já foi confirmado: aí é caso de restauração até um ponto no tempo (backup de log) — assunto de backup.",
    dificuldade=1,
)
T.mc(
    "Sobre os comandos DELETE, TRUNCATE e DROP aplicados à tabela LOG_ACESSO, é correto afirmar que",
    "DELETE sem WHERE remove todas as linhas mantendo a estrutura, TRUNCATE remove todas as linhas mantendo a estrutura e em geral de forma mais rápida, e DROP remove a tabela inteira, inclusive sua estrutura.",
    ["os três removem a estrutura da tabela, diferindo apenas na velocidade.",
     "TRUNCATE aceita cláusula WHERE para remover linhas específicas.",
     "DROP remove apenas os dados, preservando a definição da tabela para uso futuro.",
     "DELETE é um comando DDL, e TRUNCATE é um comando DML."],
    "DELETE × TRUNCATE × DROP: letra {G}.\n\n"
    "| Comando | Tipo | Remove | WHERE? | Dispara trigger de DELETE? |\n|---|---|---|---|---|\n"
    "| DELETE | DML | linhas (todas ou as do WHERE) | sim | sim |\n"
    "| TRUNCATE | DDL | todas as linhas; mantém a estrutura | não | não |\n"
    "| DROP | DDL | a tabela inteira (estrutura, índices, permissões) | não | — |\n\n"
    "O TRUNCATE é mais rápido porque desaloca páginas em vez de registrar linha a linha no log, e reinicia o contador IDENTITY/AUTO_INCREMENT. "
    "No SQL Server e no PostgreSQL ele pode ser desfeito se estiver dentro de transação explícita; no MySQL, não.\n\n"
    "A última alternativa inverte as categorias.",
)
T.mc(
    "Sobre stored procedures e funções definidas pelo usuário (user-defined functions) no Microsoft SQL Server, é correto afirmar que",
    "uma função escalar retorna um único valor e pode ser usada dentro de um SELECT, mas não pode alterar dados de tabelas permanentes; a procedure pode executar INSERT, UPDATE e DELETE e é chamada com EXEC.",
    ["procedures podem ser chamadas diretamente dentro de uma cláusula WHERE, como uma coluna.",
     "funções podem executar INSERT, UPDATE e DELETE em qualquer tabela, assim como as procedures.",
     "procedures não aceitam parâmetros de entrada nem de saída.",
     "funções e procedures são executadas automaticamente quando ocorre um evento na tabela."],
    "Procedure × função no SQL Server: letra {G}.\n\n"
    "| | Stored procedure | Função (UDF) |\n|---|---|---|\n"
    "| chamada | EXEC proc @p = 1 | dentro da consulta: SELECT dbo.fn(col) |\n"
    "| retorno | opcional; parâmetros OUTPUT e conjuntos de resultado | obrigatório: um valor (escalar) ou uma tabela |\n"
    "| altera dados? | sim (INSERT, UPDATE, DELETE, DDL) | não, em tabelas permanentes |\n"
    "| controle de transação | sim | não |\n\n"
    "Execução automática por evento é o TRIGGER, não procedure nem função.\n\n"
    "Exemplo:\n\nCREATE FUNCTION dbo.fn_com_imposto (@v DECIMAL(10,2)) RETURNS DECIMAL(10,2)\nAS BEGIN RETURN @v * 1.15; END;\n\nSELECT id, dbo.fn_com_imposto(valor) FROM PEDIDO;",
    dificuldade=2,
)
T.mc(
    "Em um trigger AFTER UPDATE escrito em T-SQL no Microsoft SQL Server, os valores das linhas antes e depois da alteração podem ser consultados, respectivamente, nas tabelas lógicas",
    "deleted e inserted.",
    ["inserted e deleted.", "OLD e NEW.", "before e after.", "old_values e new_values."],
    "Antes e depois num trigger do SQL Server: letra {G}, deleted (antes) e inserted (depois).\n\n"
    "| Evento | inserted | deleted |\n|---|---|---|\n| INSERT | linhas novas | vazia |\n| DELETE | vazia | linhas apagadas |\n"
    "| UPDATE | valores NOVOS | valores ANTIGOS |\n\n"
    "Um UPDATE, para o SQL Server, é 'apagar a versão velha e inserir a nova' — por isso usa as duas.\n\n"
    "OLD e NEW são do MySQL e do PostgreSQL (NEW.salario, OLD.salario), e lá o trigger é por LINHA; no SQL Server o trigger dispara uma vez por COMANDO, e inserted/deleted podem ter várias linhas.\n\n"
    "Erro clássico: escrever trigger de SQL Server supondo uma linha só (SELECT @x = valor FROM inserted). Com UPDATE de 100 linhas, pega uma e ignora 99.",
    dificuldade=3,
)
T.mc(
    "No MySQL, deseja-se impedir que o preço de um produto seja gravado com valor negativo, ajustando-o para zero antes da gravação. O tipo de trigger adequado e a forma de referenciar o novo valor são",
    "BEFORE INSERT (e BEFORE UPDATE), alterando NEW.preco.",
    ["AFTER INSERT, alterando OLD.preco.", "AFTER DELETE, alterando NEW.preco.",
     "BEFORE INSERT, alterando OLD.preco.", "INSTEAD OF INSERT, alterando inserted.preco."],
    "Corrigir o valor ANTES de gravar, no MySQL: letra {G}.\n\n"
    "CREATE TRIGGER trg_preco BEFORE INSERT ON produto\nFOR EACH ROW\nBEGIN\n  IF NEW.preco < 0 THEN SET NEW.preco = 0; END IF;\nEND;\n\n"
    "Só um trigger BEFORE pode modificar NEW: no AFTER a linha já foi gravada. OLD não existe num INSERT (não há versão anterior). "
    "INSTEAD OF e inserted são do SQL Server; no MySQL não há INSTEAD OF.\n\n"
    "| | MySQL / PostgreSQL | SQL Server |\n|---|---|---|\n| momento | BEFORE, AFTER | AFTER (FOR), INSTEAD OF |\n"
    "| granularidade | FOR EACH ROW | uma vez por comando |\n| valores | NEW, OLD | inserted, deleted |",
    dificuldade=3,
)
T.mc(
    "No Microsoft SQL Server, para permitir operações de INSERT em uma visão (view) que junta várias tabelas, redistribuindo os dados para as tabelas-base corretas, pode-se usar um trigger do tipo",
    "INSTEAD OF INSERT definido sobre a view.",
    ["AFTER INSERT definido sobre a view.", "BEFORE INSERT definido sobre cada tabela-base.",
     "FOR EACH ROW definido sobre o banco de dados.", "DDL trigger ON DATABASE FOR CREATE_VIEW."],
    "INSERT numa view de várias tabelas: letra {G}, INSTEAD OF.\n\n"
    "Uma view com JOIN normalmente não é atualizável: o SGBD não sabe em qual tabela gravar. O trigger INSTEAD OF intercepta o INSERT e, NO LUGAR DELE, executa o código que você escreveu — inserindo em cada tabela-base o pedaço que lhe cabe.\n\n"
    "AFTER não serve em view (não há gravação anterior a que reagir). BEFORE não existe no SQL Server. Trigger DDL reage a CREATE/ALTER/DROP, não a dados.",
    dificuldade=3,
)
T.mc(
    BASE + "A consulta abaixo retorna",
    "Bruno.",
    ["Ana e Carla.", "Ana.", "Bruno e Carla.", "nenhuma linha."],
    "LIKE '_r%': letra {G}, Bruno.\n\n"
    "| Curinga | Significa |\n|---|---|\n| % | qualquer sequência, inclusive vazia |\n| _ | exatamente UM caractere |\n\n"
    "'_r%' = qualquer primeiro caractere, 'r' na SEGUNDA posição, depois qualquer coisa. Bruno: B, r ✓. Carla: C, a ✗ (o 'r' é a terceira letra). Ana, Diego ✗.\n\n"
    "Lembrete de desempenho: LIKE 'Br%' pode usar índice; LIKE '%no' e LIKE '_r%' começam com curinga e não aproveitam índice B-tree comum.",
    formato="codigo",
    codigo="SELECT nome FROM CLIENTE WHERE nome LIKE '_r%';",
    verificar=confere("SELECT nome FROM CLIENTE WHERE nome LIKE '_r%'", [("Bruno",)]),
)
T.fixa(
    BASE + "Quantas linhas são retornadas pela consulta abaixo?",
    ["0", "1", "2", "3", "4"],
    "C",
    "BETWEEN 80 AND 100: letra C, 2 linhas.\n\n"
    "BETWEEN inclui os DOIS extremos: equivale a valor >= 80 AND valor <= 100. Entram 100 (pedido 10) e 80 (pedido 12). 250 e 40 ficam fora; o NULL também (comparação com NULL é desconhecida).\n\n"
    "Quem acha que BETWEEN exclui os limites marca 0. Quem conta o NULL marca 3.\n\n"
    "Cuidado com data e hora: BETWEEN '2025-01-01' AND '2025-01-31' numa coluna DATETIME perde tudo do dia 31 depois da meia-noite. "
    "Para intervalo de datas, prefira >= início AND < dia seguinte.",
    formato="codigo",
    codigo="SELECT id FROM PEDIDO WHERE valor BETWEEN 80 AND 100;",
    verificar=confere("SELECT count(*) FROM PEDIDO WHERE valor BETWEEN 80 AND 100", [(2,)]),
)
T.fixa(
    "Sobre stored procedures, analise as afirmativas a seguir.",
    AF3, "C",
    "Quais estão certas? Letra C: I e II.\n\n"
    "I — certa. A procedure guarda a lógica no servidor: várias aplicações chamam a mesma rotina, e o plano de execução pode ser reaproveitado.\n\n"
    "II — certa. Segurança: dá-se EXECUTE na procedure sem dar acesso direto às tabelas. O usuário consegue registrar uma venda pela procedure, mas não consegue apagar a tabela de vendas.\n\n"
    "III — errada. Executar automaticamente em resposta a INSERT, UPDATE ou DELETE é definição de TRIGGER. A procedure só roda quando alguém a chama (EXEC no SQL Server, CALL no MySQL e no PostgreSQL).",
    afirmacoes=[
        "Stored procedures permitem centralizar regras de negócio no SGBD e reutilizá-las por diferentes aplicações.",
        "É possível conceder a um usuário permissão para executar uma stored procedure sem conceder permissão direta sobre as tabelas que ela manipula.",
        "Uma stored procedure é executada automaticamente sempre que ocorre uma operação de INSERT, UPDATE ou DELETE na tabela a que está associada.",
    ],
    formato="afirmacoes",
)
T.mc(
    BASE + "A consulta abaixo, que usa uma subconsulta correlacionada, retorna",
    "os pedidos 11 e 14, que são os de maior valor de seus respectivos clientes, excluindo Bruno.",
    ["apenas o pedido 11, o de maior valor da tabela.",
     "os pedidos 11, 12 e 14, o de maior valor de cada cliente.",
     "todos os pedidos com valor acima da média geral.",
     "um erro, pois a subconsulta referencia a tabela da consulta externa."],
    "Subconsulta correlacionada: letra {G}.\n\n"
    "Para CADA pedido p da consulta externa, a subconsulta calcula o maior valor do MESMO cliente (p2.cliente_id = p.cliente_id) e compara.\n\n"
    "| Cliente | Maior valor | Pedido que é o maior |\n|---|---|---|\n| Ana (1) | 250 | 11 |\n| Bruno (2) | 80 | 12 |\n| Carla (3) | 40 (MAX ignora o NULL) | 14 |\n\n"
    "Até aí seriam 11, 12 e 14. Mas a consulta exclui o cliente 2 no WHERE externo, então sobram 11 e 14.\n\n"
    "Ela é 'correlacionada' porque depende de uma coluna da consulta externa; em tese, roda uma vez por linha externa. Não é erro — é recurso padrão.",
    formato="codigo", dificuldade=3,
    codigo="SELECT p.id\nFROM PEDIDO p\nWHERE p.cliente_id <> 2\n  AND p.valor = (SELECT MAX(p2.valor)\n                 FROM PEDIDO p2\n                 WHERE p2.cliente_id = p.cliente_id);",
    verificar=confere("SELECT p.id FROM PEDIDO p WHERE p.cliente_id <> 2 AND p.valor = (SELECT MAX(p2.valor) FROM PEDIDO p2 WHERE p2.cliente_id = p.cliente_id) ORDER BY p.id", [(11,), (14,)]),
)

# ── Funções definidas pelo usuário (07/10/2026: o edital cita "funções" e o
# estoque do simulado não tinha nenhuma) ──
UDF = "Funções definidas pelo usuário"
T.mc(
    "No Microsoft SQL Server, uma função escalar definida pelo usuário (CREATE FUNCTION ... RETURNS DECIMAL(10,2)) diferencia-se de uma stored procedure porque a função",
    "pode ser usada dentro de uma instrução SELECT, como em SELECT dbo.fn_imposto(valor) FROM PEDIDO, e obrigatoriamente retorna um valor.",
    ["não pode receber parâmetros de entrada.",
     "pode executar INSERT, UPDATE e DELETE em tabelas permanentes livremente.",
     "é executada automaticamente após cada INSERT na tabela associada.",
     "só existe no MySQL, não no SQL Server."],
    "Função × procedure: letra {G}.\n\n"
    "| | Função (UDF) | Stored procedure |\n|---|---|---|\n| como chama | dentro do SQL: SELECT, WHERE, FROM | EXEC / CALL |\n"
    "| retorno | obrigatório (um valor ou uma tabela) | opcional (parâmetros OUTPUT, conjuntos de resultado) |\n"
    "| altera dados? | no SQL Server, NÃO pode alterar tabelas permanentes | pode |\n| transação (COMMIT/ROLLBACK) | não | pode |\n\n"
    "Executar sozinha depois de um INSERT é trigger. Funções existem em todos os grandes SGBDs: SQL Server, MySQL, PostgreSQL e Oracle.",
    dificuldade=2, assunto=UDF,
)
T.mc(
    "No Microsoft SQL Server, a função criada pelo código abaixo é uma função",
    "com valor de tabela (table-valued) em linha, usada na cláusula FROM, como em SELECT * FROM dbo.fn_pedidos_cliente(1);",
    ["escalar, usada no SELECT como se fosse uma coluna.",
     "que só pode ser executada com o comando EXEC, como uma stored procedure.",
     "de gatilho (trigger) do tipo INSTEAD OF.",
     "que grava fisicamente o resultado, como uma view materializada."],
    "RETURNS TABLE: letra {G}.\n\n"
    "| Tipo de UDF no SQL Server | Retorna | Onde se usa |\n|---|---|---|\n| escalar | um valor (RETURNS INT, DECIMAL...) | SELECT, WHERE |\n"
    "| table-valued em linha (inline) | RETURNS TABLE AS RETURN (SELECT ...) | FROM, como uma tabela |\n| table-valued multi-instrução | RETURNS @t TABLE (...) com corpo BEGIN...END | FROM |\n\n"
    "A inline funciona como uma view com parâmetro: o resultado não é guardado, a consulta roda a cada chamada.",
    formato="codigo", dificuldade=2, assunto=UDF, linguagem="sql",
    codigo="CREATE FUNCTION dbo.fn_pedidos_cliente (@cliente INT)\nRETURNS TABLE\nAS\nRETURN (\n    SELECT id, valor\n    FROM PEDIDO\n    WHERE cliente_id = @cliente\n);",
)
T.mc(
    "No MySQL, ao criar uma função armazenada com CREATE FUNCTION, declará-la como DETERMINISTIC significa informar que ela",
    "sempre produz o mesmo resultado para os mesmos parâmetros de entrada.",
    ["só pode ser chamada uma vez por sessão.",
     "não pode ler nenhuma tabela do banco.",
     "é executada em paralelo pelo servidor.",
     "é recompilada a cada chamada."],
    "DETERMINISTIC: letra {G}.\n\n"
    "Determinística = mesma entrada, mesma saída (ex.: calcular imposto de um valor). NOT DETERMINISTIC = pode mudar entre chamadas (ex.: usa NOW() ou RAND()).\n\n"
    "Por que importa: com o log binário ligado (replicação), o MySQL exige que a função declare DETERMINISTIC, NO SQL ou READS SQL DATA, senão recusa o CREATE FUNCTION — uma função não determinística poderia dar resultado diferente na réplica.\n\n"
    "| Cláusula | Diz que a função |\n|---|---|\n| DETERMINISTIC | sempre igual para a mesma entrada |\n| NO SQL | não tem SQL |\n| READS SQL DATA | só lê dados |\n| MODIFIES SQL DATA | altera dados |",
    dificuldade=3, assunto=UDF,
)
