from base import AF3, AF3b, Topico

T = Topico("Tuning e desempenho", 5, "bd-tuning-desempenho",
           "Tuning e desempenho: índices, otimização de consultas e análise de performance")

T.mc(
    "No MySQL e no PostgreSQL, o comando que exibe o plano de execução escolhido pelo otimizador para uma consulta — indicando, por exemplo, se haverá varredura completa da tabela ou uso de índice — é o",
    "EXPLAIN.",
    ["DESCRIBE TABLE.", "SHOW INDEXES.", "ANALYZE TABLE, que executa a consulta e devolve as linhas.", "OPTIMIZE QUERY."],
    "Ver o plano de execução: letra {G}, EXPLAIN.\n\n"
    "EXPLAIN SELECT * FROM pedido WHERE cliente_id = 42;\n\n"
    "O que procurar na saída:\n\n"
    "| Sinal | MySQL | PostgreSQL |\n|---|---|---|\n| varredura completa (ruim em tabela grande) | type = ALL | Seq Scan |\n"
    "| uso de índice | type = ref / range / const; coluna key | Index Scan / Index Only Scan |\n| estimativa de linhas | rows | rows |\n\n"
    "EXPLAIN mostra o plano ESTIMADO sem executar. EXPLAIN ANALYZE (PostgreSQL e MySQL 8.0.18+) EXECUTA a consulta e mostra tempos reais — cuidado com UPDATE/DELETE: eles são executados de verdade.\n\n"
    "OPTIMIZE QUERY não existe. No SQL Server, o equivalente é o plano de execução do SSMS ou SET SHOWPLAN_XML ON.",
    dificuldade=1,
)
T.mc(
    "No PostgreSQL, ao executar EXPLAIN ANALYZE em uma consulta, o administrador obtém",
    "o plano de execução e as medições reais da execução, como tempo gasto e número real de linhas em cada etapa, pois a consulta é de fato executada.",
    ["apenas o plano estimado, sem executar a consulta.",
     "a lista de índices recomendados para a tabela, sem plano de execução.",
     "a atualização das estatísticas da tabela, sem exibir plano.",
     "o código-fonte da função que implementa a consulta."],
    "EXPLAIN ANALYZE no PostgreSQL: letra {G}.\n\n"
    "| Comando | Executa? | Mostra |\n|---|---|---|\n| EXPLAIN | não | plano e custos ESTIMADOS |\n| EXPLAIN ANALYZE | SIM | plano + tempo real + linhas reais por nó |\n\n"
    "O ponto de diagnóstico é comparar 'rows' estimado com 'actual rows'. Se o otimizador estimou 10 linhas e vieram 2 milhões, as estatísticas estão desatualizadas ou enganosas, e o plano escolhido provavelmente é ruim.\n\n"
    "Atualizar estatísticas é o comando ANALYZE sozinho (sem EXPLAIN) — confusão comum por causa do nome.\n\n"
    "Para testar UPDATE ou DELETE com EXPLAIN ANALYZE sem estragar dados: BEGIN; EXPLAIN ANALYZE ...; ROLLBACK;",
    dificuldade=2,
)
T.mc(
    "A coluna data_venda da tabela VENDAS possui índice. A consulta SELECT * FROM VENDAS WHERE YEAR(data_venda) = 2025; está lenta e faz varredura completa. Uma reescrita que permite ao otimizador usar o índice é",
    "SELECT * FROM VENDAS WHERE data_venda >= '2025-01-01' AND data_venda < '2026-01-01';",
    ["SELECT * FROM VENDAS WHERE YEAR(data_venda) LIKE '2025%';",
     "SELECT * FROM VENDAS WHERE CAST(data_venda AS VARCHAR(10)) LIKE '2025%';",
     "SELECT DISTINCT * FROM VENDAS WHERE YEAR(data_venda) = 2025;",
     "SELECT * FROM VENDAS WHERE YEAR(data_venda) = 2025 ORDER BY data_venda;"],
    "Função aplicada à coluna indexada: letra {G}, trocar por intervalo.\n\n"
    "O índice guarda os valores de data_venda ordenados, e não YEAR(data_venda). Ao aplicar uma função sobre a coluna, o SGBD precisa calcular a função em TODAS as linhas para comparar — varredura completa. "
    "A condição deixa de ser SARGABLE (Search ARGument ABLE).\n\n"
    "Regra: deixe a coluna 'nua' de um lado e mexa no OUTRO lado da comparação.\n\n"
    "| Não sargável | Sargável |\n|---|---|\n| YEAR(data) = 2025 | data >= '2025-01-01' AND data < '2026-01-01' |\n"
    "| salario * 1.1 > 5000 | salario > 5000 / 1.1 |\n| UPPER(nome) = 'ANA' | nome = 'ANA' (com collation CI) |\n| CAST(col AS VARCHAR) LIKE ... | comparação no tipo original |\n\n"
    "Usar < 1º de janeiro do ano seguinte, e não <= 31/12, não perde os registros de 31/12 com horário.",
    dificuldade=2,
)
T.mc(
    "A coluna nome da tabela CLIENTE possui índice B-tree. Entre as condições a seguir, a que pode se beneficiar desse índice para localizar as linhas é",
    "WHERE nome LIKE 'Silv%'",
    ["WHERE nome LIKE '%Silva'", "WHERE nome LIKE '%ilv%'", "WHERE LOWER(nome) LIKE 'silv%'", "WHERE nome LIKE '_ilva%'"],
    "LIKE com índice B-tree: letra {G}.\n\n"
    "O índice B-tree é como uma lista telefônica: ordenada pelo COMEÇO do texto. 'Silv%' tem prefixo fixo, e o SGBD vai direto ao trecho que começa com 'Silv' (index seek / range scan).\n\n"
    "| Padrão | Usa o índice para buscar? |\n|---|---|\n| 'Silv%' | sim (prefixo conhecido) |\n| '%Silva', '%ilv%' | não (o começo é desconhecido) |\n"
    "| '_ilva%' | não (o 1º caractere é curinga) |\n| LOWER(nome) LIKE ... | não (função na coluna), salvo índice de expressão |\n\n"
    "Para buscar texto no meio, o caminho é índice de texto completo (FULLTEXT no MySQL e no SQL Server; GIN com pg_trgm no PostgreSQL).",
    dificuldade=2,
)
T.mc(
    "Foi criado o índice composto CREATE INDEX ix_pedido ON PEDIDO (cliente_id, data_pedido). Esse índice NÃO é aproveitado para buscar diretamente as linhas na consulta com o filtro",
    "WHERE data_pedido = '2025-03-10'",
    ["WHERE cliente_id = 15", "WHERE cliente_id = 15 AND data_pedido = '2025-03-10'",
     "WHERE cliente_id = 15 AND data_pedido >= '2025-01-01'", "WHERE cliente_id IN (15, 16) AND data_pedido = '2025-03-10'"],
    "Índice (cliente_id, data_pedido) e filtro só por data: letra {G}.\n\n"
    "Regra do PREFIXO À ESQUERDA: o índice composto é ordenado primeiro por cliente_id e, dentro de cada cliente, por data. "
    "Ele serve a buscas que começam pela primeira coluna. Filtrar só pela segunda é como procurar na lista telefônica pelo PRIMEIRO nome: a ordenação não ajuda.\n\n"
    "| Filtro | Usa o índice? |\n|---|---|\n| cliente_id | sim |\n| cliente_id + data | sim, melhor caso |\n| cliente_id + intervalo de data | sim |\n| só data_pedido | não para seek (no máximo uma varredura do índice) |\n\n"
    "Consequência de projeto: a coluna mais usada sozinha em filtros vai PRIMEIRO no índice composto.",
    formato="negativa", dificuldade=2,
)
T.mc(
    "Uma tabela de log recebe milhares de inserções por segundo e é raramente consultada. Um analista sugeriu criar índices em todas as suas colunas para melhorar o desempenho. Essa sugestão é inadequada porque",
    "cada índice adicional precisa ser atualizado a cada INSERT, UPDATE e DELETE, o que aumenta o custo de escrita e o espaço ocupado.",
    ["índices só podem ser criados em colunas de chave primária.",
     "índices tornam as consultas SELECT mais lentas em qualquer situação.",
     "o SGBD ignora índices em tabelas com mais de mil linhas.",
     "índices impedem a execução de comandos INSERT na tabela."],
    "Índice em tudo numa tabela de escrita intensa: letra {G}.\n\n"
    "Índice é troca: acelera a LEITURA que o usa e encarece toda ESCRITA, porque cada INSERT grava a linha e uma entrada em CADA índice. "
    "Numa tabela que quase só recebe inserção, índices extras só custam: CPU, I/O, espaço e mais bloqueio.\n\n"
    "Critério para criar índice:\n\n— a coluna aparece com frequência em WHERE, JOIN ou ORDER BY;\n\n— é seletiva (filtra poucas linhas);\n\n— a tabela é mais lida do que escrita.\n\n"
    "Criar índice em coluna de FK é quase sempre bom; criar em todas as colunas, quase nunca.",
)
T.mc(
    "Em uma tabela com 5 milhões de clientes, a coluna sexo possui apenas os valores 'F' e 'M', distribuídos de forma equilibrada. Um índice B-tree comum nessa coluna tende a ser pouco útil para a consulta WHERE sexo = 'F' porque",
    "a coluna tem baixa seletividade: o filtro retorna cerca de metade da tabela, e ler tudo sequencialmente costuma ser mais barato que acessar milhões de linhas pelo índice.",
    ["índices B-tree não podem ser criados em colunas do tipo CHAR.",
     "a coluna tem alta cardinalidade, o que impede o uso do índice.",
     "o otimizador nunca usa índices em consultas com igualdade.",
     "índices só funcionam em colunas numéricas."],
    "Índice em coluna com dois valores: letra {G}, baixa SELETIVIDADE.\n\n"
    "Seletividade = proporção de linhas que o filtro devolve. Quanto MENOR a fração devolvida, mais útil o índice.\n\n"
    "WHERE sexo = 'F' devolve ~50% da tabela. Ir ao índice e depois buscar 2,5 milhões de linhas espalhadas é mais caro que varrer a tabela em sequência — e o otimizador sabe disso: ignora o índice.\n\n"
    "| Coluna | Cardinalidade (valores distintos) | Índice B-tree |\n|---|---|---|\n| CPF | altíssima | ótimo |\n| cidade | média | depende do filtro |\n| sexo, status ativo/inativo | baixíssima | pouco útil |\n\n"
    "A alternativa 'alta cardinalidade' inverte o conceito. Para colunas de baixa cardinalidade em data warehouse, existe o índice BITMAP (Oracle).",
    dificuldade=2,
)
T.mc(
    "No SQL Server, a consulta SELECT nome, email FROM CLIENTE WHERE cidade = 'Santos' é muito frequente. Para que ela seja respondida inteiramente pelo índice, sem acessar a tabela, o DBA pode criar",
    "CREATE INDEX ix_cidade ON CLIENTE (cidade) INCLUDE (nome, email);",
    ["CREATE INDEX ix_cidade ON CLIENTE (nome);",
     "CREATE CLUSTERED INDEX ix_email ON CLIENTE (email);",
     "CREATE INDEX ix_cidade ON CLIENTE (email, nome);",
     "CREATE STATISTICS st_cidade ON CLIENTE (cidade);"],
    "Índice que responde à consulta sozinho: letra {G}, índice de COBERTURA (covering index).\n\n"
    "A chave do índice é cidade (a coluna do WHERE); nome e email vão no INCLUDE, guardados só no nível folha. "
    "A consulta encontra as linhas pela cidade e já acha ali as colunas do SELECT — sem a ida extra à tabela (o 'key lookup' do plano do SQL Server).\n\n"
    "Índice só em nome não ajuda o WHERE. (email, nome) não começa por cidade. Estatística não é índice. "
    "E um segundo índice CLUSTERED é impossível, se a tabela já tem o da chave primária.\n\n"
    "Por isso SELECT * atrapalha: nenhum índice cobre todas as colunas.",
    dificuldade=3,
)
T.mc(
    "Após uma carga que inseriu milhões de linhas em uma tabela, consultas que antes eram rápidas passaram a usar planos de execução ineficientes, embora os índices continuem existindo. Uma causa provável e a ação correspondente são",
    "estatísticas desatualizadas; atualizá-las com UPDATE STATISTICS (SQL Server) ou ANALYZE (PostgreSQL e MySQL).",
    ["corrupção do log de transações; executar BACKUP LOG.",
     "excesso de permissões; executar REVOKE em todos os usuários.",
     "falta de chave estrangeira; executar DROP TABLE e recriar a tabela.",
     "collation incompatível; reinstalar o SGBD."],
    "Plano piorou depois de grande carga, índices intactos: letra {G}.\n\n"
    "O otimizador decide com base em ESTATÍSTICAS: quantas linhas a tabela tem e como os valores se distribuem (histogramas). "
    "Depois de uma carga grande, elas descrevem a tabela antiga; o otimizador estima 1.000 linhas onde há 1 milhão e escolhe o plano errado.\n\n"
    "| SGBD | Atualizar estatísticas |\n|---|---|\n| SQL Server | UPDATE STATISTICS tabela; ou sp_updatestats |\n| PostgreSQL | ANALYZE tabela; (o autovacuum também faz) |\n| MySQL | ANALYZE TABLE tabela; |\n\n"
    "Diagnóstico: no plano real, comparar linhas estimadas com linhas reais. Diferença grande = estatística ruim.",
    dificuldade=2,
)
T.fixa(
    "Ao analisar a fragmentação dos índices de um banco no Microsoft SQL Server, o DBA encontrou: índice A com 12% de fragmentação e índice B com 65%. Segundo a recomendação usual da Microsoft, as ações adequadas são, respectivamente,",
    ["reorganizar o índice A e reconstruir o índice B.",
     "reconstruir o índice A e reorganizar o índice B.",
     "reconstruir os dois índices.",
     "excluir os dois índices e recriá-los como heap.",
     "executar DBCC SHRINKDATABASE nos dois casos."],
    "A",
    "12% e 65% de fragmentação: letra A — reorganizar o A e reconstruir o B.\n\n"
    "| Fragmentação | Ação | Comando |\n|---|---|---|\n| abaixo de ~5–10% | nada | — |\n"
    "| ~5–10% a 30% | REORGANIZE (leve, sempre online) | ALTER INDEX ix ON t REORGANIZE; |\n"
    "| acima de 30% | REBUILD (recria o índice; online só na Enterprise) | ALTER INDEX ix ON t REBUILD; |\n\n"
    "O REBUILD também atualiza as estatísticas do índice com amostragem completa; o REORGANIZE não.\n\n"
    "SHRINKDATABASE é o contrário de ajudar: ele FRAGMENTA os índices ao mover páginas.\n\n"
    "Os números de 5% e 30% são orientação antiga da Microsoft; a documentação atual recomenda medir o ganho antes. Para prova, vale a regra dos 30%.",
    dificuldade=2,
)
T.mc(
    "Ao revisar o código de uma aplicação, o DBA recomendou substituir SELECT * por uma lista explícita de colunas. Um benefício dessa mudança é",
    "reduzir o volume de dados lidos e transferidos e permitir o uso de índices de cobertura.",
    ["garantir que a consulta use sempre o índice clusterizado.",
     "eliminar a necessidade de cláusula WHERE.",
     "tornar a consulta imune a SQL injection.",
     "impedir a ocorrência de deadlocks."],
    "Trocar SELECT * por colunas explícitas: letra {G}.\n\n"
    "Ganhos:\n\n— menos bytes lidos e trafegados pela rede (colunas grandes como texto e imagem ficam de fora);\n\n"
    "— chance de o índice COBRIR a consulta;\n\n— a aplicação não quebra nem muda de comportamento quando alguém acrescenta uma coluna à tabela.\n\n"
    "Não tem relação com SQL injection (o que protege é parametrizar) nem com deadlock, e não obriga o uso de nenhum índice específico.",
    dificuldade=1,
)
T.mc(
    "No plano de execução de uma consulta que junta a tabela pequena DEPARTAMENTO (20 linhas) com a tabela grande FUNCIONARIO (2 milhões de linhas), que possui índice na coluna depto_id, o algoritmo de junção mais provavelmente escolhido pelo otimizador é o",
    "nested loops, percorrendo a tabela pequena e buscando, para cada linha, os funcionários correspondentes pelo índice.",
    ["produto cartesiano completo seguido de filtro.",
     "merge join, exigindo ordenar previamente as 2 milhões de linhas.",
     "hash join, sempre obrigatório quando há índice.",
     "union all, combinando as duas tabelas."],
    "Tabela pequena + tabela grande com índice na coluna de junção: letra {G}, nested loops.\n\n"
    "| Algoritmo | Como | Bom quando |\n|---|---|---|\n"
    "| nested loops | para cada linha da tabela externa, busca as correspondentes na interna (idealmente por índice) | entrada externa PEQUENA e índice na interna |\n"
    "| hash join | monta tabela hash com a menor e varre a maior | duas entradas grandes, sem índice útil, igualdade |\n"
    "| merge join | percorre as duas já ORDENADAS pela chave | as duas entradas já vêm ordenadas (por índice) |\n\n"
    "20 buscas por índice são baratíssimas. Hash join nunca é 'obrigatório'; merge pagaria uma ordenação enorme. Produto cartesiano não é algoritmo de junção com condição.",
    dificuldade=3,
)
T.mc(
    "Para identificar quais consultas estão lentas em um servidor MySQL de produção, registrando aquelas que ultrapassam um tempo de execução configurado, o DBA deve habilitar o",
    "slow query log.",
    ["binary log.", "general query log, que registra apenas consultas lentas.", "error log.", "relay log."],
    "Registrar consultas lentas no MySQL: letra {G}, slow query log.\n\n"
    "Ligado com slow_query_log = 1 e o limite em long_query_time (segundos). Opcionalmente, log_queries_not_using_indexes. A ferramenta mysqldumpslow (ou pt-query-digest) resume o arquivo.\n\n"
    "| Log do MySQL | Registra |\n|---|---|\n| slow query log | consultas acima do tempo limite |\n| general query log | TODA consulta recebida (pesado; só para depuração curta) |\n"
    "| binary log | alterações de dados — replicação e recuperação até um ponto no tempo |\n| error log | erros e eventos do servidor |\n| relay log | na réplica, eventos recebidos do primário |\n\n"
    "Equivalentes: no SQL Server, Query Store e Extended Events; no PostgreSQL, log_min_duration_statement e a extensão pg_stat_statements.",
    dificuldade=2,
)
T.mc(
    "No Microsoft SQL Server, o recurso que armazena automaticamente o histórico de consultas executadas, seus planos de execução e estatísticas de desempenho, permitindo identificar regressões de plano e forçar um plano anterior, é o",
    "Query Store.",
    ["SQL Server Agent.", "Database Mail.", "Resource Governor.", "Log Shipping."],
    "Histórico de consultas e planos, com opção de forçar plano: letra {G}, Query Store (desde o SQL Server 2016).\n\n"
    "Uso típico: 'a consulta ficou lenta ontem'. O Query Store mostra que o plano mudou; o DBA compara os dois e pode FORÇAR o plano antigo, bom, sem mexer no código.\n\n"
    "| Recurso | Função |\n|---|---|\n| Query Store | histórico de planos e desempenho |\n| Resource Governor | limitar CPU e memória por grupo de carga |\n"
    "| Extended Events | capturar eventos (substitui o Profiler) |\n| Database Engine Tuning Advisor | sugerir índices |\n| Log Shipping | alta disponibilidade (não é desempenho) |",
    dificuldade=2,
)
T.mc(
    "Sobre índices do tipo hash e B-tree, é correto afirmar que",
    "o índice hash é eficiente para buscas por igualdade, mas não atende a consultas por intervalo nem a ordenações, enquanto o B-tree atende a igualdade, intervalos e ORDER BY.",
    ["o índice hash é o mais indicado para consultas com BETWEEN e ORDER BY.",
     "o B-tree só atende a buscas por igualdade.",
     "os dois tipos mantêm os valores ordenados, por isso são equivalentes.",
     "o índice hash só pode ser criado em colunas de texto."],
    "Hash × B-tree: letra {G}.\n\n"
    "| | B-tree | Hash |\n|---|---|---|\n| igualdade (=) | sim | sim, muito rápido |\n| intervalo (<, >, BETWEEN) | sim | NÃO |\n"
    "| ORDER BY, prefixo de LIKE | sim | NÃO |\n| estrutura | árvore balanceada, valores em ordem | função hash espalha os valores sem ordem |\n\n"
    "O hash embaralha os valores de propósito: 100 e 101 caem em lugares sem relação. Por isso não serve para faixa.\n\n"
    "O B-tree é o padrão em praticamente todo SGBD (CREATE INDEX sem tipo cria B-tree). Hash aparece no PostgreSQL (USING HASH) e no engine MEMORY do MySQL.",
    dificuldade=2,
)
T.mc(
    "A tabela MOVIMENTO armazena 10 anos de transações, com bilhões de linhas, e quase todas as consultas filtram pelo mês corrente. Para reduzir o volume lido por essas consultas e facilitar o expurgo de dados antigos, uma técnica adequada é",
    "particionar a tabela por intervalo de data, para que as consultas acessem apenas as partições envolvidas.",
    ["remover a chave primária da tabela.",
     "converter todas as colunas para o tipo texto.",
     "desativar o log de transações do banco.",
     "criar uma view sobre a tabela, o que divide fisicamente os dados."],
    "Tabela gigante consultada por período: letra {G}, particionamento por intervalo (range).\n\n"
    "A tabela continua sendo UMA para a aplicação, mas os dados ficam fisicamente separados por mês ou ano. Benefícios:\n\n"
    "— PARTITION PRUNING (eliminação de partição): a consulta do mês atual lê só a partição do mês;\n\n"
    "— expurgo barato: apagar um ano é remover ou trocar a partição (DROP/TRUNCATE PARTITION, SWITCH no SQL Server), em vez de um DELETE de bilhões de linhas;\n\n"
    "— manutenção de índice por partição.\n\n"
    "View não divide nada fisicamente. Tirar a chave primária ou o log degrada a integridade e a recuperação.",
    dificuldade=2,
)
T.mc(
    "Uma tela de relatório executa, a cada acesso, uma consulta pesada que soma milhões de vendas por região e mês; os dados de meses fechados não mudam. Para reduzir drasticamente o tempo de resposta, uma solução adequada é",
    "armazenar o resultado agregado em uma visão materializada (ou tabela de resumo) atualizada periodicamente.",
    ["criar uma view comum, que guarda o resultado da consulta.",
     "aumentar o nível de isolamento das transações para SERIALIZABLE.",
     "remover os índices da tabela de vendas.",
     "trocar SUM por COUNT na consulta."],
    "Agregação pesada sobre dados que não mudam: letra {G}.\n\n"
    "A visão MATERIALIZADA grava o resultado; a tela passa a ler poucas linhas prontas, em vez de somar milhões a cada acesso. O custo é mantê-la atualizada (REFRESH MATERIALIZED VIEW no PostgreSQL; indexed view no SQL Server, mantida automaticamente; tabela de resumo alimentada por job no MySQL).\n\n"
    "A view COMUM é a pegadinha: ela não guarda resultado nenhum, refaz a consulta toda vez.\n\n"
    "SERIALIZABLE só aumenta bloqueio; tirar índice piora; trocar SUM por COUNT muda o resultado.",
    dificuldade=2,
)
T.fixa(
    "Sobre boas práticas de desempenho em bancos de dados, analise as afirmativas.",
    AF3, "C",
    "Quais estão certas? Letra C: I e II.\n\n"
    "I — certa. Transação longa segura bloqueios por muito tempo e aumenta espera e deadlock. Faça a interação com o usuário FORA da transação.\n\n"
    "II — certa. O SQL Server indexa a PK automaticamente, mas NÃO a FK; o MySQL/InnoDB cria índice na FK; o PostgreSQL, não. Sem índice, JOINs e a verificação de integridade ao apagar o pai varrem a tabela filha.\n\n"
    "III — errada. Índice acelera leitura e encarece escrita; a quantidade certa depende da carga. 'Quanto mais, melhor' é falso.",
    afirmacoes=[
        "Manter as transações curtas reduz o tempo em que bloqueios ficam retidos e, com isso, a contenção entre sessões.",
        "Criar índices nas colunas de chave estrangeira usadas em junções costuma melhorar o desempenho dessas junções.",
        "Quanto maior o número de índices em uma tabela, melhor o desempenho de todas as operações sobre ela.",
    ],
    formato="afirmacoes",
)
T.fixa(
    "Sobre o índice clusterizado no Microsoft SQL Server, analise as afirmativas.",
    AF3b, "C",
    "Quais estão certas? Letra C: I e III.\n\n"
    "I — certa. O índice clusterizado É a tabela: as linhas ficam armazenadas na ordem da chave do índice. Por isso só pode existir um.\n\n"
    "II — errada. Ao criar PRIMARY KEY, o SQL Server cria por padrão um índice CLUSTERIZADO (se a tabela ainda não tiver um). Pode-se pedir NONCLUSTERED explicitamente.\n\n"
    "III — certa. Chave do clusterizado crescente (IDENTITY) faz as inserções irem sempre para o fim, sem divisão de páginas. "
    "Chave aleatória como GUID gerado por NEWID() insere no meio e fragmenta — por isso existe NEWSEQUENTIALID().",
    afirmacoes=[
        "Uma tabela pode ter no máximo um índice clusterizado, pois ele define a ordem física de armazenamento das linhas.",
        "Ao criar uma PRIMARY KEY, o SQL Server cria por padrão um índice não clusterizado, nunca um clusterizado.",
        "Usar como chave do índice clusterizado uma coluna crescente, como IDENTITY, tende a reduzir a fragmentação causada por inserções.",
    ],
    formato="afirmacoes",
)
T.mc(
    "O plano de execução real de uma consulta no SQL Server mostra o operador Table Scan sobre uma tabela de 8 milhões de linhas, embora o filtro WHERE retorne apenas 15 linhas. A interpretação mais adequada é que",
    "não há índice adequado para o filtro, ou ele não pôde ser usado, e o SGBD leu a tabela inteira; um índice apropriado permitiria um Index Seek.",
    ["a consulta usou o índice da forma mais eficiente possível.",
     "o Table Scan é sempre preferível ao Index Seek em tabelas grandes.",
     "o operador indica que a consulta retornou todas as 8 milhões de linhas.",
     "a tabela está corrompida e deve ser restaurada do backup."],
    "Table Scan em 8 milhões de linhas para devolver 15: letra {G}.\n\n"
    "| Operador (SQL Server) | Significa |\n|---|---|\n| Table Scan | leu a tabela inteira (heap, sem índice clusterizado) |\n"
    "| Clustered Index Scan | leu o índice clusterizado inteiro — na prática, a tabela toda |\n| Index Seek | foi direto às linhas pelo índice |\n"
    "| Key Lookup | achou no índice não clusterizado e voltou à tabela buscar colunas que faltavam |\n\n"
    "Scan não significa que todas as linhas foram DEVOLVIDAS: elas foram LIDAS e depois filtradas. Ler 8 milhões para devolver 15 é o sintoma clássico de índice faltando ou de condição não sargável (função na coluna, conversão de tipo implícita).",
    dificuldade=2,
)
