from base import AF3, AF3b, Topico

T = Topico("Modelagem de dados", 2, "bd-modelagem",
           "Modelagem de dados: modelo entidade-relacionamento (MER) e modelo relacional, normalização, chaves e relacionamentos")

T.mc(
    "No modelo entidade-relacionamento, DEPARTAMENTO e FUNCIONÁRIO têm um relacionamento 1:N: um departamento possui vários funcionários, e cada funcionário pertence a um único departamento. Ao mapear esse relacionamento para o modelo relacional, deve-se",
    "incluir na tabela FUNCIONARIO uma chave estrangeira que referencia a chave primária de DEPARTAMENTO.",
    ["incluir na tabela DEPARTAMENTO uma chave estrangeira que referencia a chave primária de FUNCIONARIO.",
     "criar obrigatoriamente uma terceira tabela com as chaves primárias das duas entidades.",
     "fundir as duas entidades em uma única tabela, eliminando o relacionamento.",
     "incluir chaves estrangeiras cruzadas nas duas tabelas, uma apontando para a outra."],
    "Relacionamento 1:N para tabelas: letra {G} — a chave estrangeira vai no lado N.\n\n"
    "Cada funcionário tem UM departamento, então cabe uma coluna depto_id em FUNCIONARIO. O contrário não cabe: um departamento tem VÁRIOS funcionários, e uma coluna não guarda vários valores (violaria a 1FN).\n\n"
    "| Cardinalidade | Mapeamento |\n|---|---|\n"
    "| 1:1 | FK em qualquer um dos lados, com UNIQUE (de preferência no lado de participação total) |\n"
    "| 1:N | FK no lado N |\n"
    "| N:N | tabela associativa com duas FKs |\n\n"
    "Atalho: a FK vai para quem tem 'só um' do outro.",
    dificuldade=1,
)
T.mc(
    "Em um sistema acadêmico, um ALUNO pode se matricular em várias DISCIPLINAS, e cada DISCIPLINA pode ter vários ALUNOS; para cada matrícula registra-se a nota final. No modelo relacional, esse relacionamento é implementado com",
    "uma tabela associativa MATRICULA, com chaves estrangeiras para ALUNO e DISCIPLINA e o atributo nota.",
    ["uma chave estrangeira para DISCIPLINA na tabela ALUNO, com o atributo nota em ALUNO.",
     "uma chave estrangeira para ALUNO na tabela DISCIPLINA, com o atributo nota em DISCIPLINA.",
     "uma coluna multivalorada em ALUNO contendo os códigos de todas as disciplinas.",
     "duas chaves estrangeiras cruzadas, sem tabela adicional, e a nota guardada em ambas as tabelas."],
    "Relacionamento N:N com atributo próprio (nota): letra {G}.\n\n"
    "N:N sempre vira uma TABELA ASSOCIATIVA:\n\n"
    "MATRICULA (aluno_id FK, disciplina_id FK, nota) — chave primária composta (aluno_id, disciplina_id).\n\n"
    "A nota é atributo do RELACIONAMENTO, não de uma das entidades: ela depende do par aluno + disciplina. Por isso mora na tabela associativa.\n\n"
    "FK em ALUNO só permitiria uma disciplina por aluno (vira 1:N). Coluna multivalorada viola a 1FN.",
    dificuldade=1,
)
T.mc(
    "Um atributo multivalorado do modelo entidade-relacionamento, como os vários telefones de um CLIENTE, deve ser mapeado para o modelo relacional por meio de",
    "uma nova tabela contendo o atributo e uma chave estrangeira para a tabela CLIENTE.",
    ["uma única coluna em CLIENTE com os telefones separados por vírgula.",
     "várias colunas fixas em CLIENTE, como telefone1, telefone2 e telefone3, como solução normalizada.",
     "um atributo derivado calculado a partir dos demais atributos de CLIENTE.",
     "uma chave primária composta em CLIENTE formada pelo identificador e pelo telefone."],
    "Atributo multivalorado no relacional: letra {G} — tabela própria.\n\n"
    "TELEFONE_CLIENTE (cliente_id FK, telefone) — PK composta (cliente_id, telefone).\n\n"
    "Lista separada por vírgula viola a 1FN (valor não atômico) e impede buscar 'quem tem o telefone X' com eficiência.\n\n"
    "telefone1, telefone2, telefone3 é grupo repetitivo: limita a três e desperdiça espaço — também é o que a 1FN proíbe.\n\n"
    "PK composta em CLIENTE com o telefone repetiria nome e endereço do cliente a cada telefone.\n\n"
    "Símbolo no MER (Chen): elipse DUPLA.",
)
T.mc(
    "Uma tabela está na primeira forma normal (1FN) quando",
    "todos os seus atributos contêm apenas valores atômicos, sem grupos repetitivos nem atributos multivalorados.",
    ["todo atributo não chave depende da chave primária inteira, e não de parte dela.",
     "não existem dependências transitivas entre atributos não chave.",
     "todo determinante é uma chave candidata.",
     "não há chaves estrangeiras referenciando outras tabelas."],
    "Definição de 1FN: letra {G} — valores atômicos.\n\n"
    "| Forma normal | Exige (além da anterior) |\n|---|---|\n"
    "| 1FN | valores atômicos; sem grupos repetitivos e sem atributos multivalorados |\n"
    "| 2FN | sem dependência PARCIAL: atributo não chave depende da chave INTEIRA |\n"
    "| 3FN | sem dependência TRANSITIVA: não chave não depende de outro não chave |\n"
    "| FNBC (Boyce-Codd) | todo determinante é chave candidata |\n\n"
    "As erradas são as definições das formas seguintes — a questão testa se você sabe a ORDEM.\n\n"
    "Frase para decorar (2FN e 3FN): o atributo depende 'da chave, da chave inteira e de nada além da chave'.",
    dificuldade=1,
)
T.mc(
    "Considere a tabela ITEM_PEDIDO (num_pedido, cod_produto, quantidade, descricao_produto), cuja chave primária é composta por num_pedido e cod_produto. Sabe-se que descricao_produto depende apenas de cod_produto. Essa tabela",
    "está na 1FN, mas não na 2FN, pois há dependência parcial da chave primária.",
    ["está na 2FN, mas não na 3FN, pois há dependência transitiva.",
     "não está na 1FN, pois possui chave primária composta.",
     "está na 3FN, pois todos os atributos dependem de algum atributo da chave.",
     "está na FNBC, pois cod_produto faz parte da chave primária."],
    "ITEM_PEDIDO com descricao_produto dependendo só de cod_produto: letra {G}.\n\n"
    "A chave é (num_pedido, cod_produto). descricao_produto depende só de PARTE dela (cod_produto) → dependência PARCIAL → viola a 2FN.\n\n"
    "Consequência prática: a descrição do produto se repete em cada pedido em que ele aparece; mudar o nome do produto exige atualizar milhares de linhas (anomalia de atualização).\n\n"
    "Solução: PRODUTO (cod_produto, descricao_produto) e ITEM_PEDIDO (num_pedido, cod_produto, quantidade).\n\n"
    "Atalho: dependência parcial só existe quando a chave é COMPOSTA. Chave simples → a tabela na 1FN já está automaticamente na 2FN.",
    dificuldade=2,
)
T.mc(
    "A tabela FUNCIONARIO (matricula, nome, cod_depto, nome_depto) tem matricula como chave primária. Sabe-se que cod_depto determina nome_depto. Para levar essa tabela à terceira forma normal, deve-se",
    "separar DEPARTAMENTO (cod_depto, nome_depto) e manter cod_depto em FUNCIONARIO como chave estrangeira.",
    ["transformar (matricula, cod_depto) em chave primária composta.",
     "remover cod_depto de FUNCIONARIO e manter nome_depto.",
     "criar uma tabela para cada departamento, com seus funcionários.",
     "manter a tabela como está, pois ela já atende à 3FN por ter chave primária simples."],
    "FUNCIONARIO com cod_depto → nome_depto: letra {G}.\n\n"
    "matricula → cod_depto → nome_depto: nome_depto depende da chave através de outro atributo não chave. É dependência TRANSITIVA, o que viola a 3FN.\n\n"
    "Correção: o determinante (cod_depto) vira chave de uma tabela nova com os atributos que ele determina, e fica em FUNCIONARIO como FK.\n\n"
    "A última alternativa confunde 3FN com 2FN: chave simples garante 2FN, não 3FN.\n\n"
    "Atalho: na 3FN, procure um atributo não chave que 'manda' em outro. Ele vira tabela.",
)
T.mc(
    "Em um banco de dados normalizado, a equipe decidiu armazenar na tabela PEDIDO o valor total do pedido, embora ele possa ser calculado somando os itens, para acelerar relatórios muito consultados. Essa decisão é um exemplo de",
    "desnormalização, que introduz redundância controlada para melhorar o desempenho de leitura.",
    ["normalização na forma normal de Boyce-Codd.", "integridade referencial em cascata.",
     "independência física de dados.", "especialização total e disjunta."],
    "Guardar um valor calculável para acelerar leitura: letra {G}, desnormalização.\n\n"
    "Normalização elimina redundância e protege contra anomalias; desnormalização reintroduz redundância DE PROPÓSITO, em troca de desempenho.\n\n"
    "O custo: manter o total coerente quando um item muda — normalmente com trigger ou na própria transação da aplicação. Sem isso, o total diverge da soma dos itens.\n\n"
    "Onde é comum: data warehouse (modelo dimensional é desnormalizado), colunas de total, contadores, tabelas de resumo.",
)
T.mc(
    "Sobre chaves estrangeiras no modelo relacional, é INCORRETO afirmar que",
    "o valor de uma chave estrangeira deve ser único na tabela em que ela está definida.",
    ["a chave estrangeira referencia a chave primária (ou uma chave candidata) de outra tabela ou da mesma tabela.",
     "uma chave estrangeira pode aceitar valor nulo, quando a participação no relacionamento é opcional.",
     "a restrição de integridade referencial impede inserir um valor de chave estrangeira que não exista na tabela referenciada.",
     "os domínios da chave estrangeira e da chave referenciada devem ser compatíveis."],
    "Qual é a INCORRETA sobre chave estrangeira? Letra {G}.\n\n"
    "Chave estrangeira REPETE: vários funcionários com o mesmo depto_id. Unicidade é propriedade de chave primária e de UNIQUE, não de FK. "
    "(FK com UNIQUE só aparece de propósito, para implementar um 1:1.)\n\n"
    "As demais estão certas:\n\n"
    "— pode referenciar a própria tabela (autorrelacionamento: gerente_id em FUNCIONARIO);\n\n"
    "— pode ser NULL (funcionário ainda sem departamento);\n\n"
    "— integridade referencial barra FK 'órfã';\n\n"
    "— os tipos têm de ser compatíveis (INT com INT).",
    formato="negativa",
)
T.mc(
    "A tabela ITEM_PEDIDO possui uma chave estrangeira para PEDIDO definida com a cláusula ON DELETE CASCADE. Ao executar a exclusão de um pedido que possui itens,",
    "o pedido é excluído e todos os seus itens também são excluídos automaticamente.",
    ["a exclusão é rejeitada, pois existem itens referenciando o pedido.",
     "o pedido é excluído, e a chave estrangeira dos itens passa a conter NULL.",
     "os itens são excluídos, mas o pedido permanece na tabela.",
     "o pedido é excluído, e os itens permanecem referenciando um pedido inexistente."],
    "ON DELETE CASCADE: letra {G} — apagar o pai apaga os filhos.\n\n"
    "| Ação referencial | Ao apagar o pai |\n|---|---|\n"
    "| NO ACTION / RESTRICT (padrão) | REJEITA a exclusão se houver filhos |\n"
    "| CASCADE | apaga os filhos junto |\n"
    "| SET NULL | mantém os filhos, com a FK = NULL |\n"
    "| SET DEFAULT | mantém os filhos, com a FK = valor padrão |\n\n"
    "As alternativas erradas descrevem NO ACTION, SET NULL e duas situações impossíveis — itens órfãos são exatamente o que a integridade referencial proíbe.\n\n"
    "Quando usar CASCADE: item que não existe sem o pai (itens do pedido). Quando NÃO usar: cliente → pedidos; apagar um cliente não deveria sumir com o histórico de vendas.",
)
T.mc(
    "Na tabela FUNCIONARIO, a coluna depto_id é chave estrangeira para DEPARTAMENTO, definida com ON DELETE SET NULL. Ao excluir um departamento que possui funcionários,",
    "os funcionários permanecem cadastrados, com depto_id igual a NULL.",
    ["os funcionários do departamento são excluídos.",
     "a exclusão do departamento é rejeitada.",
     "o depto_id dos funcionários é alterado para o código do departamento padrão definido em DEFAULT.",
     "os funcionários são transferidos automaticamente para o departamento de menor código."],
    "ON DELETE SET NULL: letra {G}.\n\n"
    "O departamento some, os funcionários ficam, agora 'sem departamento'. Para isso funcionar, a coluna depto_id precisa ACEITAR NULL — se for NOT NULL, a definição é inválida ou a exclusão falha.\n\n"
    "Valor padrão é SET DEFAULT; exclusão em cadeia é CASCADE; rejeitar é NO ACTION/RESTRICT. A última alternativa não existe em SQL.",
)
T.mc(
    "Em vez de usar o CPF como chave primária de CLIENTE, o projetista criou uma coluna id numérica, gerada automaticamente pelo SGBD (IDENTITY no SQL Server, AUTO_INCREMENT no MySQL), e manteve o CPF com restrição UNIQUE. A coluna id é um exemplo de",
    "chave substituta (surrogate key).",
    ["chave natural.", "chave estrangeira.", "superchave não mínima.", "atributo derivado."],
    "id gerado pelo SGBD, sem significado de negócio: letra {G}, chave substituta (surrogate).\n\n"
    "| Tipo | Exemplo | Vantagem | Risco |\n|---|---|---|---|\n"
    "| natural | CPF, ISBN, placa | já existe, tem significado | pode mudar, ter formato variável, ser dado pessoal |\n"
    "| substituta | id IDENTITY / AUTO_INCREMENT | estável, pequena, numérica, boa para índice | não impede duplicata de negócio sozinha |\n\n"
    "Por isso o projetista manteve o CPF como UNIQUE: o id identifica a linha, e o UNIQUE impede dois clientes com o mesmo CPF. O CPF continua sendo chave CANDIDATA (alternativa).",
)
T.mc(
    "No modelo entidade-relacionamento, DEPENDENTE só existe vinculado a um FUNCIONÁRIO e é identificado pelo nome do dependente combinado com a matrícula do funcionário. DEPENDENTE é classificado como",
    "entidade fraca, cujo identificador combina sua chave parcial com a chave da entidade proprietária.",
    ["entidade forte, pois possui o atributo nome.",
     "entidade associativa, pois resulta de um relacionamento N:N.",
     "atributo multivalorado de FUNCIONÁRIO.",
     "especialização de FUNCIONÁRIO."],
    "DEPENDENTE identificado por nome + matrícula do funcionário: letra {G}, entidade fraca.\n\n"
    "Entidade fraca não tem chave própria suficiente; usa uma CHAVE PARCIAL (o nome do dependente, sublinhado tracejado) somada à chave da entidade PROPRIETÁRIA. "
    "O relacionamento que a liga ao dono é o relacionamento IDENTIFICADOR, e a participação dela é total.\n\n"
    "| Símbolo (Chen) | Significado |\n|---|---|\n| retângulo duplo | entidade fraca |\n| losango duplo | relacionamento identificador |\n\n"
    "No relacional: DEPENDENTE (matricula FK, nome_dependente, parentesco), PK (matricula, nome_dependente), com ON DELETE CASCADE.",
    dificuldade=1,
)
T.mc(
    "Na tabela FUNCIONARIO (matricula, nome, matricula_gerente), a coluna matricula_gerente é chave estrangeira que referencia a própria tabela FUNCIONARIO. Essa estrutura implementa um",
    "autorrelacionamento (relacionamento recursivo).",
    ["relacionamento ternário.", "relacionamento N:N obrigatoriamente.",
     "atributo derivado.", "especialização sobreposta."],
    "FK que aponta para a própria tabela: letra {G}, autorrelacionamento.\n\n"
    "A mesma entidade participa duas vezes, em PAPÉIS diferentes: gerente e subordinado. É um 1:N recursivo (um gerente, vários subordinados).\n\n"
    "Para listar cada funcionário com o nome do gerente, usa-se SELF JOIN:\n\n"
    "SELECT f.nome, g.nome AS gerente\nFROM FUNCIONARIO f\nLEFT JOIN FUNCIONARIO g ON g.matricula = f.matricula_gerente;\n\n"
    "LEFT JOIN porque o diretor não tem gerente (matricula_gerente NULL) e, com INNER, sumiria da lista.",
)
T.fixa(
    "Sobre a cardinalidade mínima (participação) nos relacionamentos do modelo entidade-relacionamento, analise as afirmativas.",
    AF3, "E",
    "Todas as três estão certas — letra E.\n\n"
    "I — cardinalidade mínima 0 = participação OPCIONAL (parcial): pode existir cliente sem pedido.\n\n"
    "II — mínima 1 = participação OBRIGATÓRIA (total): todo pedido tem de ter um cliente. Na notação de Chen, linha dupla.\n\n"
    "III — no relacional, a participação obrigatória do lado da FK se traduz em FK NOT NULL; a opcional, em FK que aceita NULL.\n\n"
    "Pé de galinha (crow's foot): círculo = zero, traço = um, pé de galinha = muitos. '|o' perto da entidade lê-se 'zero ou um'.",
    afirmacoes=[
        "Cardinalidade mínima igual a zero indica participação opcional da entidade no relacionamento.",
        "Cardinalidade mínima igual a um indica participação obrigatória (total) da entidade no relacionamento.",
        "No modelo relacional, a participação obrigatória do lado que recebe a chave estrangeira pode ser implementada declarando essa chave estrangeira como NOT NULL.",
    ],
    formato="afirmacoes",
)
T.mc(
    "No diagrama entidade-relacionamento, a idade de um cliente pode ser calculada a partir de sua data de nascimento. Nesse caso, idade é um atributo",
    "derivado, que normalmente não é armazenado, mas calculado quando necessário.",
    ["multivalorado, que deve ser mapeado para uma tabela própria.",
     "composto, que deve ser decomposto em colunas simples.",
     "identificador, que deve compor a chave primária.",
     "chave estrangeira, que referencia a data de nascimento."],
    "Idade calculada a partir da data de nascimento: letra {G}, atributo derivado.\n\n"
    "| Tipo de atributo | Exemplo | No relacional |\n|---|---|---|\n"
    "| simples | nome | uma coluna |\n| composto | endereço (rua, número, CEP) | uma coluna por parte |\n"
    "| multivalorado | telefones | tabela própria |\n| derivado | idade, total do pedido | em geral calculado (view, coluna computada), não gravado |\n\n"
    "Gravar a idade é erro clássico: ela fica errada no dia seguinte ao aniversário. Grava-se a data de nascimento e calcula-se a idade.\n\n"
    "Símbolo (Chen): elipse TRACEJADA.",
    dificuldade=1,
)
T.mc(
    "A entidade VEÍCULO foi especializada em CARRO e CAMINHÃO, com especialização total e disjunta. Uma forma válida de mapear essa hierarquia para o modelo relacional é",
    "criar uma única tabela VEICULO com os atributos de todas as subclasses e uma coluna discriminadora de tipo.",
    ["criar apenas a tabela VEICULO, descartando os atributos específicos das subclasses.",
     "criar uma tabela CARRO_CAMINHAO com chave primária composta pelas duas subclasses.",
     "transformar CARRO e CAMINHÃO em atributos multivalorados de VEICULO.",
     "criar uma tabela associativa N:N entre CARRO e CAMINHÃO."],
    "Mapeamento de especialização: letra {G} (tabela única com discriminador).\n\n"
    "Há três estratégias válidas:\n\n"
    "| Estratégia | Como | Bom quando |\n|---|---|---|\n"
    "| tabela única | VEICULO com todas as colunas + tipo | poucas colunas específicas; aceita NULLs |\n"
    "| tabela por subclasse | VEICULO + CARRO + CAMINHAO, cada filha com PK = FK para VEICULO | muitas colunas específicas |\n"
    "| só as subclasses | CARRO e CAMINHAO com os atributos herdados repetidos | especialização TOTAL e DISJUNTA, sem consulta ao 'veículo genérico' |\n\n"
    "A tabela única funciona bem com disjunta: a coluna tipo guarda UM valor. Descartar atributos perde informação; as demais alternativas não representam herança.",
    dificuldade=3,
)
T.mc(
    "Uma tabela possui chave primária composta (A, B) e a dependência funcional C → B, em que C é um atributo não chave. Nessa situação, a tabela",
    "pode estar na 3FN, mas não está na forma normal de Boyce-Codd, pois C é determinante sem ser chave candidata.",
    ["está na FNBC, pois toda tabela na 3FN está na FNBC.",
     "não está na 1FN, pois um atributo não chave determina parte da chave.",
     "está na 4FN, pois não há dependências multivaloradas.",
     "não admite normalização, por ter chave composta."],
    "C → B, com C não sendo chave candidata: letra {G}.\n\n"
    "FNBC exige que TODO determinante seja chave candidata. C determina B e não é chave → viola a FNBC.\n\n"
    "Pode ainda estar na 3FN porque a definição da 3FN tem uma exceção: aceita X → Y quando Y faz parte de alguma chave candidata (B é parte da chave). É exatamente essa brecha que a FNBC fecha.\n\n"
    "Toda tabela em FNBC está em 3FN; o contrário não vale — a primeira errada inverte isso.\n\n"
    "Atalho: FNBC = 3FN sem exceção. Achou um determinante que não é chave → fora da FNBC.",
    dificuldade=3,
)
T.mc(
    "Em uma tabela não normalizada, alterar o endereço de um fornecedor exigiu atualizar dezenas de linhas, e uma delas ficou com o endereço antigo, gerando informação contraditória. Esse problema é conhecido como anomalia de",
    "atualização (modificação).",
    ["inserção.", "exclusão.", "junção.", "concorrência."],
    "Mesmo dado repetido em várias linhas e uma delas ficou desatualizada: letra {G}, anomalia de atualização.\n\n"
    "| Anomalia | O que acontece |\n|---|---|\n"
    "| inserção | não dá para cadastrar um fato sem outro (fornecedor sem produto) |\n"
    "| exclusão | apagar uma linha leva junto informação que se queria manter (o último produto leva o fornecedor) |\n"
    "| atualização | o dado repetido precisa mudar em várias linhas; esquecer uma gera inconsistência |\n\n"
    "As três nascem da redundância, e é para eliminá-las que se normaliza.",
    dificuldade=1,
)
T.mc(
    "No relacionamento 1:1 entre FUNCIONARIO e CRACHA, em que todo crachá pertence a exatamente um funcionário e nem todo funcionário possui crachá, a implementação relacional mais adequada é",
    "colocar em CRACHA uma chave estrangeira para FUNCIONARIO, declarada NOT NULL e UNIQUE.",
    ["colocar em FUNCIONARIO uma chave estrangeira para CRACHA, declarada NOT NULL.",
     "criar uma tabela associativa com chave primária composta e sem restrição de unicidade.",
     "colocar em CRACHA uma chave estrangeira para FUNCIONARIO, sem restrição UNIQUE.",
     "unir as duas tabelas, tornando os atributos de crachá obrigatórios para todo funcionário."],
    "1:1 com participação total de CRACHA e parcial de FUNCIONARIO: letra {G}.\n\n"
    "A FK vai no lado de participação TOTAL (o crachá), porque lá ela nunca fica vazia:\n\n"
    "— NOT NULL: todo crachá tem dono;\n\n"
    "— UNIQUE: o mesmo funcionário não pode ter dois crachás — é o UNIQUE que transforma 1:N em 1:1.\n\n"
    "FK em FUNCIONARIO teria de aceitar NULL (nem todo funcionário tem crachá); declará-la NOT NULL obrigaria todos a ter. Sem UNIQUE, vira 1:N. "
    "Unir as tabelas obrigaria crachá para todos, contrariando o enunciado.",
    dificuldade=3,
)
T.fixa(
    "Analise as afirmativas a seguir sobre chaves no modelo relacional.",
    AF3b, "C",
    "Quais estão certas? Letra C: I e III.\n\n"
    "I — certa. Superchave é qualquer conjunto de atributos que identifica a linha; chave candidata é a superchave MÍNIMA.\n\n"
    "II — errada. Uma tabela tem UMA chave primária (que pode ser composta de vários atributos). As outras candidatas são chaves alternativas — implementadas com UNIQUE.\n\n"
    "III — certa. A integridade de ENTIDADE proíbe NULL em qualquer atributo da chave primária: se a chave pudesse ser nula, a linha não seria identificável.",
    afirmacoes=[
        "Uma chave candidata é uma superchave mínima, isto é, da qual nenhum atributo pode ser retirado sem perder a capacidade de identificar unicamente cada linha.",
        "Uma tabela pode possuir várias chaves primárias, desde que cada uma seja formada por um único atributo.",
        "A restrição de integridade de entidade determina que nenhum atributo que compõe a chave primária pode assumir valor nulo.",
    ],
    formato="afirmacoes",
)
