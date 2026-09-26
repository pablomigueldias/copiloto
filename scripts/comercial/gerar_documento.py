"""Gera o PDF de um modelo do kit documental (M01–M16).

    python scripts/comercial/gerar_documento.py M03-proposta.md campos.json saida.pdf
    python scripts/comercial/gerar_documento.py --com-notas M04-contrato.md campos.json revisao.pdf
    python scripts/comercial/gerar_documento.py --campo documento_numero=CONT-2026-001 M04-contrato.md campos.json c.pdf

O modelo é procurado em `data/comercial/modelos/` quando o caminho não existe.
`campos.json` é um objeto {campo: valor}. Falha, sem gerar nada, se algum
`{{campo}}` ficar sem valor. Precisa do extra [ui] (Playwright + Chromium) e do
pandoc no PATH. `--com-notas` inclui a parte depois de `<!-- notas -->` (a versão
para revisão, com os pontos para o advogado). `--campo chave=valor` (repetível) troca
um campo do JSON só nesta geração: o mesmo arquivo de campos serve a vários documentos.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.comercial.documentos import MODELOS, CampoFaltando, gerar_pdf


def main() -> int:
    args, com_notas, trocas = [], False, {}
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--com-notas":
            com_notas = True
        elif a == "--campo":
            chave, _, valor = next(it, "").partition("=")
            trocas[chave] = valor
        else:
            args.append(a)
    if len(args) != 3:
        print(__doc__)
        return 2
    modelo, campos, saida = (Path(a) for a in args)
    if not modelo.exists():
        modelo = MODELOS / modelo
    try:
        valores = json.loads(campos.read_text(encoding="utf-8")) | trocas
        destino = gerar_pdf(modelo.read_text(encoding="utf-8"), valores, saida, com_notas=com_notas)
    except CampoFaltando as e:
        print(f"não gerei: {e}")
        return 1
    print(f"gerado: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
