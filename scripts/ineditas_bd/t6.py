from base import AF3, AF3b, Topico

T = Topico("Backup e recuperação", 6, "bd-backup-recuperacao",
           "Backup e recuperação: políticas de backup, restore, disaster recovery e procedimentos de continuidade de negócios")

T.mc(
    "O tipo de backup que copia apenas os dados alterados desde o último backup completo (full), independentemente de outros backups parciais feitos depois dele, é o backup",
    "diferencial.",
    ["incremental.", "completo.", "espelhado.", "de cópia (copy-only)."],
    "Alterações desde o último FULL: letra {G}, diferencial.\n\n"
    "| Tipo | Copia | Restaurar exige |\n|---|---|---|\n"
    "| completo (full) | tudo | só ele |\n"
    "| diferencial | o que mudou desde o último FULL | full + o ÚLTIMO diferencial |\n"
    "| incremental | o que mudou desde o último backup de QUALQUER tipo | full + TODOS os incrementais em sequência |\n\n"
    "O diferencial CRESCE ao longo da semana (acumula tudo desde o full), mas restaura rápido. O incremental é pequeno a cada dia, mas a restauração depende de uma corrente inteira — se um elo falhar, perde-se o resto.\n\n"
    "Atalho: Diferencial = Desde o full. Incremental = Imediatamente anterior.",
    dificuldade=1,
)
T.mc(
    "Uma empresa faz backup completo aos domingos e backups incrementais de segunda a sábado, às 23h. Na quinta-feira, às 10h, o servidor falhou. Para recuperar os dados até o último backup disponível, é necessário restaurar",
    "o backup completo de domingo e os incrementais de segunda, terça e quarta, nessa ordem.",
    ["apenas o backup completo de domingo.", "o backup completo de domingo e somente o incremental de quarta.",
     "somente os incrementais de segunda, terça e quarta.", "o incremental de quarta, seguido do completo de domingo."],
    "Full no domingo + incrementais diários, falha na quinta às 10h: letra {G}.\n\n"
    "Cada incremental guarda só o que mudou desde o backup ANTERIOR. O de quarta não contém o que mudou na segunda nem na terça. Por isso: full de domingo → incremental de segunda → terça → quarta, nessa ordem.\n\n"
    "O que se perde: tudo de quinta, da 0h às 10h. Para não perder, é preciso backup de log de transações — o que permite recuperar até um ponto no tempo.\n\n"
    "Compare: se fossem DIFERENCIAIS, bastaria full de domingo + diferencial de quarta.",
    formato="calculo", dificuldade=2,
)
T.mc(
    "Uma empresa faz backup completo aos domingos e backups diferenciais de segunda a sábado, às 23h. Na sexta-feira, às 9h, o banco foi corrompido. O conjunto mínimo de backups a restaurar para chegar ao último ponto disponível é",
    "o completo de domingo e o diferencial de quinta-feira.",
    ["o completo de domingo e os diferenciais de segunda a quinta-feira.",
     "apenas o diferencial de quinta-feira.",
     "o completo de domingo e o diferencial de segunda-feira.",
     "apenas o completo de domingo."],
    "Full no domingo + diferenciais diários, falha na sexta às 9h: letra {G}.\n\n"
    "O diferencial de quinta contém TUDO o que mudou desde domingo — inclusive o que os de segunda, terça e quarta continham. Basta o full + o ÚLTIMO diferencial.\n\n"
    "Restaurar todos os diferenciais em sequência não é errado em resultado, mas não é o MÍNIMO, e é o erro de quem confunde com incremental. O diferencial sozinho não serve: ele precisa do full como base.\n\n"
    "Perde-se o período de quinta 23h até sexta 9h, a menos que haja backup de log.",
    formato="calculo", dificuldade=1,
)
T.mc(
    "No Microsoft SQL Server, o modelo de recuperação (recovery model) que permite fazer backups do log de transações e restaurar o banco até um ponto específico no tempo é o",
    "FULL.",
    ["SIMPLE.", "BULK_LOGGED, que garante ponto no tempo em qualquer situação.", "MINIMAL.", "READ_ONLY."],
    "Ponto no tempo no SQL Server: letra {G}, modelo FULL.\n\n"
    "| Recovery model | Backup de log? | Ponto no tempo? | Log |\n|---|---|---|---|\n"
    "| SIMPLE | não | não; só até o último full ou diferencial | truncado automaticamente no checkpoint |\n"
    "| FULL | sim | sim | só é liberado após BACKUP LOG |\n"
    "| BULK_LOGGED | sim | não dentro de um backup de log que contenha operação em massa | registra minimamente as cargas em massa |\n\n"
    "MINIMAL e READ_ONLY não são modelos de recuperação.\n\n"
    "Armadilha operacional: banco em FULL SEM rotina de BACKUP LOG faz o arquivo de log crescer até lotar o disco. FULL exige backup de log agendado.",
    dificuldade=2,
)
T.mc(
    "Um banco de dados do SQL Server está configurado com o modelo de recuperação SIMPLE e recebe um backup completo diário às 22h. Às 15h, um usuário apagou por engano uma tabela importante. Nesse cenário,",
    "só é possível recuperar os dados até o backup completo das 22h do dia anterior, perdendo as alterações feitas desde então.",
    ["é possível restaurar até as 14h59, imediatamente antes da exclusão, usando o log de transações.",
     "basta executar ROLLBACK para desfazer a exclusão, mesmo após o COMMIT.",
     "o modelo SIMPLE mantém automaticamente uma cópia de cada tabela excluída.",
     "é possível fazer um backup do final do log (tail-log) para recuperar até o momento da falha."],
    "Modelo SIMPLE, backup diário às 22h, erro às 15h: letra {G}.\n\n"
    "No SIMPLE não há backup de log: o log é reaproveitado a cada checkpoint. Sem a sequência de logs, não há como recuperar até um instante — o ponto de restauração possível é o último backup completo (ou diferencial).\n\n"
    "Perda: das 22h de ontem até as 15h de hoje — essa janela é o RPO real da política.\n\n"
    "ROLLBACK só desfaz transação ainda NÃO confirmada. Backup tail-log só existe no FULL e no BULK_LOGGED.\n\n"
    "Lição: banco cujo dado do dia importa não pode ficar em SIMPLE.",
    dificuldade=2,
)
T.fixa(
    "Um banco no SQL Server, em modelo de recuperação FULL, tem backup completo às 0h e backups de log a cada hora. Às 10h40 um DELETE sem WHERE apagou a tabela de clientes. O DBA quer restaurar o banco até as 10h39. A sequência correta é:",
    ["fazer o backup do final do log (tail-log); restaurar o completo das 0h WITH NORECOVERY; restaurar os logs de 1h a 10h WITH NORECOVERY; restaurar o tail-log com STOPAT = '10:39' WITH RECOVERY.",
     "restaurar o completo das 0h WITH RECOVERY e, em seguida, os logs de 1h a 10h.",
     "restaurar apenas o backup de log das 10h WITH RECOVERY.",
     "restaurar os logs de 1h a 10h e, por último, o completo das 0h.",
     "executar ROLLBACK TO '10:39' no banco de produção."],
    "A",
    "Restaurar até as 10h39 no modelo FULL: letra A.\n\n"
    "1. BACKUP LOG ... WITH NORECOVERY (tail-log) — captura o que aconteceu entre 10h e o momento atual, inclusive o DELETE. Sem ele, o máximo seria 10h00.\n\n"
    "2. RESTORE DATABASE (full das 0h) WITH NORECOVERY.\n\n"
    "3. RESTORE LOG de cada hora, em ordem, WITH NORECOVERY.\n\n"
    "4. RESTORE LOG (tail-log) WITH STOPAT = '... 10:39', RECOVERY.\n\n"
    "| Opção | Efeito |\n|---|---|\n| WITH NORECOVERY | deixa o banco 'restaurando', aceitando o próximo backup da sequência |\n| WITH RECOVERY | finaliza: desfaz o que ficou sem COMMIT e abre o banco; depois disso, NADA mais pode ser aplicado |\n\n"
    "Usar RECOVERY no full encerra a sequência cedo demais. ROLLBACK não volta no tempo depois do COMMIT.\n\n"
    "Boa prática: restaurar numa cópia (outro nome de banco) e copiar só a tabela de volta, sem derrubar a produção inteira.",
    dificuldade=3,
)
T.mc(
    "Em um plano de continuidade, o RPO (Recovery Point Objective) de um sistema foi definido em 15 minutos. Isso significa que",
    "a organização aceita perder no máximo 15 minutos de dados, o que exige cópias (por exemplo, backups de log ou replicação) com intervalo de até 15 minutos.",
    ["o sistema deve voltar a funcionar em no máximo 15 minutos após o desastre.",
     "os backups completos devem levar no máximo 15 minutos para serem executados.",
     "os testes de restauração devem ocorrer a cada 15 minutos.",
     "os dados de backup devem ser mantidos por 15 minutos antes de descartados."],
    "RPO de 15 minutos: letra {G} — perda máxima de DADOS.\n\n"
    "| Métrica | Pergunta | Medida no eixo do tempo |\n|---|---|---|\n"
    "| RPO — Recovery Point Objective | quanto DADO posso perder? | PARA TRÁS a partir do desastre: até onde volta o último ponto recuperável |\n"
    "| RTO — Recovery Time Objective | em quanto TEMPO o sistema tem de voltar? | PARA A FRENTE: do desastre até o sistema no ar |\n\n"
    "A alternativa 'voltar a funcionar em 15 minutos' é a definição de RTO — a confusão mais cobrada.\n\n"
    "RPO de 15 min → backup de log a cada 15 min (ou replicação). RPO perto de zero → replicação síncrona.",
    dificuldade=1,
)
T.mc(
    "Após uma falha grave, o sistema de faturamento de uma empresa pode ficar fora do ar por, no máximo, 4 horas, conforme definido na análise de impacto no negócio. Esse limite corresponde ao",
    "RTO (Recovery Time Objective).",
    ["RPO (Recovery Point Objective).", "MTBF (Mean Time Between Failures).", "SLA de backup diferencial.", "ponto de verificação (checkpoint)."],
    "Tempo máximo fora do ar: letra {G}, RTO.\n\n"
    "RTO = do desastre até o serviço restabelecido. Ele dimensiona o PROCESSO de recuperação: com RTO de 4 h não dá para depender de restaurar 5 TB de fita que leva 10 h; é preciso site espelhado, réplica ou restauração mais rápida.\n\n"
    "RPO é perda de DADOS. MTBF é tempo médio entre falhas (confiabilidade). Checkpoint é mecanismo interno do SGBD que grava páginas do buffer em disco.\n\n"
    "Atalho: RPO = Ponto (dado). RTO = Tempo (volta).",
    dificuldade=1,
)
T.mc(
    "Segundo a regra 3-2-1, amplamente recomendada para políticas de backup, deve-se manter",
    "três cópias dos dados, em dois tipos de mídia diferentes, com uma cópia fora do local (off-site).",
    ["três backups completos por dia, dois diferenciais e um incremental.",
     "três servidores de banco, dois em produção e um em homologação.",
     "backups por três dias, em dois discos, com uma restauração por semana.",
     "três cópias no mesmo servidor, em duas pastas diferentes, com uma criptografada."],
    "Regra 3-2-1: letra {G}.\n\n"
    "3 — três cópias (a produção + 2 backups);\n\n2 — em duas mídias diferentes (disco e fita; disco local e nuvem);\n\n1 — uma delas FORA do local (outro prédio, outra região de nuvem).\n\n"
    "A cópia off-site protege contra incêndio, enchente, roubo. Versões atuais acrescentam '3-2-1-1-0': uma cópia IMUTÁVEL ou offline (contra ransomware, que criptografa também o backup acessível pela rede) e zero erro na verificação da restauração.\n\n"
    "Três cópias no mesmo servidor morrem juntas com ele.",
    dificuldade=1,
)
T.mc(
    "Sobre backup lógico e backup físico de bancos de dados, é correto afirmar que",
    "o backup lógico exporta os objetos e dados como comandos ou formato portátil (como mysqldump e pg_dump), enquanto o físico copia os arquivos de dados do SGBD, sendo em geral mais rápido de restaurar em bancos grandes.",
    ["o backup lógico copia os arquivos binários de dados, e o físico gera comandos SQL.",
     "o backup físico permite restaurar em qualquer SGBD de outro fabricante, por ser independente de versão.",
     "mysqldump e pg_dump são ferramentas de backup físico.",
     "o backup lógico é sempre mais rápido de restaurar do que o físico."],
    "Lógico × físico: letra {G}.\n\n"
    "| | Lógico | Físico |\n|---|---|---|\n"
    "| o que gera | CREATE TABLE + INSERT, ou formato de exportação | cópia dos arquivos de dados e log |\n"
    "| ferramentas | mysqldump, pg_dump, bcp, exportar dados | BACKUP DATABASE (SQL Server), pg_basebackup, Percona XtraBackup, MySQL Enterprise Backup, snapshot |\n"
    "| restauração | reexecuta tudo e recria índices: LENTA em banco grande | copia arquivos: rápida |\n"
    "| portabilidade | alta (outra versão, às vezes outro SGBD) | baixa (mesma versão e plataforma) |\n"
    "| granularidade | fácil restaurar uma tabela | em geral, o banco inteiro |\n\n"
    "Na prática combinam-se os dois: físico para recuperação de desastre e lógico para migrar ou recuperar uma tabela.",
    dificuldade=2,
)
T.mc(
    "Um backup realizado com o SGBD em funcionamento, sem interromper o acesso dos usuários, é chamado de backup",
    "quente (online).",
    ["frio (offline).", "diferencial.", "completo.", "incremental."],
    "Backup com o banco rodando: letra {G}, quente (online / hot).\n\n"
    "| | Quente (online) | Frio (offline) |\n|---|---|---|\n| banco | em uso | parado |\n| disponibilidade | mantida | interrompida |\n"
    "| consistência | garantida pelo SGBD (log aplicado na restauração) | trivial: nada muda durante a cópia |\n\n"
    "O BACKUP DATABASE do SQL Server, o pg_basebackup e o mysqldump --single-transaction (InnoDB) são online.\n\n"
    "Cuidado: copiar os arquivos do banco com o serviço RODANDO, por fora do SGBD (cópia de pasta comum), NÃO é backup quente — gera cópia inconsistente. O quente tem de usar o mecanismo do SGBD.\n\n"
    "Diferencial, completo e incremental classificam O QUE se copia, não se o banco está no ar.",
    dificuldade=1,
)
T.mc(
    "Para fazer backup lógico de um banco MySQL com tabelas InnoDB sem bloquear as gravações e obtendo uma cópia consistente de todas as tabelas, deve-se usar o mysqldump com a opção",
    "--single-transaction.",
    ["--lock-all-tables.", "--no-data.", "--skip-triggers.", "--compact."],
    "mysqldump consistente e sem bloqueio no InnoDB: letra {G}, --single-transaction.\n\n"
    "A opção abre uma transação em REPEATABLE READ antes de começar: o dump enxerga o banco 'congelado' no instante inicial (MVCC), enquanto os usuários continuam gravando.\n\n"
    "mysqldump --single-transaction --routines --triggers vendas > vendas.sql\n\n"
    "| Opção | Efeito |\n|---|---|\n| --lock-all-tables | bloqueia TUDO durante o dump (necessário para MyISAM) |\n| --no-data | só a estrutura |\n"
    "| --routines / --triggers | inclui procedures e triggers |\n\n"
    "Só funciona para tabelas transacionais (InnoDB). MyISAM no meio fica inconsistente.",
    dificuldade=2,
)
T.mc(
    "Uma empresa mantém uma réplica síncrona do banco de produção em outro datacenter e, por isso, decidiu abolir os backups. Essa decisão é inadequada porque",
    "a replicação copia também exclusões acidentais, corrupção lógica e ataques como ransomware, sem permitir voltar a um ponto anterior no tempo.",
    ["réplicas síncronas não mantêm os dados idênticos ao primário.",
     "a replicação só funciona com backup diferencial ativo.",
     "réplicas não podem ser usadas para leitura.",
     "a replicação síncrona impede a ocorrência de falhas de hardware."],
    "Réplica não substitui backup: letra {G}.\n\n"
    "Replicação protege contra a perda do SERVIDOR (disponibilidade). Backup protege contra a perda do DADO CERTO (recuperação no tempo).\n\n"
    "Se alguém executar DROP TABLE, a réplica síncrona executa o mesmo DROP milissegundos depois. Se um bug gravar lixo, a réplica grava o mesmo lixo. Só um backup de ANTES do erro resolve.\n\n"
    "| Mecanismo | Protege contra |\n|---|---|\n| replicação, cluster, Always On | falha de hardware, perda do datacenter |\n| backup com histórico | erro humano, corrupção lógica, ransomware, auditoria |\n\n"
    "Exceção parcial: réplica com ATRASO proposital (delayed replica) dá uma janela para reagir, mas ainda não substitui backup.",
    dificuldade=2,
)
T.mc(
    "Um DBA executa backups diários há dois anos, mas nunca testou a restauração. Do ponto de vista da política de backup, essa prática é falha porque",
    "só a restauração comprova que o backup é íntegro, completo e recuperável dentro do RTO exigido.",
    ["backups não testados ocupam o dobro do espaço em disco.",
     "testar a restauração apaga os backups mais antigos.",
     "a restauração só pode ser testada em caso de desastre real.",
     "o SGBD invalida automaticamente backups que nunca foram restaurados."],
    "Backup nunca restaurado: letra {G}.\n\n"
    "Backup que não foi testado é hipótese. Os problemas aparecem na hora da restauração: arquivo corrompido, mídia ilegível, backup que não incluía um banco novo, senha da chave de criptografia perdida, restauração que leva 12 h quando o RTO é 4 h.\n\n"
    "Boas práticas:\n\n— restaurar periodicamente em ambiente separado e rodar DBCC CHECKDB na cópia restaurada;\n\n— usar BACKUP ... WITH CHECKSUM e RESTORE VERIFYONLY (SQL Server) — verificam a legibilidade, mas NÃO substituem a restauração real;\n\n"
    "— cronometrar a restauração e comparar com o RTO;\n\n— documentar o procedimento passo a passo.",
    dificuldade=1,
)
T.mc(
    "Antes de restaurar um banco do SQL Server cujo arquivo de dados foi danificado, mas cujo arquivo de log continua acessível, o DBA deve, sempre que possível, executar um",
    "backup do final do log (tail-log backup), para não perder as transações registradas após o último backup de log.",
    ["DBCC SHRINKFILE no arquivo de log.", "backup diferencial do banco danificado.",
     "TRUNCATE em todas as tabelas.", "ALTER DATABASE ... SET RECOVERY SIMPLE."],
    "Arquivo de dados perdido, log intacto: letra {G}, tail-log backup.\n\n"
    "O log ainda guarda as transações desde o último backup de log. O tail-log captura esse 'rabo':\n\n"
    "BACKUP LOG vendas TO DISK = 'D:\\bk\\vendas_tail.trn' WITH NO_TRUNCATE, NORECOVERY;\n\n"
    "NO_TRUNCATE permite o backup mesmo com o banco danificado; NORECOVERY deixa o banco em estado de restauração, impedindo novas transações.\n\n"
    "Depois: restaurar full, diferencial, logs e, por último, o tail-log WITH RECOVERY — perda ZERO.\n\n"
    "Mudar para SIMPLE nessa hora trunca o log e joga fora exatamente o que se queria salvar.",
    dificuldade=3,
)
T.mc(
    "Em uma estratégia de recuperação de desastres, o site alternativo que já possui equipamentos instalados e dados sincronizados com a produção, podendo assumir a operação em minutos, é chamado de site",
    "quente (hot site).",
    ["frio (cold site).", "morno (warm site).", "espelho de backup em fita.", "de teste (staging)."],
    "Pronto e sincronizado, assume em minutos: letra {G}, hot site.\n\n"
    "| Site | Tem | Volta em | Custo |\n|---|---|---|---|\n"
    "| quente (hot) | equipamento + dados sincronizados (réplica) | minutos | alto |\n"
    "| morno (warm) | equipamento, dados de backup recentes, não em tempo real | horas | médio |\n"
    "| frio (cold) | espaço, energia, rede; sem equipamento ou dados prontos | dias | baixo |\n\n"
    "A escolha decorre do RTO e do RPO: RTO de minutos exige site quente; RTO de dias aceita site frio. O DRaaS (Disaster Recovery as a Service) é o site quente ou morno alugado de um provedor de nuvem.",
    dificuldade=1,
)
T.mc(
    "No processo de gestão de continuidade de negócios, a etapa que identifica os processos críticos, estima o impacto financeiro e operacional de sua interrupção ao longo do tempo e serve de base para definir RTO e RPO é a",
    "análise de impacto no negócio (BIA — Business Impact Analysis).",
    ["análise de pontos de função.", "auditoria de permissões.", "normalização dos dados.", "gestão de mudanças."],
    "Medir o impacto da parada e derivar RTO e RPO: letra {G}, BIA.\n\n"
    "Ordem típica da gestão de continuidade (ISO 22301):\n\n"
    "1. BIA — quais processos são críticos e quanto custa cada hora parada → define RTO, RPO e prioridades;\n\n"
    "2. análise de riscos — o que pode causar a parada;\n\n"
    "3. estratégia de continuidade — site quente, backup em nuvem, DRaaS;\n\n"
    "4. plano de continuidade de negócios (PCN) e plano de recuperação de desastres (PRD/DRP);\n\n"
    "5. testes, treinamento e revisão.\n\n"
    "Para o DBA: o banco do faturamento com RTO de 1 h e o banco de histórico com RTO de 3 dias recebem políticas de backup e alta disponibilidade diferentes.",
    dificuldade=2,
)
T.fixa(
    "Sobre políticas de backup de bancos de dados, analise as afirmativas a seguir.",
    AF3b, "C",
    "Quais estão certas? Letra C: I e III.\n\n"
    "I — certa. A política deve definir o quê, a frequência, o tipo, a retenção (por quanto tempo guardar), onde guardar e quem responde por isso.\n\n"
    "II — errada. Guardar o backup no mesmo disco ou servidor do banco não protege contra a falha mais básica: a perda daquele disco ou servidor.\n\n"
    "III — certa. Backup tem os mesmos dados do banco, então precisa da mesma proteção: criptografia (BACKUP ... WITH ENCRYPTION no SQL Server) e controle de acesso. Backup vazado é vazamento de dados, inclusive para a LGPD.",
    afirmacoes=[
        "A política de backup deve definir, entre outros pontos, a frequência das cópias, os tipos de backup utilizados e o prazo de retenção.",
        "Armazenar os arquivos de backup no mesmo disco dos arquivos de dados é suficiente, desde que estejam em pastas diferentes.",
        "Os arquivos de backup devem receber controles de segurança, como criptografia e restrição de acesso, pois contêm os mesmos dados sensíveis do banco.",
    ],
    formato="afirmacoes",
)
T.fixa(
    "Sobre os comandos de backup e restauração do Microsoft SQL Server, analise as afirmativas.",
    AF3, "E",
    "As três estão certas — letra E.\n\n"
    "I — BACKUP DATABASE ... WITH DIFFERENTIAL gera o backup diferencial.\n\n"
    "II — WITH COPY_ONLY gera um backup avulso que NÃO interfere na sequência: não vira a nova base dos diferenciais. Serve para tirar uma cópia para homologação sem bagunçar a estratégia da produção.\n\n"
    "III — RESTORE ... WITH NORECOVERY mantém o banco em estado de restauração para aplicar os próximos backups; o último usa WITH RECOVERY.\n\n"
    "Exemplos:\n\nBACKUP DATABASE vendas TO DISK = 'D:\\bk\\vendas_full.bak' WITH CHECKSUM;\nBACKUP DATABASE vendas TO DISK = 'D:\\bk\\vendas_dif.bak' WITH DIFFERENTIAL;\nBACKUP LOG vendas TO DISK = 'D:\\bk\\vendas_1000.trn';",
    afirmacoes=[
        "O comando BACKUP DATABASE com a opção WITH DIFFERENTIAL gera um backup diferencial.",
        "Um backup completo feito com a opção COPY_ONLY não altera a base dos backups diferenciais seguintes.",
        "Ao restaurar uma sequência de backups, todos exceto o último devem ser restaurados com a opção WITH NORECOVERY.",
    ],
    formato="afirmacoes",
    dificuldade=3,
)
T.mc(
    "No PostgreSQL, a técnica que permite restaurar um banco até um instante específico combinando um backup físico de base (como o feito com pg_basebackup) com o arquivamento contínuo dos arquivos de log de escrita antecipada é conhecida como",
    "PITR (Point-in-Time Recovery), com arquivamento de WAL.",
    ["pg_dump em formato texto.", "VACUUM FULL.", "replicação lógica por publicação.", "TRUNCATE com CASCADE."],
    "Backup de base + arquivamento contínuo do log, até um instante: letra {G}, PITR com WAL.\n\n"
    "WAL (Write-Ahead Log) é o log de transações do PostgreSQL. Com archive_mode = on e archive_command configurados, cada segmento de WAL é copiado para um local seguro. "
    "Para recuperar: restaura-se o backup de base e reaplica-se o WAL até recovery_target_time.\n\n"
    "| SGBD | Ponto no tempo |\n|---|---|\n| SQL Server | full + backups de log (recovery model FULL) |\n| PostgreSQL | pg_basebackup + arquivamento de WAL |\n"
    "| MySQL | backup completo + binary log (mysqlbinlog --stop-datetime) |\n\n"
    "pg_dump é lógico e restaura só até o instante do dump. VACUUM é manutenção.",
    dificuldade=3,
)
