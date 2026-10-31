"""O catálogo de assuntos do simulado — a prova do Avança SP, matéria a matéria.

Existe por causa do diagnóstico. "Errei 4 de banco de dados" não diz o que
estudar; "errei 2 de trigger e 1 de crase" diz. O tópico do acervo ("SQL e
programação de banco", "Classes de palavras") é largo demais para isso, então
cada questão do estoque ganha um `assunto` daqui — vocabulário **fechado**: o
importador recusa assunto que não está nesta lista, porque um rótulo digitado de
dois jeitos partiria o mesmo erro em dois e o reforço sairia pela metade.

A estrutura tem três níveis, e cada um serve a uma decisão:

- **matéria** — o quadro do edital (CRECI-SP 01/2026, PAS – Analista de TI –
  Banco de Dados, cap. 11): PT 10, MAT 10, Inglês técnico 10, Específicos 30.
- **grupo** — onde mora o peso. Em PT e MAT é o assunto como a Avança SP o
  cobrou nas 14 provas (`docs/avanca-sp/avanca-sp-peso-questoes.md`); em BD é a
  linha do edital, com o precedente da banca somado a um piso, porque o edital
  promete backup e administração e a banca quase nunca cobrou — "estude pelo
  edital, não pelo histórico". Inglês não tem precedente nenhum (zero em 680
  questões da banca), e o peso é o do programa do edital.
- **assunto** — o que aparece no diagnóstico e o que recebe as 5 de reforço.

Só entra aqui assunto que está no Anexo II do edital. Em 07/10/2026 saíram três
que o acervo tinha e o edital não cobra — data warehouse/OLAP/data mining,
ameaças (malware, spoofing) e fonologia —; as questões deles ficam no acervo,
sem `assunto`, e por isso fora do simulado.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Grupo:
    nome: str
    peso: float
    assuntos: tuple[str, ...]


@dataclass(frozen=True)
class Materia:
    chave: str
    nome: str
    questoes: int
    grupos: tuple[Grupo, ...]


PT = Materia("pt", "Língua Portuguesa", 10, (
    Grupo("Classes de palavras", 33.5, (
        "Substantivo: classificação e flexão",
        "Adjetivo e locução adjetiva",
        "Advérbio: classificação e circunstâncias",
        "Pronomes: classificação",
        "Valores do QUE",
        "Morfologia: classificar palavras no contexto",
        "Verbo: tempos e modos",
        "Verbo: conjugação de irregulares",
        "Vozes verbais",
    )),
    Grupo("Interpretação de texto", 24.5, (
        "Interpretação: ideia central, tese e finalidade",
        "Interpretação: informação explícita no texto",
        "Interpretação: inferência e sentido de trecho",
        "Discurso direto, indireto e indireto livre",
    )),
    Grupo("Sentido das palavras e figuras", 9.7, (
        "Sinônimos, antônimos e reescrita com mesmo sentido",
        "Sentido próprio e figurado (denotação e conotação)",
        "Figuras de linguagem",
        "Ambiguidade",
    )),
    Grupo("Ortografia e acentuação", 9.0, (
        "Ortografia: grafia das palavras",
        "Hífen e prefixos",
        "Parônimos e homônimos (mal/mau, onde/aonde, porquês)",
        "Acentuação gráfica e sílaba tônica",
    )),
    Grupo("Regência e crase", 7.1, (
        "Crase",
        "Regência verbal e transitividade",
        "Regência nominal",
    )),
    Grupo("Análise sintática", 7.1, (
        "Sujeito: tipos e oração sem sujeito",
        "Termos da oração: objetos, complemento nominal e adjuntos",
    )),
    Grupo("Pontuação", 3.9, (
        "Vírgula",
        "Dois-pontos, travessão e outros sinais",
    )),
    Grupo("Concordância", 3.2, (
        "Concordância verbal",
        "Concordância nominal",
    )),
    Grupo("Colocação pronominal", 3.2, (
        "Colocação pronominal (próclise, ênclise e mesóclise)",
    )),
    Grupo("Coesão", 3.0, (
        "Referência e retomada (anáfora e catáfora)",
        "Conectivos: valor semântico",
        "Mecanismos de coesão (sequenciação, lexical, elipse)",
    )),
    # 1,3% no histórico, mas as duas ocorrências são da prova mais nova (Rio
    # Claro 2026) e o edital lista o assunto: peso de "em ascensão".
    Grupo("Redação oficial", 4.0, (
        "Redação oficial: atributos (clareza, concisão, impessoalidade)",
        "Redação oficial: pronomes de tratamento e fecho",
        "Redação oficial: tipos de documento e e-mail",
    )),
))

MAT = Materia("mat", "Matemática e Raciocínio Lógico", 10, (
    Grupo("Geometria", 23.1, (
        "Área e perímetro",
        "Volume e capacidade de sólidos",
        "Teorema de Pitágoras",
        "Ângulos e triângulos",
        "Semelhança de triângulos",
        "Sólidos geométricos e visualização espacial",
    )),
    Grupo("Porcentagem", 19.2, (
        "Porcentagem: cálculo básico",
        "Variação percentual (aumento e redução)",
        "Aumentos e descontos sucessivos",
    )),
    Grupo("Média aritmética", 13.8, (
        "Média aritmética simples",
        "Média ponderada",
        "Média: incluir ou retirar valores",
    )),
    Grupo("Razão, proporção e regra de três", 11.5, (
        "Razão: cálculo e interpretação",
        "Razão com soma ou diferença conhecida",
        "Divisão em partes proporcionais",
        "Grandezas diretamente proporcionais",
        "Regra de três simples direta",
        "Regra de três simples inversa",
        "Regra de três composta",
    )),
    Grupo("Sequências", 8.5, (
        "Sequência numérica: padrão e termo",
        "Sequência figural e ciclos (resto da divisão)",
    )),
    Grupo("Relações arbitrárias", 8.5, (
        "Associação de atributos (quem é quem)",
        "Ordenação e posições",
        "Codificação e correspondência de letras",
    )),
    Grupo("Tabelas e gráficos", 6.9, (
        "Leitura de tabelas e gráficos",
    )),
    Grupo("Juro simples", 3.1, (
        "Juro simples: juros, montante, taxa e prazo",
    )),
    Grupo("Lógica e argumentação", 3.1, (
        "Quantificadores e diagramas (todo, algum, nenhum)",
        "Diagramas de Venn: contagem",
        "Validade de argumentos",
        "Negação de proposições (De Morgan)",
        "Negação de quantificadores",
        "Equivalências lógicas",
        "Condicional e dedução",
        "Tabela-verdade e valor lógico",
    )),
    Grupo("MMC, MDC e divisibilidade", 2.0, (
        "MMC: eventos que se repetem",
        "MDC: dividir em grupos iguais",
        "Divisores e divisibilidade",
    )),
    # Os quatro abaixo estão no edital e quase não caíram: o piso de 2 garante
    # que apareçam de tempos em tempos sem roubar vaga de geometria.
    Grupo("Equações e sistemas do 1º grau", 2.0, (
        "Equação do 1º grau: problemas",
        "Sistema de equações do 1º grau",
    )),
    Grupo("Operações com números reais", 2.0, (
        "Frações: operações e problemas",
        "Operações com inteiros e expressões numéricas",
    )),
    Grupo("Sistemas de medidas", 2.0, (
        "Conversão de comprimento e área",
        "Conversão de volume e capacidade (litro e m³)",
    )),
    Grupo("Situações-problema", 2.0, (
        "Problemas de contagem e tempo",
        "Problemas de custo e tarifa",
    )),
))

EN = Materia("en", "Inglês Técnico", 10, (
    Grupo("Compreensão de texto técnico", 40, (
        "Ideia principal e finalidade do texto",
        "Informação específica (according to the text)",
        "Inferência em texto técnico",
    )),
    Grupo("Vocabulário técnico", 25, (
        "Vocabulário em contexto (sinônimo)",
        "Glossário de TI: hardware, redes e cloud",
        "Glossário de TI: banco de dados e programação",
        "Glossário de TI: segurança da informação",
        "Falsos cognatos",
    )),
    Grupo("Gramática aplicada à leitura", 20, (
        "Referência pronominal",
        "Conectivos e marcadores de coesão",
        "Formação de palavras (prefixos e sufixos)",
        "Verbos modais e voz passiva em documentação",
    )),
    Grupo("Comandos, mensagens de erro e logs", 10, (
        "Mensagens de erro e logs",
        "Comandos de sistema e instruções de instalação",
    )),
    Grupo("Normas, RFCs e redação técnica", 5, (
        "RFCs e palavras-chave MUST, SHOULD e MAY",
        "Normas ISO e NIST",
        "Redação técnica: e-mail e relatório",
    )),
))

# Peso = precedente nas 14 provas (a tabela "Cruzamento com o seu edital") + 3
# de piso por linha do edital.
BD = Materia("bd", "Conhecimentos Específicos — Banco de Dados", 30, (
    Grupo("Conceitos, arquitetura e tipos de SGBD", 18, (
        "Características da abordagem de banco de dados",
        "Arquitetura de três esquemas e independência de dados",
        "Componentes internos do SGBD",
        "Modelos de dados: hierárquico, em rede, relacional e OO",
        "Modelo relacional: terminologia (grau, cardinalidade, tupla)",
        "Transações e propriedades ACID",
        "Níveis de isolamento e anomalias de concorrência",
        "SGBDs: MySQL, PostgreSQL, SQL Server e Access",
        "SQL Server: bancos de sistema e edições",
        "Papéis: DBA e usuários do banco",
        "NoSQL: tipos, CAP e BASE",
    )),
    Grupo("Segurança de dados", 16, (
        "Conceitos básicos: CID, ativo e incidente",
        "Controle de acesso: autenticação, autorização e RBAC",
        "SQL injection e consultas parametrizadas",
        "Criptografia: simétrica, assimétrica, hash e TDE",
        "Mascaramento de dados e Row-Level Security",
        "Auditoria de banco de dados",
        "LGPD: dados pessoais, sensíveis e anonimização",
        "Hardening e boas práticas de proteção",
    )),
    Grupo("SQL e programação de banco", 15, (
        "Grupos de comandos SQL: DDL, DML, DCL, DQL e DTL",
        "Filtros e ordenação: WHERE, LIKE, BETWEEN, ORDER BY e TOP/LIMIT",
        "Agregação: COUNT, SUM, AVG, GROUP BY e HAVING",
        "JOINs: INNER, LEFT, RIGHT e FULL",
        "Subconsultas e operadores de conjunto (IN, EXISTS, UNION)",
        "NULL em comparações e agregações",
        "DML: INSERT, UPDATE e DELETE",
        "DELETE, TRUNCATE e DROP",
        "Views (visões)",
        "Stored procedures",
        "Triggers",
        "Funções definidas pelo usuário",
    )),
    Grupo("Modelagem de dados", 14, (
        "MER: entidade forte, fraca e associativa",
        "MER: atributos (chave, multivalorado, composto, derivado)",
        "MER: relacionamentos e cardinalidade",
        "Especialização e generalização",
        "Modelos conceitual, lógico e físico",
        "Mapeamento do MER para o modelo relacional",
        "Chaves: primária, candidata, estrangeira e substituta",
        "Normalização e dependência funcional",
    )),
    Grupo("Tuning e desempenho", 9, (
        "Índices: tipos, seletividade e índice composto",
        "Índice clusterizado, não clusterizado e de cobertura",
        "Plano de execução (EXPLAIN) e estatísticas",
        "Otimização de consultas: sargabilidade e SELECT *",
        "Monitoramento: slow query log e Query Store",
        "Particionamento, desnormalização e views materializadas",
    )),
    Grupo("Administração de banco de dados", 6, (
        "Instalação e configuração do SGBD",
        "Usuários, logins e papéis (roles)",
        "GRANT, REVOKE e DENY",
        "Restrições de integridade (PK, UNIQUE, CHECK, DEFAULT)",
        "Integridade referencial (ON DELETE e ON UPDATE)",
        "Controle de transações e deadlock",
        "Manutenção do banco (DBCC e verificação de integridade)",
    )),
    Grupo("Backup e recuperação", 6, (
        "Tipos de backup: completo, incremental e diferencial",
        "Modelos de recuperação, log e restauração point-in-time",
        "Backup lógico × físico e quente × frio",
        "Política de backup (3-2-1 e teste de restauração)",
        "Replicação × backup e alta disponibilidade",
        "RPO, RTO, sites e continuidade de negócios",
    )),
))

# A ordem do caderno do simulado. A prova real abre com Português e fecha com
# os específicos; o Pablo pediu em 07/10/2026 o contrário — específicos
# primeiro, depois Matemática e Português, com a cabeça descansada para o que
# vale metade da nota. Inglês, que ele não citou, fecha.
MATERIAS: tuple[Materia, ...] = (BD, MAT, PT, EN)
POR_CHAVE = {m.chave: m for m in MATERIAS}

# assunto → (matéria, grupo). Construído uma vez; é a única forma de saber de
# que matéria uma questão é, já que o tópico do acervo não diz (a questão de
# segurança da informação mora em "Conhecimentos específicos de TI" e conta como
# Banco de Dados).
ONDE: dict[str, tuple[Materia, Grupo]] = {}
for _m in MATERIAS:
    for _g in _m.grupos:
        for _a in _g.assuntos:
            assert _a not in ONDE, f"assunto repetido no catálogo: {_a}"
            ONDE[_a] = (_m, _g)

TOTAL_QUESTOES = sum(m.questoes for m in MATERIAS)  # 60, como no edital


def valido(assunto: str) -> bool:
    return assunto in ONDE
