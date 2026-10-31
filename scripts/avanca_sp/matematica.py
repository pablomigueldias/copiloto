"""Matemática e Raciocínio Lógico — o bloco comum das provas não-TI de 07/10/2026.

Toda conta passa por um `assert` aqui antes de virar explicação: se a conta
não fecha, o script nem roda.
"""
from fractions import Fraction as F
from itertools import permutations
from math import gcd, isqrt, lcm, pi, sqrt

from bloco_comum import Q

IMG = "avanca-sp/"

# ── Embu-Guaçu 2022 ──────────────────────────────────────────────────────

assert F(14, 28) == F(1, 2)
Q("embu", 11, "razao-proporcao", "Razão: cálculo e interpretação", "A",
  "Uma sorveteria vendeu, em um dia, 36 picolés, 28 sorvetes e 14 geladinhos. A razão entre o número de geladinhos vendidos pelo número de sorvetes vendidos, é:",
  ["0,5.", "1.", "2.", "5.", "7,5."],
  "Razão de A PARA B = A ÷ B, na ordem em que o enunciado fala: letra {G}.\n\n"
  "geladinhos ÷ sorvetes = 14 ÷ 28 = 0,5.\n\n"
  "Os 36 picolés são distração: não entram na conta.\n\n"
  "Pegadinha: inverter a ordem dá 28 ÷ 14 = 2, que também está nas alternativas.", dificuldade=1)

assert 80 + 80 * 1.25 == 180
Q("embu", 12, "porcentagem-progressoes", "Porcentagem: cálculo básico", "C",
  "Sônia fez 80 meias de crochê, em um mês. No mês seguinte, ela fez 25 % a mais de meias. Daí, a quantidade total de meias que ela fez, nesses dois meses, é:",
  ["100.", "120.", "180.", "200.", "210."],
  "Total dos DOIS meses: letra {G}.\n\n"
  "| Mês | Meias |\n|---|---|\n| 1º | 80 |\n| 2º | 80 × 1,25 = 100 |\n| total | 180 |\n\n"
  "A alternativa 100 é só o segundo mês — a resposta de quem para no meio. Leia de novo o que a pergunta pede.", dificuldade=1)

Q("embu", 13, "geometria", "Ângulos e triângulos", "C",
  "A porta do quarto de Ugo ficou aberta formando um ângulo de 35° com a parede. Sobre esse ângulo é correto afirmar:",
  ["é um ângulo raso.", "é um ângulo raro.", "é um ângulo agudo.", "é um ângulo obtuso.", "é um ângulo obeso."],
  "35° é menor que 90°: agudo. Letra {G}.\n\n"
  "| Ângulo | Medida |\n|---|---|\n| agudo | entre 0° e 90° |\n| reto | 90° |\n| obtuso | entre 90° e 180° |\n| raso | 180° |\n\n"
  "'Raro' e 'obeso' não existem como classificação de ângulo.", dificuldade=1)

assert 8 ** 3 * 1000 == 512_000
Q("embu", 14, "geometria", "Volume e capacidade de sólidos", "E",
  "Um tanque aquático cúbico foi comprado para colocar tartarugas. Sabe-se que o mesmo possui 800 cm de lado, então seu volume é:",
  ["5,12 litros.", "51,2 litros.", "512 litros.", "5 120 litros.", "512 000 litros."],
  "Converta antes de elevar ao cubo: letra {G}.\n\n"
  "800 cm = 8 m → V = 8³ = 512 m³ → 512 × 1.000 L = 512.000 L.\n\n"
  "Atalho: 1 m³ = 1.000 L e 1 dm³ = 1 L. Por dm: 800 cm = 80 dm → 80³ = 512.000 dm³ = 512.000 L.\n\n"
  "A pegadinha é o 512 sem o fator 1.000: a alternativa 512 litros é a resposta de quem esqueceu que 1 m³ tem mil litros.", dificuldade=2)

assert abs(4 * 185.6 - 742.4) < 1e-9
Q("embu", 15, "geometria", "Área e perímetro", "A",
  "Um tapete foi feito com formato quadrado. Sabe-se que seu lado mede 185,6 m, então seu perímetro é de:",
  ["742,4 m.", "864 m.", "921,8 m.", "967,36 m.", "995,3 m."],
  "Perímetro do quadrado = 4 × lado: letra {G}.\n\n4 × 185,6 = 742,4 m.\n\n"
  "Perímetro é contorno (soma dos lados, em m); área é superfície (lado², em m²). Não confundir.", dificuldade=1)

# ── Itupeva 2024 ─────────────────────────────────────────────────────────

parte = F(6_300_000, 5 + 7 + 9)
assert parte * (9 - 5) == 1_200_000
Q("itupeva", 11, "razao-proporcao", "Divisão em partes proporcionais", "B",
  "Três irmãos ganharam uma herança de 6,30 milhões de reais e dividirão em partes diretamente proporcionais a 5, 7 e 9. Qual a diferença dos valores recebidos entre o irmão que mais recebeu e o que menos recebeu?",
  ["R$ 1,5 milhão.", "R$ 1,2 milhão.", "R$ 2,7 milhões.", "R$ 2,1 milhões.", "R$ 1,7 milhão."],
  "Divisão proporcional: letra {G}.\n\n"
  "1. Some as partes: 5 + 7 + 9 = 21.\n2. Valor de uma parte: 6,3 milhões ÷ 21 = 0,3 milhão.\n\n"
  "| Irmão | Partes | Recebe |\n|---|---|---|\n| menor | 5 | 1,5 mi |\n| meio | 7 | 2,1 mi |\n| maior | 9 | 2,7 mi |\n\n"
  "Diferença: 2,7 − 1,5 = 1,2 milhão. Atalho: (9 − 5) partes × 0,3 = 1,2.\n\n"
  "As erradas 1,5, 2,1 e 2,7 são as próprias partes — a banca põe o caminho no lugar da chegada.", dificuldade=2)

litros = F(810, 360) * 8
assert litros == 18 and litros / F(9, 10) == 20
Q("itupeva", 12, "regra-de-tres", "Regra de três simples direta", "D",
  "Um pintor precisa pintar uma parede com área total de 810 metros quadrados e deseja saber quantos litros de tinta deve comprar. Cada 8 litros de tinta rendem o suficiente para cobrir 360 metros quadrados de área. No entanto, durante o trabalho, 10% da tinta comprada é desperdiçada, ou seja, apenas 90% da tinta adquirida é realmente usada na pintura. Com essas condições, quantos litros de tinta o pintor precisa comprar para garantir que o serviço seja concluído?",
  ["21,3.", "19,5.", "18,0.", "20,0.", "20,4."],
  "Regra de três e depois o desperdício: letra {G}.\n\n"
  "1. Tinta que vai para a parede: 8 L → 360 m², x → 810 m². x = 8 × 810 ÷ 360 = 18 L.\n"
  "2. Só 90% do que se compra é aproveitado: compra × 0,9 = 18 → compra = 20 L.\n\n"
  "Pegadinha: somar 10% (18 × 1,1 = 19,8) não é o mesmo que dividir por 0,9. O desperdício é 10% do COMPRADO, não do usado.", dificuldade=2)

assert 82_800 / 18 == 4600
Q("itupeva", 13, "sistemas-de-medidas", "Conversão de comprimento e área", "B",
  "O prédio Burj Khalifa, que fica em Dubai, Emirados Árabes, é atualmente o maior prédio do mundo, com 0,828 km de altura. Suponha que existe uma escada que leva do térreo até o topo do prédio. Cada degrau dessa escada tem altura de 18 cm. Quantos degraus há ao todo?",
  ["460.", "4.600.", "46.000.", "4.600.000.", "46.000.000."],
  "Mesma unidade antes de dividir: letra {G}.\n\n"
  "0,828 km = 828 m = 82.800 cm. 82.800 ÷ 18 = 4.600 degraus.\n\n"
  "| km | hm | dam | m | dm | cm | mm |\n|---|---|---|---|---|---|---|\n\n"
  "Cada passo para a direita multiplica por 10: de km para cm são 5 passos, × 100.000.\n\n"
  "As alternativas diferem só por potência de 10 — é questão de conversão, não de conta.", dificuldade=1)

Q("itupeva", 14, "logica-argumentacao", "Quantificadores e diagramas (todo, algum, nenhum)", "C",
  "Considere verdadeiras as seguintes afirmativas:\n\n• Há músicos que também são pintores;\n• Todo escultor também é músico;\n• Há pintores que também são escultores.\n\nCom base nas alternativas, podemos afirmar que:",
  ["Todo músico também é escultor.", "Todo músico é escultor e pintor.",
   "Todos os pintores que são escultores também são músicos.",
   "Todos os músicos que são escultores também são pintores.",
   "Todos os pintores que são músicos também são escultores."],
  "Diagrama: o círculo dos escultores fica INTEIRO dentro do dos músicos. Letra {G}.\n\n"
  "Quem é pintor E escultor está dentro de escultores, e escultores está dentro de músicos — então também é músico. Isso vale sempre.\n\n"
  "| Alternativa | Por que não é obrigatória |\n|---|---|\n| todo músico é escultor | 'todo escultor é músico' não se inverte |\n"
  "| todo músico é escultor e pintor | idem, e pior |\n| músicos escultores são pintores | só ALGUNS pintores são escultores |\n| pintores músicos são escultores | 'algum' não garante 'todos' |\n\n"
  "Regra: 'Todo A é B' não permite concluir 'Todo B é A'. 'Algum' nunca vira 'todo'.", dificuldade=2)

assert 100 / 20 == 5 and (60 + 40 + 100) / 20 == 10
Q("itupeva", 15, "operacoes-numeros-reais", "Operações com inteiros e expressões numéricas", "C",
  "Uma cafeteria precisa entregar encomendas de 60 caixas de biscoitos do Tipo A, 40 caixas do Tipo B e 100 caixas do Tipo C usando uma van com capacidade máxima de 10 caixas por viagem. Em todas as viagens, a van deve levar sempre x caixas do Tipo A, y caixas do Tipo B e z caixas do Tipo C. A van dará 20 viagens ao todo. Nesse caso, qual deve ser o valor de z?",
  ["2.", "3.", "5.", "4.", "6."],
  "Viagens iguais: cada tipo se divide pelas 20 viagens. Letra {G}.\n\n"
  "z = 100 ÷ 20 = 5 (e x = 3, y = 2).\n\n"
  "Conferência: 3 + 2 + 5 = 10 por viagem, exatamente a capacidade da van.", dificuldade=1)

trigo, aveia = 750, 250
assert trigo * F(100, 250) - aveia == 50
Q("itupeva", 16, "razao-proporcao", "Grandezas diretamente proporcionais", "D",
  "Em uma receita de bolo, pede-se para colocar 100 g de farinha de aveia para cada 250 g de farinha de trigo. Uma confeiteira comprou 1 kg de uma mistura que continha 75% de farinha de trigo e 25% de farinha de aveia. Quanto de farinha de aveia ela deve adicionar à mistura para atender à especificação da receita?",
  ["20 g.", "25 g.", "40 g.", "50 g.", "100 g."],
  "O trigo não muda; ajusta-se a aveia a ele. Letra {G}.\n\n"
  "Mistura: 750 g de trigo e 250 g de aveia.\n\n"
  "Receita: 100 g de aveia / 250 g de trigo → para 750 g de trigo, 750 × 100 ÷ 250 = 300 g de aveia.\n\n"
  "Já há 250 g: faltam 300 − 250 = 50 g.\n\n"
  "Atalho: a proporção aveia:trigo da receita é 2:5; a da mistura é 1:3. Fixe o que você não pode tirar (trigo) e calcule o que falta.", dificuldade=2)

x = [v for v in range(51) if 50 * v + 40 * (50 - v) == 42 * 50]
assert x == [10]
Q("itupeva", 17, "media-aritmetica", "Média ponderada", "A",
  "Em jogo de pega-varetas, cada cor de vareta tem uma pontuação. Varetas verdes valem 50 pontos e varetas vermelhas valem 40 pontos. Suponha que em uma caixa há varetas verdes e vermelhas misturadas, num total de 50 varetas. A média aritmética simples dos pontos das varetas é 42 pontos. Quantas varetas verdes há na caixa?",
  ["10.", "50.", "40.", "30.", "25."],
  "Total de pontos = média × quantidade: letra {G}.\n\n"
  "Total: 42 × 50 = 2.100 pontos. Com v verdes: 50v + 40(50 − v) = 2.100 → 10v + 2.000 = 2.100 → v = 10.\n\n"
  "Atalho: a média 42 está a 2 do 40 e a 8 do 50 → as quantidades ficam na razão inversa, 8 vermelhas para 2 verdes. Verdes = 2/10 de 50 = 10.\n\n"
  "Média 42 bem perto de 40 já avisa: há muito mais vermelhas.", dificuldade=2)

assert F(7 * 9, 3 * 9) == F(7, 3)
Q("itupeva", 18, "sequencias-logicas", "Sequência numérica: padrão e termo", "E",
  "Observe a seguinte sequência lógica numérica:\n\n7/3, 14/6, 21/9, …\n\nQuando o denominador for 27, em um determinado elemento da sequência, o numerador será:",
  ["35.", "39.", "49.", "42.", "63."],
  "No termo n, a fração é 7n / 3n: letra {G}.\n\n"
  "| n | 1 | 2 | 3 | … | 9 |\n|---|---|---|---|---|---|\n| numerador | 7 | 14 | 21 | … | 63 |\n| denominador | 3 | 6 | 9 | … | 27 |\n\n"
  "Denominador 27 → n = 27 ÷ 3 = 9 → numerador 7 × 9 = 63.\n\n"
  "Todos os termos valem 7/3; o que muda é só a forma de escrever.", dificuldade=1)

assert 2400 * 1.05 / 12 == 210
Q("itupeva", 19, "porcentagem-progressoes", "Porcentagem: cálculo básico", "E",
  "Suponha que um cliente tomará emprestado num banco a quantia de R$ 2.400,00 e pagará uma taxa de 5% do valor. O cliente pagará o montante da sua dívida em 12 iguais parcelas mensais. Qual será o valor da parcela mensal paga pelo cliente?",
  ["R$ 228,00.", "R$ 252,00.", "R$ 240,00.", "R$ 200,00.", "R$ 210,00."],
  "Montante primeiro, divisão depois: letra {G}.\n\n"
  "Montante = 2.400 × 1,05 = 2.520. Parcela = 2.520 ÷ 12 = 210.\n\n"
  "A taxa aqui é de 5% sobre o valor, uma vez só — não 5% ao mês.\n\n"
  "R$ 200 é a parcela sem a taxa; R$ 252 é o montante dividido por 10.", dificuldade=1)

assert isqrt(5 * 5 - 4 * 4) == 3 and 4 * 3 / 2 == 6
Q("itupeva", 20, "geometria", "Teorema de Pitágoras", "A",
  "Indique a área de um triângulo retângulo que tem um dos catetos com medida de 4 cm e a hipotenusa com medida de 5 cm:",
  ["6 cm².", "9 cm².", "10 cm².", "15 cm².", "20 cm²."],
  "Pitágoras para o cateto que falta, depois a área: letra {G}.\n\n"
  "5² = 4² + b² → 25 = 16 + b² → b = 3.\n\n"
  "No triângulo retângulo, os dois catetos são base e altura: A = 3 × 4 ÷ 2 = 6 cm².\n\n"
  "Atalho: 3-4-5 é o triângulo pitagórico mais cobrado (e seus múltiplos 6-8-10, 9-12-15).\n\n"
  "Pegadinha: 10 cm² é 4 × 5 ÷ 2 — usar a hipotenusa como altura.", dificuldade=1)

# ── ITUPREV 2024 ─────────────────────────────────────────────────────────

assert 200 - F(200, 1000) * 100 == 180
Q("ituprev", 11, "razao-proporcao", "Divisão em partes proporcionais", "B",
  "Uma mãe paga uma mesada para os seus 4 filhos de acordo com a tabela:\n\n| Filho | Valor |\n|---|---|\n| Ana | R$ 500,00 |\n| Bruna | R$ 300,00 |\n| Carlos | R$ 200,00 |\n| Davi | Não recebe |\n\n"
  "Suponha que Davi começará a receber R$ 100,00 e que a mãe irá subtrair a quantia dos demais filhos para não alterar o total que ela atualmente já gasta com as suas mesadas. Suponha também que a redução que cada filho sofrerá será diretamente proporcional ao quanto eles atualmente ganham. Quanto Carlos passará a receber após os ajustes?",
  ["R$ 150,00.", "R$ 180,00.", "R$ 130,00.", "R$ 190,00.", "R$ 198,00."],
  "Os R$ 100 saem dos três na proporção 500 : 300 : 200. Letra {G}.\n\n"
  "Total atual: 1.000. Carlos ganha 200/1.000 = 20% do total → paga 20% da redução: 0,2 × 100 = 20.\n\n"
  "| Filho | Antes | Corte | Depois |\n|---|---|---|---|\n| Ana | 500 | 50 | 450 |\n| Bruna | 300 | 30 | 270 |\n| Carlos | 200 | 20 | 180 |\n| Davi | 0 | — | 100 |\n\n"
  "Conferência: 450 + 270 + 180 + 100 = 1.000. Todos perderam os mesmos 10%.", dificuldade=2)

assert 100_000 * 0.75 * 1.24 == 93_000
Q("ituprev", 12, "porcentagem-progressoes", "Aumentos e descontos sucessivos", "C",
  "João comprou um carro por cem mil reais e após alguns anos vendeu para Marcelo com um desconto de 25%. Marcelo passou mais alguns anos com o carro, e após uma alta valorização do mercado, vendeu o carro com um acréscimo de 24% sobre o valor que ele comprou. Por quanto Marcelo vendeu o carro?",
  ["R$ 99.000,00.", "R$ 124.000,00.", "R$ 93.000,00.", "R$ 98.990,00.", "R$ 95.000,00."],
  "Sucessivos se MULTIPLICAM: letra {G}.\n\n"
  "100.000 × 0,75 = 75.000 (Marcelo compra). 75.000 × 1,24 = 93.000 (Marcelo vende).\n\n"
  "Pegadinha: −25% e +24% não dão −1% (que seria 99.000). O 24% incide sobre 75 mil, não sobre 100 mil.\n\n"
  "Atalho: 0,75 × 1,24 = 0,93 → queda total de 7%.", dificuldade=2)

agua, alcool = F(280 * 2, 7) - 2, F(280 * 5, 7) - 10
assert (agua, alcool) == (78, 190) and agua / alcool == F(39, 95)
Q("ituprev", 13, "razao-proporcao", "Razão: cálculo e interpretação", "B",
  "Um recipiente contém uma mistura de água e álcool na proporção de 2:5, com um volume total de 280 ml. O recipiente foi deixado aberto por 24 horas e o líquido evaporou parcialmente. Sabe-se que evaporou 10 ml de álcool e 2 ml de água nas 24 horas. Qual a nova proporção entre água e álcool após a evaporação?",
  ["25:88.", "39:95.", "31:99.", "12:41.", "33:70."],
  "Volumes primeiro, razão depois: letra {G}.\n\n"
  "2 + 5 = 7 partes → 280 ÷ 7 = 40 ml cada parte.\n\n"
  "| | Antes | Evaporou | Depois |\n|---|---|---|---|\n| água | 2 × 40 = 80 | 2 | 78 |\n| álcool | 5 × 40 = 200 | 10 | 190 |\n\n"
  "78 : 190, simplificando por 2 → 39 : 95.\n\n"
  "Razão se aplica a quantidade, não a variação: subtrair 2 e 10 direto de 2:5 não faz sentido.", dificuldade=2)

Q("ituprev", 14, "geometria", "Ângulos e triângulos", "E",
  "Observe as seguintes afirmativas a respeito de polígonos convexos:",
  ["Somente I.", "Somente II.", "I e II.", "II e III.", "I, II e III."],
  "Todas certas: letra {G}.\n\n"
  "I — certa. A soma dos ângulos internos de QUALQUER triângulo é 180°, seja ele escaleno, isósceles ou equilátero.\n\n"
  "II — certa. Losango é o quadrilátero de quatro lados iguais; é a definição dele.\n\n"
  "III — certa. Quadrado: internos 4 × 90° = 360°. Os externos de qualquer polígono convexo somam 360°. As duas somas dão 360°.\n\n"
  "| Polígono de n lados | Soma |\n|---|---|\n| ângulos internos | (n − 2) × 180° |\n| ângulos externos | sempre 360° |\n\n"
  "No quadrado (n = 4): (4 − 2) × 180° = 360° — é o único polígono em que as duas somas coincidem.",
  afirmacoes=["A soma dos ângulos internos de um triângulo é sempre igual a 180° mesmo se o triângulo for escaleno;",
              "Um losango tem necessariamente todos os lados congruentes;",
              "A soma dos ângulos internos de um quadrado é igual à soma dos seus ângulos externos;"],
  dificuldade=2)

sol = [(a, b) for a in range(4) for b in range(3) if 2 * a + 3 * b == 7]
assert sol == [(2, 1)]
Q("ituprev", 15, "equacoes-1-grau", "Equação do 1º grau: problemas", "A",
  "Em uma determinada modalidade de um jogo de basquete só há cestas de 2 e 3 pontos. Sabe-se que um jogador nessa modalidade fez 7 pontos no total. Quantas cestas no total esse jogador fez?",
  ["3.", "4.", "5.", "6.", "7."],
  "2a + 3b = 7 com a e b inteiros: letra {G}.\n\n"
  "| cestas de 3 (b) | pontos que sobram | cestas de 2 (a) |\n|---|---|---|\n| 0 | 7 | 3,5 — não serve |\n| 1 | 4 | 2 ✔ |\n| 2 | 1 | 0,5 — não serve |\n\n"
  "Única solução: 2 cestas de 2 e 1 de 3 → 3 cestas.\n\n"
  "Atalho: 7 é ímpar e 2a é par → precisa de um número ímpar de cestas de 3.", dificuldade=1)

por_maquina = F(60, 5 * 3)
assert F(65) / (5 * por_maquina + por_maquina * F(3, 2)) == F(5, 2)
Q("ituprev", 16, "regra-de-tres", "Regra de três composta", "A",
  "Em uma lavanderia, 5 máquinas idênticas trabalham juntas lavando 60 kg de roupa a cada 3 horas. Se o gerente adquirir mais uma máquina, cuja velocidade de lavagem seja 50% maior comparado a uma máquina do modelo já existente, então em quantas horas o novo conjunto de máquinas lavará 65 kg de roupa?",
  ["2,5.", "1,75.", "2,25.", "2,0.", "3,5."],
  "Converta tudo para kg por hora: letra {G}.\n\n"
  "1. 5 máquinas: 60 kg em 3 h = 20 kg/h → cada máquina 4 kg/h.\n"
  "2. Máquina nova: 50% mais rápida → 6 kg/h.\n"
  "3. Conjunto: 5 × 4 + 6 = 26 kg/h.\n"
  "4. 65 ÷ 26 = 2,5 h.\n\n"
  "Atalho: a nova vale 1,5 máquina antiga → equivale a 6,5 máquinas. Tempo = 65 ÷ (6,5 × 4) = 2,5 h.", dificuldade=3)

carol = [c for c in range(40) if 5 * (c + 4) == 4 * (c + 5 + 4)]
assert carol == [16]
Q("ituprev", 17, "equacoes-1-grau", "Equação do 1º grau: problemas", "C",
  "Sabe-se que André tem 5 anos a mais que a sua irmã, Carol, e que daqui a 4 anos Carol terá 4/5 da idade de André (também daqui a 4 anos). Quantos anos Carol tem atualmente?",
  ["12.", "25.", "16.", "20.", "21."],
  "Equação com as idades daqui a 4 anos: letra {G}.\n\n"
  "Carol = c; André = c + 5. Daqui a 4 anos: c + 4 = (4/5)(c + 9).\n\n"
  "5c + 20 = 4c + 36 → c = 16.\n\n"
  "Conferência: daqui a 4 anos, Carol 20 e André 25; 20/25 = 4/5. ✔\n\n"
  "Pegadinha: 20 é a idade de Carol DAQUI A 4 ANOS; a pergunta é a de hoje.", dificuldade=2)

dados = {"Física": 8, "Química": 14, "Português": 21, "História": 12, "Matemática": 29}
assert sorted(dados, key=dados.get)[1] == "História"
Q("ituprev", 18, "grandezas-tabelas-graficos", "Leitura de tabelas e gráficos", "D",
  "O gráfico abaixo mostra o número de estudantes de uma escola que participaram de olimpíadas em 5 áreas de conhecimento:\n\nCom base no gráfico, qual a área de conhecimento que teve o SEGUNDO MENOR número de estudantes em 2020?",
  ["Física.", "Química.", "Português.", "História.", "Matemática."],
  "Só as barras de 2020 (as claras): letra {G}.\n\n"
  "| Área | 2020 |\n|---|---|\n| Física | 8 (menor) |\n| História | 12 (segundo menor) |\n| Química | 14 |\n| Português | 21 |\n| Matemática | 29 |\n\n"
  "Pegadinhas: a legenda (ano errado — em 2021 o segundo menor seria Português, com 8) e o 'SEGUNDO' em caixa alta, que a banca põe porque sabe que a pressa marca o menor.",
  imagem=IMG + "ituprev-2024-grafico-olimpiadas.png",
  imagem_alt="Gráfico de barras, 2020 e 2021: Física 8 e 6; Química 14 e 16; Português 21 e 8; História 12 e 9; Matemática 29 e 27.",
  dificuldade=1)

senhas = ["".join(p) for p in permutations("2357")
          if p[p.index("7") + 1:p.index("7") + 2] == ("5",) and p.index("3") not in (0, 3)
          and p.index("2") < p.index("3")]
assert senhas == ["2375"]
Q("ituprev", 19, "relacoes-arbitrarias", "Ordenação e posições", "E",
  "Uma senha de quatro dígitos foi criada usando os números 2, 3, 5 e 7, sem repetições. Sabe-se que:\n\n• O número 5 está em uma posição imediatamente à direita do número 7.\n• O número 3 não é o primeiro nem o último.\n• O número 2 está antes do número 3.\n\nIndique a senha corretamente ordenada:",
  ["2357.", "5237.", "2753.", "7532.", "2375."],
  "Teste as alternativas contra as três regras: letra {G}.\n\n"
  "| Senha | 75 juntos? | 3 no meio? | 2 antes do 3? |\n|---|---|---|---|\n| 2357 | não (57) | sim | sim |\n| 5237 | não | sim | sim |\n| 2753 | sim | não (último) | sim |\n| 7532 | sim | sim | não |\n| 2375 | sim | sim | sim ✔ |\n\n"
  "Em questão de ordenação com alternativas prontas, testar é mais rápido que montar.", dificuldade=1)

assert F(7 * 1 + 8 * 3 + 10 * F(3, 4) * 6, 10) == F(76, 10)
Q("ituprev", 20, "media-aritmetica", "Média ponderada", "D",
  "Em uma faculdade, três atividades contribuíram para a nota final de um estudante, cada uma com pesos diferentes. A atividade ‘A’ tem peso 1, a atividade ‘B’ tem peso 3 e a atividade ‘C’ tem peso 6. As notas obtidas pelo estudante foram: 7 na atividade ‘A’, 8 na atividade ‘B’ e 10 na atividade ‘C’. Contudo, o professor aplicou uma penalidade de 25% sobre a nota da atividade ‘C’ devido a atraso na entrega. Indique a média aritmética ponderada final do estudante considerando a penalidade:",
  ["7,9.", "7,1.", "7,2.", "7,6.", "6,5."],
  "Penalidade na nota, depois a ponderada: letra {G}.\n\n"
  "C = 10 × 0,75 = 7,5.\n\n"
  "| Atividade | Nota | Peso | Nota × peso |\n|---|---|---|---|\n| A | 7 | 1 | 7 |\n| B | 8 | 3 | 24 |\n| C | 7,5 | 6 | 45 |\n| total | | 10 | 76 |\n\n"
  "Média = 76 ÷ 10 = 7,6.\n\n"
  "Pegadinha: tirar 25% da MÉDIA (sem penalidade daria 9,1) em vez de só da nota C.", dificuldade=2)

# ── Jaguariúna 2023 ──────────────────────────────────────────────────────

assert (1000 // 20) * (300 // 20) == 750
Q("jaguariuna", 11, "geometria", "Área e perímetro", "A",
  "Uma parede será construída utilizando tijolos de altura e comprimento iguais a 20 cm, e largura 10 cm. Eles serão colocados sempre em posição ‘vertical’, de forma que a espessura da parede será correspondente ao lado de 10 cm do tijolo. Quantos tijolos no mínimo serão necessários para construir uma parede de 10 metros de comprimento e 3 metros de altura? Considere que não haverá espaçamento entre tijolos adjacentes.",
  ["750.", "950.", "1050.", "1200.", "1350."],
  "Área da parede ÷ área da face do tijolo: letra {G}.\n\n"
  "A espessura (10 cm) é a do tijolo; a face visível é 20 cm × 20 cm.\n\n"
  "Comprimento: 1.000 ÷ 20 = 50 tijolos. Altura: 300 ÷ 20 = 15 fileiras. Total: 50 × 15 = 750.\n\n"
  "Pela área: 10 × 3 = 30 m² ÷ 0,04 m² = 750.\n\n"
  "Pegadinha: usar a face 20 × 10 (que daria 1.500, nem está nas alternativas) — a questão diz que o lado de 10 cm vira a espessura.", dificuldade=2)

assert gcd(60, 72, 120) == 12
Q("jaguariuna", 12, "numeros-divisibilidade", "MDC: dividir em grupos iguais", "B",
  "Uma empresa vende cestas de frutas e quer padronizar o conteúdo de todas as cestas para que sejam idênticos. As cestas contêm morangos, peras e maçãs (cada cesta deve conter x morangos, y peras e z maçãs). Em um determinado dia o estoque dispõe de 60 morangos, 72 peras e 120 maçãs. Neste dia, quantas cestas no máximo poderão ser feitas sabendo-se que as cestas devem ser idênticas e a empresa deve utilizar todas as frutas dispostas no estoque.",
  ["10.", "12.", "6.", "8.", "20."],
  "Máximo de grupos iguais sem sobra = MDC: letra {G}.\n\n"
  "60 = 2² × 3 × 5\n72 = 2³ × 3²\n120 = 2³ × 3 × 5\n\nMDC = fatores comuns com o menor expoente = 2² × 3 = 12.\n\n"
  "Cada cesta: 5 morangos, 6 peras, 10 maçãs.\n\n"
  "| Pergunta | Ferramenta |\n|---|---|\n| dividir em partes iguais, o maior possível | MDC |\n| quando voltam a coincidir | MMC |", dificuldade=1)

c, p = F(12, 10), F(2, 10)  # c + p e c − p
assert (c + p) / 2 == F(7, 10)
Q("jaguariuna", 13, "equacoes-1-grau", "Sistema de equações do 1º grau", "C",
  "Uma copiadora faz xerox de documentos. As cópias podem ser em preto-e-branco ou coloridas, e têm preços diferentes. Bruno foi na copiadora e pediu 10 xerox coloridas e 15 xerox preto e branco, e o valor total foi R$14,50. João foi na mesma copiadora e pediu 15 xerox coloridas e 10 xerox preto e branco, e pagou um valor total de R$ 15,50. Nessa situação, qual o valor da unidade da xerox colorida? Considere que o valor unitário das cópias não mudou entre as compras de Bruno e João.",
  ["R$ 0,60.", "R$ 0,65.", "R$ 0,70.", "R$ 0,75.", "R$ 0,80."],
  "Sistema simétrico: some e subtraia. Letra {G}.\n\n"
  "10c + 15p = 14,50\n15c + 10p = 15,50\n\n"
  "Somando: 25c + 25p = 30 → c + p = 1,20.\nSubtraindo: 5c − 5p = 1 → c − p = 0,20.\n\nc = (1,20 + 0,20) ÷ 2 = 0,70 (e p = 0,50).\n\n"
  "Conferência: 10 × 0,70 + 15 × 0,50 = 7 + 7,50 = 14,50. ✔\n\n"
  "Quando os coeficientes se trocam (10/15 e 15/10), somar e subtrair as equações resolve sem substituição.", dificuldade=2)

assert F(60, 500) == F(12, 100)
Q("jaguariuna", 14, "razao-proporcao", "Razão: cálculo e interpretação", "B",
  "Um fio de nylon tem diâmetro da ordem de 0,5 mm, e um fio de cabelo tem diâmetro da ordem de 60 micrômetros (μm). Um micrômetro representa um milionésimo de um metro (ou seja, 1 m = 1.000.000 μm). Qual a razão entre o diâmetro de um fio de cabelo e o diâmetro de um fio de nylon?",
  ["1,2.", "0,12.", "0,012.", "0,0012.", "0,00012."],
  "Mesma unidade, depois a razão na ordem pedida: letra {G}.\n\n"
  "0,5 mm = 500 μm (1 mm = 1.000 μm).\n\n"
  "cabelo ÷ nylon = 60 ÷ 500 = 0,12.\n\n"
  "Sem converter, 60 ÷ 0,5 = 120 — nem está nas alternativas, mas é o erro clássico.", dificuldade=2)

Q("jaguariuna", 15, "logica-argumentacao", "Negação de proposições (De Morgan)", "D",
  "Observe a seguinte sentença:\n\n“Nesta selva, um animal é caçador ou presa.”\n\nIndique a alternativa que apresenta a negação lógica da sentença:",
  ["Nesta selva, um animal é caçador mas não é presa.", "Nesta selva, um animal não é caçador ou não é presa.",
   "Nesta selva, um animal não é caçador, mas é presa.", "Nesta selva, um animal não é caçador e nem presa.",
   "Nesta selva, um animal não é caçador se e somente se não for presa."],
  "De Morgan: ~(p ∨ q) = ~p ∧ ~q. Letra {G}.\n\n"
  "Negar 'é caçador OU presa' é dizer que não é nenhum dos dois: não é caçador E não é presa.\n\n"
  "| Proposição | Negação |\n|---|---|\n| p ou q | não p e não q |\n| p e q | não p ou não q |\n| se p então q | p e não q |\n\n"
  "A alternativa B nega as partes mas não troca o conectivo — é a negação de 'p E q', o par que a banca usa para confundir.", dificuldade=1)

perim = 1 + 1 + 0.5 + sqrt(1 + 0.25)
assert abs(perim - 3.62) < 0.01
Q("jaguariuna", 16, "geometria", "Teorema de Pitágoras", "E",
  "Uma folha de papel de formato quadrado foi cortada conforme a figura:\n\nO ponto A é o ponto médio do lado. Indique o perímetro da figura resultante (em cm) sabendo-se que o lado do quadrado original media 1 cm. Dado: √5 ≈ 2,24.",
  ["1,12.", "1,24.", "3,24.", "3,06.", "3,62."],
  "Contorno da peça cinza: letra {G}.\n\n"
  "O corte vai de A (meio do lado esquerdo) até o canto inferior direito, e sai o triângulo de catetos 1 e 0,5.\n\n"
  "Corte = hipotenusa: √(1² + 0,5²) = √1,25 = √5 / 2 ≈ 2,24 ÷ 2 = 1,12.\n\n"
  "| Lado da figura | Medida |\n|---|---|\n| topo | 1 |\n| direita | 1 |\n| esquerda (topo até A) | 0,5 |\n| corte | 1,12 |\n| perímetro | 3,62 |\n\n"
  "Pegadinha: 1,12 é só o corte; esquecer o meio lado esquerdo dá 3,12.",
  imagem=IMG + "jaguariuna-2023-quadrado-cortado.png",
  imagem_alt="Um quadrado cinza e, ao lado, o mesmo quadrado cortado: o ponto A fica no meio do lado esquerdo, e um corte tracejado vai de A até o canto inferior direito, retirando o triângulo de baixo.",
  dificuldade=2)

assert abs(0.25 * 0.10 + 0.30 * 0.20 + 0.45 * 0.30 - 0.22) < 1e-9
Q("jaguariuna", 17, "porcentagem-progressoes", "Porcentagem: cálculo básico", "D",
  "Um fabricante de lâmpadas especiais produz lâmpadas azuis, vermelhas e amarelas. Da produção total, as azuis representam 25%, as vermelhas 30%, e as amarelas 45%. Num certo dia de produção, uma determinada máquina parou de funcionar e sabe-se que 10% das lâmpadas azuis apresentaram defeitos. O mesmo aconteceu para 20% das lâmpadas vermelhas e 30% das lâmpadas amarelas. Nessa situação, quantos por cento do total da produção diária apresentou defeito?",
  ["30%.", "28%.", "24%.", "22%.", "20%."],
  "Porcentagem de porcentagem, depois a soma: letra {G}.\n\n"
  "| Cor | Parte do total | Defeito | Do total |\n|---|---|---|---|\n| azul | 25% | 10% | 2,5% |\n| vermelha | 30% | 20% | 6% |\n| amarela | 45% | 30% | 13,5% |\n| total | | | 22% |\n\n"
  "Atalho: pense em 100 lâmpadas — 2,5 + 6 + 13,5 = 22.\n\n"
  "Pegadinha: a média simples de 10, 20 e 30 dá 20% — mas as cores não têm o mesmo peso.", dificuldade=2)

original = F(76) / F(95, 100)
assert original == 80 and original * F(90, 100) == 72
Q("jaguariuna", 18, "porcentagem-progressoes", "Aumentos e descontos sucessivos", "C",
  "Um supermercado utiliza uma estratégia sucessiva de descontos a depender da quantidade de um dado item em estoque e da proximidade do seu vencimento. A tabela abaixo mostra o desconto aplicado sobre o valor original do produto a depender dessas variáveis:\n\n"
  "| Dias para o vencimento | > 5000 itens | 3000 a 4999 | 1000 a 2999 | < 999 |\n|---|---|---|---|---|\n| > 30 | 5% | 3% | 0% | 0% |\n| 30 a 21 | 10% | 5% | 5% | 0% |\n| 20 a 11 | 30% | 20% | 10% | 2% |\n| 01 a 10 | 60% | 50% | 30% | 10% |\n\n"
  "Um determinado produto que tinha 1500 unidades em estoque, faltando 25 dias para o seu vencimento, estava sendo comercializado por R$ 76,00. Após 5 dias, foram vendidas apenas 200 unidades. Qual o novo valor do produto?",
  ["R$ 76,00.", "R$ 72,20.", "R$ 72,00.", "R$ 66,60.", "R$ 64,00."],
  "O desconto é sobre o valor ORIGINAL — ache-o primeiro. Letra {G}.\n\n"
  "1. Antes: 1.500 itens e 25 dias → coluna 1000–2999, linha 30–21 → 5%. 76 = 0,95 × original → original = 80.\n"
  "2. Depois: 1.300 itens e 20 dias → mesma coluna, linha 20–11 → 10%. Novo preço: 80 × 0,90 = 72,00.\n\n"
  "Pegadinha: aplicar 10% sobre 76 dá 68,40; aplicar 5% a mais sobre 76 dá 72,20 (alternativa B). A tabela fala em desconto 'sobre o valor original'.", dificuldade=3)

Q("jaguariuna", 19, "sequencias-logicas", "Sequência figural e ciclos (resto da divisão)", "D",
  "Observe a seguinte sequência lógica figural:\n\nDe acordo com as correspondências abaixo, indique o elemento que deve ser colocado na posição faltante (marcado com um ponto de interrogação):",
  ["I.", "II.", "III.", "IV.", "V."],
  "A matriz é simétrica em relação à diagonal principal: letra {G}.\n\n"
  "| | col 1 | col 2 | col 3 |\n|---|---|---|---|\n| linha 1 | ▲ | ● | ■ |\n| linha 2 | ● | ▲ | ✕ |\n| linha 3 | ■ | ? | ▲ |\n\n"
  "A diagonal é toda ▲, e cada posição (linha i, coluna j) repete a (linha j, coluna i): ● em (1,2) e (2,1), ■ em (1,3) e (3,1). Então (3,2) = (2,3) = ✕, a figura IV.\n\n"
  "Em sequência figural 3 × 3, teste as linhas, as colunas e a simetria antes de procurar regra complicada.",
  imagem=IMG + "jaguariuna-2023-sequencia-figural.png",
  imagem_alt="Matriz 3×3 de figuras. Linha 1: triângulo, círculo, quadrado. Linha 2: círculo, triângulo, X. Linha 3: quadrado, ponto de interrogação, triângulo. Opções: I triângulo, II círculo, III quadrado, IV X, V estrela.",
  dificuldade=2)

assert F(68 - 20, 20) == F(240, 100)
Q("jaguariuna", 20, "grandezas-tabelas-graficos", "Leitura de tabelas e gráficos", "A",
  "Um estudante fará um vestibular no mês de novembro. Ele começou a estudar no mês de janeiro e adotou uma estratégia de fazer, a cada final de mês, uma prova de anos anteriores deste mesmo vestibular. Assim ele conseguiria acompanhar sua evolução ao longo do ano de estudo. O gráfico abaixo mostra o número de questões acertadas, dentre as 90 que são aplicadas anualmente:\n\nCom base no gráfico, pode-se afirmar que o aumento percentual do número de acertos do estudante no mês de outubro, comparado com o número de acertos no mês de janeiro, foi de:",
  ["240%.", "53%.", "140%.", "340%.", "75%."],
  "Aumento percentual = (novo − antigo) ÷ antigo: letra {G}.\n\n"
  "Janeiro 20, outubro 68. (68 − 20) ÷ 20 = 48 ÷ 20 = 2,4 = 240%.\n\n"
  "| Conta | Resultado | É |\n|---|---|---|\n| 68 ÷ 20 | 3,4 = 340% | o valor de outubro em relação a janeiro |\n| (68 − 20) ÷ 20 | 2,4 = 240% | o AUMENTO ✔ |\n| 68 ÷ 90 | 75% | o aproveitamento em outubro |\n\n"
  "Pegadinha: 340% é 'quanto outubro vale de janeiro', não 'quanto aumentou'. As 90 questões da prova não entram.",
  imagem=IMG + "jaguariuna-2023-grafico-vestibular.png",
  imagem_alt="Gráfico de barras de acertos por mês: janeiro 20, fevereiro 22, março 26, abril 35, maio 43, junho 40, julho 49, agosto 53, setembro 55, outubro 68.",
  dificuldade=2)

# ── SAAE Amparo 2023 ─────────────────────────────────────────────────────

assert F(8, 100) * 600 * 5 == 240
Q("saae", 11, "regra-de-tres", "Regra de três simples direta", "C",
  "Para viajar até a cidade A, distante cinquenta quilômetros de sua casa, um motorista utiliza seu automóvel, o qual consome oito litros de gasolina para realizar o trajeto de ida e volta até a referida cidade. Considerando que cada litro de combustível custa R$ 5,00 (cinco reais), qual o valor total gasto pelo condutor ao realizar uma viagem de ida e volta até a cidade B, utilizando o mesmo automóvel e considerando o mesmo consumo de combustível por quilômetro rodado? Considere que a cidade B está a trezentos quilômetros de sua residência.",
  ["R$ 200,00", "R$ 220,00", "R$ 240,00", "R$ 260,00", "R$ 280,00"],
  "Ida e volta nos dois casos: letra {G}.\n\n"
  "A: 100 km (ida e volta) → 8 L. B: 600 km (ida e volta) → 6 vezes mais → 48 L. 48 × 5 = R$ 240.\n\n"
  "Pegadinha: comparar 50 km com 300 km é a mesma razão (×6) — mas quem calcula 8 L para 50 km dobra o consumo e erra.", dificuldade=1)

L = 45 - F(20, 100) * 150
assert 4 * L == 60
Q("saae", 12, "geometria", "Área e perímetro", "D",
  "Qual o perímetro, em metros, de um terreno quadrado, cujo lado L pode ser calculado pela equação: L = 45 – X? Considere que o valor de X equivale a 20% (vinte por cento) de 150.",
  ["30", "40", "50", "60", "70"],
  "Três passos curtos: letra {G}.\n\nX = 0,20 × 150 = 30. L = 45 − 30 = 15. Perímetro = 4 × 15 = 60 m.\n\n"
  "A alternativa 30 é o X; quem para no meio marca o número que acabou de achar.", dificuldade=1)

assert 25 * 2 * 3 == 150
Q("saae", 13, "grandezas-tabelas-graficos", "Leitura de tabelas e gráficos", "E",
  "O gráfico a seguir representa a quantidade de pó, em gramas, que determinado robô aspirador é capaz de recolher ao ser utilizado. Considerando que a bateria do eletrodoméstico possui capacidade de mantê-lo funcionando por duas horas, qual a massa de pó, em gramas, que ele irá aspirar, até seu completo desligamento, após submeter-se a duas recargas, certo que iniciou sua atividade com carga completa?",
  ["50", "75", "100", "125", "150"],
  "Taxa do gráfico × tempo total de bateria: letra {G}.\n\n"
  "Taxa: de 3 h (75 g) para 5 h (125 g) são +50 g em 2 h → 25 g/h. A reta passa pela origem (75 ÷ 3 = 25).\n\n"
  "Tempo: carga inicial + 2 recargas = 3 cargas × 2 h = 6 h.\n\nMassa: 25 × 6 = 150 g.\n\n"
  "Pegadinha: contar só as duas recargas (4 h → 100 g) e esquecer a carga completa do início.",
  imagem=IMG + "saae-amparo-2023-grafico-aspirador.png",
  imagem_alt="Gráfico de linha reta: massa de pó aspirada (gramas) por tempo de funcionamento (horas). Pontos: 3 h = 75 g; 5 h = 125 g; 7 h = 175 g; 9 h = 225 g; 11 h = 275 g.",
  dificuldade=2)

meses = {"jan": 16 * 155, "fev": 19 * 150, "mar": 18 * 145, "abr": 17 * 155}
assert max(meses, key=meses.get) == "fev"
Q("saae", 14, "grandezas-tabelas-graficos", "Leitura de tabelas e gráficos", "B",
  "A fim de efetuar o controle de seus ganhos, uma empregada doméstica que presta serviços como diarista montou a seguinte planilha, onde é possível verificar, nos primeiros quatro meses de um ano, o número de faxinas que realizou e o valor recebido por cada uma delas. Com base nos dados abaixo, em qual mês ela auferiu maior remuneração, considerando todos os valores recebidos dentro do período?\n\n"
  "| Mês | Nº de faxinas | Valor de cada |\n|---|---|---|\n| Jan | 16 | R$ 155,00 |\n| Fev | 19 | R$ 150,00 |\n| Mar | 18 | R$ 145,00 |\n| Abr | 17 | R$ 155,00 |",
  ["janeiro", "fevereiro", "março", "abril", "em março e abril, onde recebeu o mesmo valor total"],
  "Faxinas × valor, mês a mês: letra {G}.\n\n"
  "| Mês | Conta | Total |\n|---|---|---|\n| jan | 16 × 155 | 2.480 |\n| fev | 19 × 150 | 2.850 |\n| mar | 18 × 145 | 2.610 |\n| abr | 17 × 155 | 2.635 |\n\n"
  "Fevereiro tem o menor valor por faxina e mesmo assim o maior total — a quantidade pesou mais.", dificuldade=1)

assert 3 * 3 ** 2 * 50 == 1350
Q("saae", 15, "geometria", "Área e perímetro", "B",
  "Um construtor deseja adquirir azulejos a fim de revestir apenas o fundo de uma piscina circular, a qual possui diâmetro de 6 metros. Considerando Pi = 3, e que o valor do metro quadrado de azulejo que ele deseja comprar custa R$ 50,00 (cinquenta reais), qual o valor total dispendido por ele para adquirir a quantidade necessária do produto?",
  ["R$ 1.200,00", "R$ 1.350,00", "R$ 1.700,00", "R$ 3.500,00", "R$ 5.400,00"],
  "Área do círculo usa o RAIO: letra {G}.\n\n"
  "r = 6 ÷ 2 = 3 m. A = π r² = 3 × 9 = 27 m². Custo: 27 × 50 = R$ 1.350.\n\n"
  "Pegadinha: usar o diâmetro como raio → 3 × 36 = 108 m² → R$ 5.400 (alternativa E).", dificuldade=1)

assert lcm(20, 45, 65, 80) == 9360
Q("saae", 16, "numeros-divisibilidade", "MMC: eventos que se repetem", "D",
  "Considere os seguintes números: 20, 45, 65 e 80. Qual o MMC – mínimo múltiplo comum – deles?",
  ["2.340", "3.120", "4.680", "9.360", "14.040"],
  "Fatore e pegue cada primo com o MAIOR expoente: letra {G}.\n\n"
  "20 = 2² × 5\n45 = 3² × 5\n65 = 5 × 13\n80 = 2⁴ × 5\n\n"
  "MMC = 2⁴ × 3² × 5 × 13 = 16 × 9 × 65 = 9.360.\n\n"
  "Teste rápido: o MMC tem de ser múltiplo de 80 → 9.360 ÷ 80 = 117. 4.680 ÷ 80 não dá inteiro, e 2.340 também não.", dificuldade=2)

assert 0.2 * 0.5 == 0.1
Q("saae", 17, "sistemas-de-medidas", "Conversão de comprimento e área", "A",
  "Considere que um retângulo possui um dos lados medindo vinte centímetros e o outro medindo cinquenta centímetros. Qual a área total deste retângulo, em metros quadrados?",
  ["0,1", "0,3", "0,5", "0,7", "0,9"],
  "Converta os lados para metro antes de multiplicar: letra {G}.\n\n0,20 m × 0,50 m = 0,10 m².\n\n"
  "Pelo outro caminho: 20 × 50 = 1.000 cm², e 1 m² = 10.000 cm² → 0,1 m².\n\n"
  "Área anda de 100 em 100 por unidade (1 m = 100 cm, mas 1 m² = 10.000 cm²).", dificuldade=1)

assert 500 * 1.2 * 30 == 18_000
Q("saae", 18, "porcentagem-progressoes", "Porcentagem: cálculo básico", "C",
  "Para suprir a demanda regular de produção de energia, uma usina termoelétrica que funciona ininterruptamente utiliza, em média, quinhentos litros de óleo por dia. Em um mês em que houve necessidade de aumento da produção de energia em 20% (vinte por cento), o que acarreta o mesmo aumento proporcional no consumo de combustível, qual será o volume total, em litros, de óleo utilizado pela usina? Considere que o mês possui 30 (trinta) dias.",
  ["15.000", "16.000", "18.000", "20.000", "22.000"],
  "Aumento de 20% = multiplicar por 1,2: letra {G}.\n\n500 × 1,2 = 600 L/dia × 30 dias = 18.000 L.\n\n"
  "15.000 é o mês SEM o aumento (500 × 30).", dificuldade=1)

assert 10 ** 2 + 10 ** 2 == 200
Q("saae", 19, "geometria", "Teorema de Pitágoras", "D",
  "Um morador deseja dividir uma sala, que possui formato quadrado, construindo uma parede ligando os vértices opostos por meio de uma linha diagonal, formando assim dois triângulos retângulos. Considerando que a sala possui lados iguais a 10 (dez) metros, a parede que a separará terá comprimento, em metros, equivalente a:",
  ["Raiz quadrada de 25", "Raiz quadrada de 100", "Raiz quadrada de 150", "Raiz quadrada de 200", "Raiz quadrada de 250"],
  "Diagonal do quadrado por Pitágoras: letra {G}.\n\nd² = 10² + 10² = 200 → d = √200 (= 10√2 ≈ 14,1 m).\n\n"
  "Atalho: diagonal do quadrado de lado ℓ = ℓ√2. Diagonal do cubo = ℓ√3.", dificuldade=1)

assert 1_500_000 / 2 * 0.8 == 600_000
Q("saae", 20, "porcentagem-progressoes", "Porcentagem: cálculo básico", "B",
  "João e Maria divorciaram-se, certo que, diante do regime de bens adotado por eles quando do casamento, cada um ficaria com metade do patrimônio do casal quando da separação. Considerando que o casal possuía bens que totalizavam o montante de R$ 1.500.000,00 (um milhão e quinhentos mil reais), e que Maria, após receber sua parte, irá doar 20 % (vinte por cento) de tudo o que receber, qual o valor da partilha que restará a ela após referida doação?",
  ["R$ 500.000,00", "R$ 600.000,00", "R$ 650.000,00", "R$ 675.000,00", "R$ 700.000,00"],
  "Metade, depois 80% da metade: letra {G}.\n\n1.500.000 ÷ 2 = 750.000. Doa 20% → fica com 80%: 750.000 × 0,8 = 600.000.\n\n"
  "Fica com 80% = multiplicar por 0,8 direto, sem calcular a doação à parte.", dificuldade=1)

# ── São Miguel Arcanjo 2023 ──────────────────────────────────────────────

precos = {"300": F(15, 300), "500": F(20, 500), "750": F(30, 750)}
assert precos["500"] == precos["750"] < precos["300"]
Q("sma", 11, "razao-proporcao", "Razão: cálculo e interpretação", "E",
  "Ao se dirigir a uma barraca que comercializa chope artesanal, um consumidor deparou-se com os seguintes preços: 300ml do produto custam R$15,00; 500ml custam R$20,00 e 750ml custam R$30,00. Nesta situação, qual das opções representará maior economia para o consumidor, considerando o volume do produto adquirido e o valor pago?",
  ["300ml", "500ml", "750ml", "300ml ou 500ml, visto que ambos possuem o mesmo valor por volume do produto",
   "500ml ou 750ml, visto que ambos possuem o mesmo valor por volume do produto"],
  "Compare o preço por mL: letra {G}.\n\n"
  "| Copo | Conta | R$ por mL |\n|---|---|---|\n| 300 mL | 15 ÷ 300 | 0,05 |\n| 500 mL | 20 ÷ 500 | 0,04 |\n| 750 mL | 30 ÷ 750 | 0,04 |\n\n"
  "500 e 750 empatam no mais barato por mL.\n\n"
  "Pegadinha: achar que o maior copo é sempre o mais vantajoso.", dificuldade=1)

assert 0.5 * 6 == 3
Q("sma", 12, "geometria", "Área e perímetro", "D",
  "Um carpinteiro, durante a construção de uma residência, necessita de uma ripa de madeira retangular que possua 3 m² de área. Dentre as configurações abaixo, qual representa o objeto que pode ser utilizado pelo trabalhador em sua obra, considerando que os valores representam o cumprimento dos lado do retângulo:",
  ["100 centímetros e 2 metros", "100 centímetros e 2,5 metros", "50 centímetros e 3 metros",
   "50 centímetros e 6 metros", "160 centímetro e 2 metros"],
  "Converta para metro e multiplique: letra {G}.\n\n"
  "| Lados | Área |\n|---|---|\n| 1 m × 2 m | 2 m² |\n| 1 m × 2,5 m | 2,5 m² |\n| 0,5 m × 3 m | 1,5 m² |\n| 0,5 m × 6 m | 3 m² ✔ |\n| 1,6 m × 2 m | 3,2 m² |\n\n"
  "Misturar cm e m sem converter (50 × 6 = 300) é o erro que a questão quer.", dificuldade=1)

assert 4 * 30 * 30 / 1000 == 3.6
Q("sma", 13, "sistemas-de-medidas", "Conversão de volume e capacidade (litro e m³)", "C",
  "Um metro cúbico de água equivale ao volume aproximado de 1.000 litros do mesmo líquido. Considerando uma família de 4 pessoas, onde cada indivíduo consome diariamente 30 litros de água, e considerando um mês contendo 30 (trinta) dias, o consumo de água desta família no referido mês, em m³, foi de:",
  ["3,2", "3,4", "3,6", "3,8", "4,0"],
  "Litros no mês, depois ÷ 1.000: letra {G}.\n\n4 × 30 × 30 = 3.600 L = 3,6 m³.\n\n"
  "| Unidade | Equivale |\n|---|---|\n| 1 m³ | 1.000 L |\n| 1 dm³ | 1 L |\n| 1 cm³ | 1 mL |", dificuldade=1)

assert F(138_000 - 120_000, 120_000 * 10) == F(15, 1000)
Q("sma", 14, "juro-simples", "Juro simples: juros, montante, taxa e prazo", "B",
  "Um investidor necessita obter o valor de R$138.000,00 a fim de efetuar o pagamento de uma dívida. Nesta situação, considerando que ele possui o capital inicial de R$120.000,00, e que o valor deverá permanecer aplicado por 10 (dez) meses, e que após este prazo será efetuado o pagamento da referida dívida, qual a taxa de juros mensal, considerando o regime de juros simples, que ele deve obter a fim de saldar sua dívida sem que haja qualquer sobra:",
  ["1,0%", "1,5%", "1,8%", "2,0%", "2,3%"],
  "J = C × i × t, com J = montante − capital: letra {G}.\n\n"
  "J = 138.000 − 120.000 = 18.000.\n18.000 = 120.000 × i × 10 → i = 18.000 ÷ 1.200.000 = 0,015 = 1,5% ao mês.\n\n"
  "Atalho: 18.000 é 15% de 120.000 em 10 meses → 1,5% por mês (no juro simples a taxa se divide pelo tempo).", dificuldade=2)

assert 2400 * 4.2 * 1000 == 10_080_000
Q("sma", 15, "operacoes-numeros-reais", "Operações com inteiros e expressões numéricas", "A",
  "Considere uma pessoa que necessita, diariamente, de 2.400 quilocalorias de energia. Considere, ainda, que 1 quilocaloria equivale a aproximadamente 4,2 quilojoules de energia, e que o prefixo quilo equivale a 1.000 unidades. Nesta situação, quantos Joules de energia este indivíduo necessita ingerir por dia?",
  ["10.080.000.", "10.800.000.", "12.000.000", "13.200.000", "18.000.000"],
  "Duas conversões em cadeia: letra {G}.\n\n2.400 kcal × 4,2 = 10.080 kJ. 10.080 kJ × 1.000 = 10.080.000 J.\n\n"
  "Pegadinha: 10.800.000 troca a ordem dos algarismos (2.400 × 4,5) — confira a conta, não o 'formato' do número.", dificuldade=1)

assert pi  # (π da prova é sempre o valor dado no enunciado)
