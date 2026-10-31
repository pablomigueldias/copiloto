"""Matemática e raciocínio lógico — inéditas. Contas conferidas por script antes de escrever (ver `verificar`)."""
from fractions import Fraction as F
from itertools import permutations
from math import gcd, lcm

from base import Sequencia, Topico

SEQ_MAT = Sequencia()
_kw = dict(materia="Matemática Avança SP", cargo="Matemática e Raciocínio Lógico (nível superior)",
           sequencia=SEQ_MAT)

LOG = Topico("Lógica de argumentação", 1, "mat-logica-argumentacao",
             "Estruturas lógicas, lógicas de argumentação, diagramas lógicos", **_kw)
REL = Topico("Relações arbitrárias e dedução", 2, "mat-relacoes-arbitrarias",
             "Estrutura lógica das relações arbitrárias entre pessoas, lugares, coisas, eventos fictícios", **_kw)
SIT = Topico("Situações-problema", 3, "mat-situacoes-problema", "Resolução de situações-problema", **_kw)
MED = Topico("Média aritmética", 4, "mat-media", "Média aritmética simples e ponderada", **_kw)
NUM = Topico("Números e divisibilidade", 5, "mat-numeros-divisibilidade",
             "Mínimo múltiplo comum e máximo divisor comum", **_kw)
EQ = Topico("Equações do 1º grau", 6, "mat-equacoes", "Sistema de equações do 1º grau", **_kw)
R3 = Topico("Regra de três", 7, "mat-regra-de-tres", "Regra de três simples e composta", **_kw)
GEO = Topico("Geometria", 8, "mat-geometria",
             "Noções de geometria: forma, perímetro, área, volume, ângulo, teorema de Pitágoras", **_kw)
TAB = Topico("Grandezas, tabelas e gráficos", 9, "mat-tabelas-graficos", "Relação entre grandezas: tabelas e gráficos", **_kw)
JUR = Topico("Juro simples", 10, "mat-juro-simples", "Juro simples", **_kw)

TOPICOS = [LOG, REL, SIT, MED, NUM, EQ, R3, GEO, TAB, JUR]


def checa(cond):
    def f():
        assert cond
    return f


# ── Lógica de argumentação / diagramas ──
LOG.mc(
    "Considere verdadeiras as proposições:\n\nI. Todo analista é concursado.\nII. Nenhum concursado é terceirizado.\n\nA partir delas, conclui-se necessariamente que",
    "nenhum analista é terceirizado.",
    ["algum terceirizado é analista.", "todo concursado é analista.",
     "algum analista não é concursado.", "todo terceirizado é concursado."],
    "Todo analista é concursado; nenhum concursado é terceirizado. Letra {G}.\n\n"
    "Diagrama: o círculo dos ANALISTAS fica inteiro DENTRO do círculo dos CONCURSADOS; o círculo dos TERCEIRIZADOS fica inteiro FORA do dos concursados. "
    "Logo, analistas e terceirizados não se encostam: nenhum analista é terceirizado.\n\n"
    "| Alternativa | Por que cai |\n|---|---|\n"
    "| algum terceirizado é analista | contradiz o diagrama |\n"
    "| todo concursado é analista | inverte a premissa I: o círculo de dentro não cobre o de fora |\n"
    "| algum analista não é concursado | nega a premissa I |\n"
    "| todo terceirizado é concursado | contradiz a premissa II |\n\n"
    "Atalho: 'todo A é B' = A dentro de B. 'Nenhum B é C' = B e C separados. O que está dentro de B herda a separação.",
    dificuldade=1,
)
LOG.mc(
    "Em um setor com 50 funcionários, 30 sabem programar em SQL, 25 sabem programar em Python e 10 sabem as duas linguagens. O número de funcionários desse setor que não sabem nenhuma das duas linguagens é",
    "5.", ["10.", "0.", "15.", "45."],
    "50 funcionários, 30 SQL, 25 Python, 10 ambos. Letra {G}: 5.\n\n"
    "Quem sabe PELO MENOS uma: 30 + 25 − 10 = 45. O 10 é subtraído porque quem sabe as duas foi contado duas vezes — uma no SQL, outra no Python.\n\n"
    "Nenhuma: 50 − 45 = 5.\n\n"
    "Pelo diagrama: só SQL = 30 − 10 = 20; só Python = 25 − 10 = 15; ambos = 10; total dentro dos círculos = 45.\n\n"
    "Pegadinhas: 0 é de quem soma 30 + 25 = 55 e acha que todo mundo sabe alguma; 45 é a resposta de 'pelo menos uma'.\n\n"
    "Fórmula: n(A ∪ B) = n(A) + n(B) − n(A ∩ B).",
    formato="calculo", dificuldade=1,
    verificar=checa(50 - (30 + 25 - 10) == 5),
)

# ── Relações arbitrárias ──
_sols = []
for cg in permutations(["DBA", "desenvolvedor", "gerente"]):
    for cd in permutations(["Santos", "Campinas", "Sorocaba"]):
        c, d = dict(zip(["Ana", "Bruno", "Carla"], cg)), dict(zip(["Ana", "Bruno", "Carla"], cd))
        if any(c[p] == "DBA" and d[p] != "Santos" for p in c):
            continue
        if d["Bruno"] == "Santos" or c["Bruno"] == "gerente" or d["Carla"] != "Sorocaba" or c["Ana"] == "desenvolvedor":
            continue
        _sols.append((c, d))

REL.mc(
    "Ana, Bruno e Carla trabalham em uma empresa de TI, um como DBA, outro como desenvolvedor e outro como gerente, e moram em cidades diferentes: Santos, Campinas e Sorocaba. Sabe-se que:\n\n"
    "• o DBA mora em Santos;\n• Bruno não mora em Santos e não é gerente;\n• Carla mora em Sorocaba;\n• Ana não é desenvolvedora.\n\nCom base nessas informações, é correto afirmar que",
    "Bruno é desenvolvedor e mora em Campinas.",
    ["Ana é gerente e mora em Santos.", "Carla é DBA e mora em Sorocaba.",
     "Bruno é DBA e mora em Campinas.", "Ana é DBA e mora em Campinas."],
    "Quem é quem? Letra {G}.\n\n"
    "Ordem de dedução — comece pela pista que amarra duas categorias:\n\n"
    "1. O DBA mora em Santos. Carla mora em Sorocaba → Carla NÃO é DBA. Bruno não mora em Santos → Bruno NÃO é DBA. Logo, ANA é a DBA e mora em SANTOS.\n\n"
    "2. Bruno não é gerente e não é DBA → Bruno é DESENVOLVEDOR. Sobra GERENTE para Carla.\n\n"
    "3. Santos é de Ana e Sorocaba de Carla → Bruno mora em CAMPINAS.\n\n"
    "| Pessoa | Cargo | Cidade |\n|---|---|---|\n| Ana | DBA | Santos |\n| Bruno | desenvolvedor | Campinas |\n| Carla | gerente | Sorocaba |\n\n"
    "A pista 'Ana não é desenvolvedora' acabou sobrando — é comum a banca dar uma informação a mais, só para confirmar.\n\n"
    "Atalho: monte a tabela pessoa × atributo e marque X nas impossibilidades. Quando uma linha fica com uma só opção, ela se propaga.",
    dificuldade=2,
    verificar=checa(len(_sols) == 1 and _sols[0][0]["Bruno"] == "desenvolvedor" and _sols[0][1]["Bruno"] == "Campinas"),
)
_filas = []
for o in permutations("ABCDE"):
    pos = {x: i + 1 for i, x in enumerate(o)}
    if pos["A"] == 1 and pos["E"] == 5 and pos["D"] - pos["B"] == 1 and abs(pos["C"] - pos["A"]) != 1:
        _filas.append("".join(o))
REL.mc(
    "Cinco servidores — Alfredo, Beatriz, Cláudio, Denise e Eduardo — formaram uma fila para o atendimento. Sabe-se que:\n\n"
    "• Alfredo é o primeiro da fila;\n• Eduardo é o último;\n• Beatriz está imediatamente à frente de Denise;\n• Cláudio não está ao lado de Alfredo.\n\nQuem ocupa a terceira posição da fila?",
    "Denise.", ["Beatriz.", "Cláudio.", "Alfredo.", "Eduardo."],
    "Quem é o terceiro da fila? Letra {G}: Denise.\n\n"
    "Posições fixas: Alfredo na 1ª e Eduardo na 5ª. Sobram 2ª, 3ª e 4ª para Beatriz, Cláudio e Denise.\n\n"
    "Cláudio não pode ficar ao lado de Alfredo → Cláudio não é o 2º.\n\n"
    "Beatriz e Denise são consecutivas, nessa ordem. Testando:\n\n"
    "| 2ª | 3ª | 4ª | Válido? |\n|---|---|---|---|\n| Beatriz | Denise | Cláudio | sim |\n| Cláudio | Beatriz | Denise | não: Cláudio ao lado de Alfredo |\n\n"
    "Fila: Alfredo, Beatriz, Denise, Cláudio, Eduardo.\n\n"
    "Atalho: fixe primeiro quem tem posição absoluta (primeiro, último), depois encaixe os blocos ('imediatamente à frente' = bloco de dois).",
    dificuldade=2,
    verificar=checa(_filas == ["ABDCE"]),
)

# ── Situações-problema ──
SIT.mc(
    "Um servidor gastou 1/3 do seu salário com aluguel e 1/4 do que restou com alimentação, sobrando-lhe R$ 3.000,00. O salário desse servidor é de",
    "R$ 6.000,00.", ["R$ 4.800,00.", "R$ 5.142,86.", "R$ 7.200,00.", "R$ 9.000,00."],
    "Salário S; aluguel 1/3; alimentação 1/4 do RESTO; sobram R$ 3.000. Letra {G}.\n\n"
    "Depois do aluguel resta 2/3 de S. A alimentação leva 1/4 DESSE resto, então sobram 3/4 dele:\n\n"
    "S × 2/3 × 3/4 = S/2 = 3.000 → S = 6.000.\n\n"
    "Conferindo: aluguel 2.000; resto 4.000; alimentação 1.000; sobra 3.000. ✓\n\n"
    "A pegadinha é ler '1/4 do que restou' como '1/4 do salário': aí sobraria 1 − 1/3 − 1/4 = 5/12 de S, e S = 3.000 × 12/5 = 7.200.\n\n"
    "Atalho: 'do restante' → multiplique as frações do que SOBRA a cada etapa.",
    formato="calculo", dificuldade=2,
    verificar=checa(F(3000) / (F(2, 3) * F(3, 4)) == 6000),
)
SIT.mc(
    "Em uma equipe, 40% dos integrantes são mulheres. Se forem contratadas mais 10 mulheres, e ninguém sair, as mulheres passarão a representar 50% da equipe. O número inicial de integrantes da equipe é",
    "50.", ["40.", "20.", "60.", "100."],
    "40% mulheres; entram 10 mulheres; vira 50%. Letra {G}: 50.\n\n"
    "Com N integrantes no início: mulheres = 0,4N. Depois: mulheres = 0,4N + 10 e total = N + 10.\n\n"
    "0,4N + 10 = 0,5 (N + 10)\n0,4N + 10 = 0,5N + 5\n5 = 0,1N → N = 50.\n\n"
    "Conferindo: 20 mulheres em 50; depois 30 em 60 = 50%. ✓\n\n"
    "O erro comum é esquecer que o TOTAL também cresce em 10: 0,4N + 10 = 0,5N daria N = 100.",
    formato="calculo", dificuldade=2,
    verificar=checa(F(4, 10) * 50 + 10 == F(1, 2) * 60),
)

# ── Média ──
MED.mc(
    "Em um processo seletivo, o candidato obteve nota 6 na prova de Português (peso 2), 8 na de Matemática (peso 3) e 5 na de Conhecimentos Específicos (peso 5). Sua média ponderada final foi",
    "6,1.", ["6,3.", "6,0.", "6,5.", "7,0."],
    "Notas 6, 8 e 5 com pesos 2, 3 e 5. Letra {G}: 6,1.\n\n"
    "Média ponderada = soma de (nota × peso) ÷ soma dos pesos.\n\n"
    "| Prova | Nota | Peso | Nota × peso |\n|---|---|---|---|\n| Português | 6 | 2 | 12 |\n| Matemática | 8 | 3 | 24 |\n| Específicos | 5 | 5 | 25 |\n| Total | | 10 | 61 |\n\n"
    "61 ÷ 10 = 6,1.\n\n"
    "6,3 é a média SIMPLES (19 ÷ 3), a armadilha de quem ignora os pesos. A nota mais baixa tem o maior peso, por isso a ponderada fica abaixo da simples.",
    formato="calculo", dificuldade=1,
    verificar=checa(F(6 * 2 + 8 * 3 + 5 * 5, 10) == F(61, 10)),
)
MED.mc(
    "Para ser aprovado em um curso, o aluno precisa de média ponderada mínima 7,0 em três avaliações, com pesos 2, 3 e 5, respectivamente. Ele tirou 7,0 na primeira e 6,0 na segunda. A nota mínima que precisa obter na terceira avaliação é",
    "7,6.", ["8,0.", "7,0.", "7,8.", "8,2."],
    "Pesos 2, 3 e 5; notas 7 e 6; média mínima 7. Letra {G}: 7,6.\n\n"
    "(7 × 2 + 6 × 3 + 5x) ÷ 10 = 7\n14 + 18 + 5x = 70\n5x = 38 → x = 7,6.\n\n"
    "Raciocínio rápido: a soma ponderada precisa chegar a 7 × 10 = 70 pontos. Ele já tem 32; faltam 38, divididos pelo peso 5.\n\n"
    "8,0 é de quem acha que precisa compensar a nota 6 com média simples ((7 + 6 + x) ÷ 3 = 7).",
    formato="calculo", dificuldade=2,
    verificar=checa(F(14 + 18 + 5 * F(38, 5), 10) == 7),
)

# ── MMC e MDC ──
NUM.mc(
    "Em um servidor, três rotinas automáticas são executadas a cada 6 horas, 8 horas e 12 horas, respectivamente. Se as três foram executadas juntas à 0h de uma segunda-feira, elas voltarão a ser executadas juntas pela primeira vez",
    "à 0h de terça-feira.", ["às 12h de segunda-feira.", "às 8h de terça-feira.", "à 0h de quarta-feira.", "às 18h de segunda-feira."],
    "Rotinas a cada 6, 8 e 12 h, juntas à 0h de segunda. Letra {G}.\n\n"
    "Coincidem a cada MMC(6, 8, 12):\n\n6 = 2 × 3\n8 = 2³\n12 = 2² × 3\n\nMMC = 2³ × 3 = 24 horas.\n\n"
    "0h de segunda + 24 h = 0h de terça.\n\n"
    "Atalho: 'voltam a coincidir', 'ao mesmo tempo de novo' → MMC. 'Dividir em partes iguais, as maiores possíveis' → MDC.",
    formato="calculo", dificuldade=1,
    verificar=checa(lcm(6, 8, 12) == 24),
)
NUM.mc(
    "Um almoxarifado tem 72 resmas de papel A4 e 120 resmas de papel ofício. Elas serão distribuídas em lotes com a mesma quantidade de resmas, a maior possível, sem misturar os tipos de papel em um mesmo lote e sem sobras. O número total de lotes formados será",
    "8.", ["24.", "6.", "12.", "16."],
    "72 e 120 resmas, lotes iguais, os maiores possíveis. Letra {G}: 8 lotes.\n\n"
    "Tamanho do lote = MDC(72, 120):\n\n72 = 2³ × 3²\n120 = 2³ × 3 × 5\n\nMDC = 2³ × 3 = 24 resmas por lote.\n\n"
    "Número de lotes: 72 ÷ 24 = 3 de A4 e 120 ÷ 24 = 5 de ofício → 3 + 5 = 8.\n\n"
    "24 é a pegadinha: é o TAMANHO de cada lote, não a quantidade de lotes. Leia o que a pergunta pede.",
    formato="calculo", dificuldade=2,
    verificar=checa(gcd(72, 120) == 24 and 72 // 24 + 120 // 24 == 8),
)

# ── Sistemas de equações ──
EQ.mc(
    "Em uma papelaria, 3 canetas e 2 cadernos custam R$ 31,00, e 2 canetas e 3 cadernos custam R$ 34,00. O preço de uma caneta somado ao de um caderno é",
    "R$ 13,00.", ["R$ 12,00.", "R$ 14,00.", "R$ 15,00.", "R$ 65,00."],
    "3c + 2k = 31 e 2c + 3k = 34. Letra {G}: R$ 13,00.\n\n"
    "Atalho de prova: SOME as duas equações → 5c + 5k = 65 → c + k = 13. Nem é preciso achar cada preço.\n\n"
    "Resolvendo por completo (para conferir): subtraindo, a segunda menos a primeira → −c + k = 3 → k = c + 3. Em c + k = 13: 2c + 3 = 13 → c = 5 e k = 8.\n\n"
    "Conferindo: 3 × 5 + 2 × 8 = 31 ✓; 2 × 5 + 3 × 8 = 34 ✓.\n\n"
    "65 é a soma bruta, antes de dividir por 5. Quando a pergunta pede uma COMBINAÇÃO das incógnitas, tente somar ou subtrair as equações antes de resolver.",
    formato="calculo", dificuldade=2,
    verificar=checa(3 * 5 + 2 * 8 == 31 and 2 * 5 + 3 * 8 == 34),
)
EQ.mc(
    "No estacionamento de um órgão público há apenas carros e motos, totalizando 30 veículos e 100 rodas. O número de motos é",
    "10.", ["20.", "15.", "25.", "5."],
    "30 veículos, 100 rodas, carros (4) e motos (2). Letra {G}: 10 motos.\n\n"
    "c + m = 30\n4c + 2m = 100\n\nMultiplicando a primeira por 2: 2c + 2m = 60. Subtraindo da segunda: 2c = 40 → c = 20 carros e m = 10 motos.\n\n"
    "Raciocínio sem álgebra: se fossem 30 motos, seriam 60 rodas. Faltam 40 rodas; cada troca de moto por carro acrescenta 2 → 20 trocas → 20 carros e 10 motos.\n\n"
    "20 é o número de CARROS — a pegadinha de quem resolve certo e responde a incógnita errada.",
    formato="calculo", dificuldade=1,
    verificar=checa(20 + 10 == 30 and 4 * 20 + 2 * 10 == 100),
)

# ── Regra de três ──
R3.mc(
    "Seis analistas, trabalhando 6 horas por dia, migram 480 tabelas de um banco de dados em 8 dias. Mantido o mesmo ritmo individual, quantos dias serão necessários para que 4 analistas, trabalhando 8 horas por dia, migrem 640 tabelas?",
    "12.", ["8.", "9.", "16.", "6."],
    "Regra de três composta. Letra {G}: 12 dias.\n\n"
    "| Analistas | Horas/dia | Tabelas | Dias |\n|---|---|---|---|\n| 6 | 6 | 480 | 8 |\n| 4 | 8 | 640 | x |\n\n"
    "Compare cada grandeza com DIAS:\n\n"
    "— mais tabelas → mais dias: DIRETA (640/480);\n\n— menos analistas → mais dias: INVERSA (6/4);\n\n— mais horas por dia → menos dias: INVERSA (6/8).\n\n"
    "x = 8 × (640/480) × (6/4) × (6/8) = 8 × 4/3 × 3/2 × 3/4 = 12.\n\n"
    "Conferindo pelo trabalho total: 6 × 6 × 8 = 288 analista-horas para 480 tabelas = 0,6 h por tabela. 640 × 0,6 = 384 analista-horas ÷ (4 × 8) = 12 dias. ✓",
    formato="calculo", dificuldade=2,
    verificar=checa(F(8) * F(640, 480) * F(6, 4) * F(6, 8) == 12),
)
R3.mc(
    "Dez impressoras iguais imprimem 2.000 páginas em 4 horas. Seis dessas impressoras, no mesmo ritmo, imprimirão 1.500 páginas em",
    "5 horas.", ["4 horas.", "3 horas e 36 minutos.", "6 horas.", "1 hora e 48 minutos."],
    "10 impressoras, 2.000 páginas, 4 h → 6 impressoras, 1.500 páginas. Letra {G}: 5 horas.\n\n"
    "— menos páginas → menos tempo: DIRETA (1.500/2.000);\n\n— menos impressoras → mais tempo: INVERSA (10/6).\n\n"
    "x = 4 × (1.500/2.000) × (10/6) = 4 × 3/4 × 5/3 = 5 h.\n\n"
    "Pelo ritmo: cada impressora faz 2.000 ÷ 10 ÷ 4 = 50 páginas por hora. Seis fazem 300 por hora; 1.500 ÷ 300 = 5 h. ✓\n\n"
    "1h48 é de quem trata 'impressoras' como direta (4 × 3/4 × 6/10 = 1,8 h). Pergunte sempre: AUMENTANDO esta grandeza, o tempo aumenta ou diminui?",
    formato="calculo", dificuldade=2,
    verificar=checa(F(4) * F(1500, 2000) * F(10, 6) == 5),
)

# ── Geometria ──
GEO.mc(
    "Uma escada de 13 m de comprimento está apoiada em uma parede vertical, com o pé a 5 m da base da parede, em um piso horizontal. A altura, na parede, do ponto em que a escada se apoia é",
    "12 m.", ["8 m.", "18 m.", "√194 m.", "10 m."],
    "Escada 13 m, pé a 5 m da parede. Letra {G}: 12 m.\n\n"
    "A parede, o chão e a escada formam um triângulo RETÂNGULO, e a escada é a hipotenusa (o lado oposto ao ângulo reto).\n\n"
    "13² = 5² + h²\n169 = 25 + h²\nh² = 144 → h = 12.\n\n"
    "√194 vem de somar os quadrados (13² + 5²), tratando a escada como cateto.\n\n"
    "Triplas pitagóricas que mais caem: 3-4-5 (e múltiplos 6-8-10, 9-12-15), 5-12-13, 8-15-17. Reconhecê-las poupa a conta.",
    formato="calculo", dificuldade=1,
    verificar=checa(13 ** 2 - 5 ** 2 == 12 ** 2),
)
GEO.mc(
    "Uma caixa-d'água tem a forma de um paralelepípedo reto retângulo, com medidas internas de 2 m de comprimento, 1,5 m de largura e 1 m de altura. Sua capacidade, em litros, é",
    "3.000 litros.", ["300 litros.", "30.000 litros.", "4.500 litros.", "3 litros."],
    "Paralelepípedo 2 m × 1,5 m × 1 m, em litros. Letra {G}: 3.000 L.\n\n"
    "Volume = comprimento × largura × altura = 2 × 1,5 × 1 = 3 m³.\n\n"
    "Conversão: 1 m³ = 1.000 litros (1 dm³ = 1 L, e 1 m³ = 1.000 dm³). Logo, 3 m³ = 3.000 L.\n\n"
    "| Medida | Equivale a |\n|---|---|\n| 1 m³ | 1.000 L |\n| 1 dm³ | 1 L |\n| 1 cm³ | 1 mL |\n\n"
    "As alternativas erradas são a mesma conta com a conversão errada por fatores de 10 — é exatamente o que a banca testa.",
    formato="calculo", dificuldade=1,
    verificar=checa(2 * F(3, 2) * 1 * 1000 == 3000),
)

# ── Tabelas e gráficos ──
_CHAMADOS = ("A tabela mostra o número de chamados técnicos abertos em um setor de TI, por mês.\n\n"
             "| Mês | Chamados |\n|---|---|\n| Janeiro | 80 |\n| Fevereiro | 100 |\n| Março | 90 |\n| Abril | 120 |\n\n")
TAB.mc(
    _CHAMADOS + "Considerando os meses consecutivos, o maior aumento percentual no número de chamados ocorreu",
    "de março para abril, com aumento de aproximadamente 33%.",
    ["de janeiro para fevereiro, com aumento de 25%.", "de janeiro para fevereiro, com aumento de 20%.",
     "de março para abril, com aumento de 30%.", "de fevereiro para março, com aumento de 10%."],
    "Maior aumento PERCENTUAL entre meses consecutivos. Letra {G}.\n\n"
    "Variação percentual = (novo − antigo) ÷ ANTIGO × 100.\n\n"
    "| Período | Variação absoluta | Percentual |\n|---|---|---|\n| jan → fev | +20 | 20 ÷ 80 = 25% |\n| fev → mar | −10 | −10% (queda) |\n| mar → abr | +30 | 30 ÷ 90 ≈ 33,3% |\n\n"
    "Armadilhas:\n\n— dividir pelo valor NOVO: 20 ÷ 100 = 20% e 30 ÷ 120 = 25%;\n\n— 30% é de quem divide 30 por 100;\n\n— fev → mar foi QUEDA, não aumento.",
    formato="calculo", dificuldade=2,
    verificar=checa(F(30, 90) > F(20, 80) and round(30 / 90 * 100) == 33),
)
TAB.mc(
    _CHAMADOS + "A média mensal de chamados no período apresentado foi de",
    "97,5 chamados.", ["95 chamados.", "100 chamados.", "105 chamados.", "390 chamados."],
    "Média de 80, 100, 90 e 120. Letra {G}: 97,5.\n\n"
    "Soma: 80 + 100 + 90 + 120 = 390. Média: 390 ÷ 4 = 97,5.\n\n"
    "390 é o total do período, não a média. 100 é a mediana arredondada — a média é que se pede.\n\n"
    "Conferência rápida: a média tem de ficar entre o menor (80) e o maior (120) valor. Alternativa fora desse intervalo já cai.",
    formato="calculo", dificuldade=1,
    verificar=checa(F(80 + 100 + 90 + 120, 4) == F(195, 2)),
)

# ── Juro simples ──
JUR.mc(
    "Um capital aplicado a juro simples, à taxa de 2% ao mês, rendeu R$ 360,00 de juros em 6 meses. O valor do capital aplicado foi de",
    "R$ 3.000,00.", ["R$ 18.000,00.", "R$ 30,00.", "R$ 2.160,00.", "R$ 3.360,00."],
    "Juro de R$ 360 em 6 meses a 2% a.m. Letra {G}: R$ 3.000.\n\n"
    "J = C × i × t, com a taxa em decimal e a mesma unidade de tempo da taxa:\n\n"
    "360 = C × 0,02 × 6 = C × 0,12 → C = 360 ÷ 0,12 = 3.000.\n\n"
    "Conferindo: 2% de 3.000 = 60 por mês; × 6 = 360. ✓\n\n"
    "Armadilhas: 18.000 esquece o tempo (360 ÷ 0,02); 30 usa a taxa como 2 em vez de 0,02 (360 ÷ 12); 2.160 multiplica em vez de dividir (360 × 6); 3.360 é o montante (capital + juros), não o capital.\n\n"
    "Juro simples rende sempre o MESMO valor por período (aqui, R$ 60 por mês); por isso o crescimento é linear.",
    formato="calculo", dificuldade=1,
    verificar=checa(F(360) / (F(2, 100) * 6) == 3000),
)
JUR.mc(
    "Um servidor aplicou R$ 2.500,00 a juro simples, à taxa de 1,5% ao mês, por 8 meses. Ao final do período, o montante resgatado foi de",
    "R$ 2.800,00.", ["R$ 300,00.", "R$ 2.537,50.", "R$ 2.875,00.", "R$ 5.500,00."],
    "Montante de R$ 2.500 a 1,5% a.m. por 8 meses. Letra {G}: R$ 2.800.\n\n"
    "J = C × i × t = 2.500 × 0,015 × 8 = 300.\n\nM = C + J = 2.500 + 300 = 2.800.\n\n"
    "Armadilhas: 300 é só o JURO (a pergunta pede montante); 2.537,50 aplica a taxa uma vez só (um mês); 2.875 usa 15% em vez de 1,5%, mas só por um período.\n\n"
    "Atalho: em juro simples, 1,5% × 8 meses = 12% sobre o capital. 12% de 2.500 = 300.",
    formato="calculo", dificuldade=1,
    verificar=checa(F(2500) * (1 + F(15, 1000) * 8) == 2800),
)
