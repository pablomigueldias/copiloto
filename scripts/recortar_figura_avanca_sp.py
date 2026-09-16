"""Recorta a figura de uma questão do caderno do Instituto Avança SP.

    .venv/bin/python scripts/recortar_figura_avanca_sp.py \
        docs/avanca-sp/Provas/amparo-2022-analista-de-ti.pdf 41 \
        data/estudo/imagens/avanca-sp/amparo-2022-topologia-b.png

A prova é de duas colunas, e é por isso que este script existe: recortar "a
metade de cima da página" pega meia figura e metade de outra questão. Aqui o
recorte vem da coordenada que o próprio PDF declara — `pdftotext -bbox-layout`
dá a caixa de cada palavra, e com ela dá para achar onde começa "QUESTÃO N",
onde começa a primeira alternativa, e qual faixa vertical entre as duas não tem
palavra nenhuma. Essa faixa é a figura.

Três casos que o caminho simples erra, e que estão tratados:

1. **Cabeçalho centrado na página** significa questão de coluna única, com
   figura larga. Cortar no meio a partiria ao meio.
2. **A figura transborda a coluna.** Se na faixa não houver palavra da outra
   coluna, o recorte pode ir até a borda da página.
3. **Figura com rótulo de texto dentro** ("Q1", "5 m", "AVENIDA") quebra a
   faixa vazia em pedaços pequenos. Nesse caso passe `--bloco`: recorta a
   questão inteira, com enunciado e tudo. Fica mais sujo e é o certo — isolar
   só o desenho cortaria a legenda de que ele depende.

`--bloco` também é a saída para questão cujas ALTERNATIVAS são imagens (I a V
desenhados), em que não existe "a figura" separada do resto.
"""
import re
import subprocess
import sys
from xml.etree import ElementTree as ET

from PIL import Image

NS = '{http://www.w3.org/1999/xhtml}'

def palavras(pdf):
    xml = subprocess.run(['pdftotext', '-bbox-layout', pdf, '-'],
                         capture_output=True, text=True).stdout
    raiz = ET.fromstring(xml)
    for i, pag in enumerate(raiz.iter(NS + 'page'), 1):
        larg, alt = float(pag.get('width')), float(pag.get('height'))
        for w in pag.iter(NS + 'word'):
            yield {'pag': i, 'larg': larg, 'alt': alt, 't': (w.text or '').strip(),
                   'x0': float(w.get('xMin')), 'y0': float(w.get('yMin')),
                   'x1': float(w.get('xMax')), 'y1': float(w.get('yMax'))}

def recorta(pdf, numero, saida, dpi=200, ate_alternativa=True, bloco=False):
    ws = list(palavras(pdf))
    marcas = [i for i, w in enumerate(ws)
              if re.fullmatch(r'QUEST[ÃA]O', w['t'], re.I)
              and i + 1 < len(ws) and re.fullmatch(rf'0?{numero}', ws[i+1]['t'])]
    if not marcas:
        return None
    i = marcas[0]
    ini = ws[i]
    coluna_meio = ini['larg'] / 2
    # Cabeçalho centrado na página inteira = questão de coluna única (a figura
    # larga ocupa a largura toda e cortar no meio a partiria ao meio).
    unica = abs(ini['x0'] - coluna_meio) < ini['larg'] * 0.10
    if unica:
        coluna_meio = ini['larg']
    esquerda = ini['x0'] < coluna_meio
    x0, x1 = (0, coluna_meio) if esquerda else (coluna_meio, ini['larg'])
    fim_y = ini['alt']
    for w in ws[i+1:]:
        if w['pag'] != ini['pag']:
            break
        if (w['x0'] < coluna_meio) != esquerda:
            continue
        if w['y0'] <= ini['y1']:
            continue
        if ate_alternativa and re.fullmatch(r'\(?[A-E]\)?', w['t']) and w['x0'] < x0 + (x1-x0)*0.25:
            fim_y = w['y0']
            break
        if re.fullmatch(r'QUEST[ÃA]O', w['t'], re.I):
            fim_y = w['y0']
            break
    # A figura é a faixa vertical sem palavra nenhuma dentro da questão: acha
    # o maior vão entre linhas de texto da coluna e recorta só ele.
    linhas = sorted({round(w['y0'], 1) for w in ws
                     if w['pag'] == ini['pag'] and (w['x0'] < coluna_meio) == esquerda
                     and ini['y1'] <= w['y0'] <= fim_y}
                    | {round(w['y1'], 1) for w in ws
                       if w['pag'] == ini['pag'] and (w['x0'] < coluna_meio) == esquerda
                       and ini['y1'] <= w['y1'] <= fim_y})
    vao = (ini['y1'], fim_y)
    if linhas and not bloco:
        pares = [(linhas[k], linhas[k+1]) for k in range(len(linhas)-1)]
        pares.append((linhas[-1], fim_y))
        a, b = max(pares, key=lambda p: p[1]-p[0])
        if b - a > 30:
            vao = (a, b)
    topo_y, fim_y = vao

    # A figura costuma transbordar a coluna. Se na faixa não houver palavra da
    # outra coluna, o recorte pode ir até a borda da página; se houver, para
    # pouco antes dela.
    vizinhas = [w for w in ws if w['pag'] == ini['pag']
                and (w['x0'] < coluna_meio) != esquerda
                and w['y1'] > topo_y and w['y0'] < fim_y]
    if esquerda:
        x1 = min([w['x0'] for w in vizinhas], default=ini['larg']) - 4
        x1 = max(x1, coluna_meio)
    else:
        x0 = max([w['x1'] for w in vizinhas], default=0.0) + 4
        x0 = min(x0, coluna_meio)

    png = '/tmp/_pag.png'
    subprocess.run(['pdftoppm', '-r', str(dpi), '-png', '-f', str(ini['pag']),
                    '-l', str(ini['pag']), '-singlefile', pdf, png[:-4]], check=True)
    img = Image.open(png)
    esc = img.size[0] / ini['larg']
    cx = (int(x0*esc), max(0, int(topo_y*esc) - 6), int(x1*esc),
          min(img.size[1], int(fim_y*esc) + 6))
    if cx[3] - cx[1] < 40:
        return None
    img.crop(cx).save(saida)
    return saida

if __name__ == '__main__':
    pdf, n, saida = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    bloco = '--bloco' in sys.argv
    print(recorta(pdf, n, saida, ate_alternativa=not bloco, bloco=bloco) or 'não encontrado')
