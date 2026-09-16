"""Confere o gabarito do acervo contra o PDF oficial da banca.

O acervo do Instituto Avança SP foi transcrito de `docs/avanca-sp/`, e a
transcrição é de onde vem o erro que mais custa caro aqui: gabarito errado não
é questão difícil, é questão que ensina a coisa errada e ainda por cima
reforçada por repetição espaçada. Este script fecha o circuito — lê o PDF do
gabarito que a banca publicou, casa questão a questão pela `origem` e diz o
que não bate.

Os PDFs ficam em `docs/avanca-sp/Provas/`, que é ignorado pelo git (material
pessoal). Sem eles o script diz quais faltam e sai; ele não é parte do import.

Um detalhe do formato do PDF que custou um falso positivo inteiro: o gabarito
traz **todos os cargos do concurso** em sequência, cada um com o mesmo bloco
de "01: A  02: B ...". Os primeiros 25 itens são a prova comum (português,
raciocínio lógico) e são idênticos entre cargos; só os específicos divergem.
Ler um item a mais que o bloco do cargo certo devolve a resposta do cargo
seguinte — e foi exatamente isso que aconteceu quando o corte dependia de
reconhecer o título por acento. O corte agora é estrutural: dentro de um
cargo, a primeira linha que não é linha de resposta encerra o bloco.
"""
from __future__ import annotations

import glob
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PROVAS = BASE / "docs/avanca-sp/Provas"

# gabarito em PDF → cargo cujo bloco interessa. A chave é como a `origem` das
# questões nomeia a prova: "<município em minúsculas>-<ano>-<cargo em minúsculas>".
#
# O cargo entrou na chave em 15/09/2026, e não é firula: Americana 2022 aplicou
# DOIS cargos de TI no mesmo concurso, e a chave sem cargo casava as questões do
# Analista Programador contra o bloco de respostas do Analista de Administração
# de Dados — onze divergências que não existiam. (As 25 primeiras questões dos
# dois cargos são idênticas; só os específicos divergem, e é ali que dava ruim.)
FONTES: dict[str, tuple[str, str]] = {
    "americana-2022-analista de administração de dados": (
        "gabarito-americana-2022-definitivo.pdf",
        "ANALISTA DE ADMINISTRAÇÃO DE DADOS",
    ),
    "americana-2022-analista programador de sistemas": (
        "gabarito-americana-2022-definitivo.pdf",
        "ANALISTA PROGRAMADOR DE SISTEMAS",
    ),
    "embu-guaçu-2023-analista de tecnologia da informação": (
        "gabarito-embu-guacu-2023-definitivo.pdf",
        "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO",
    ),
    "itatiba-2024-analista de tecnologia da informação": (
        "gabarito-itatiba-2024-preliminar.pdf",
        "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO",
    ),
    "juquitiba-2024-analista de tecnologia da informação": (
        "gabarito-juquitiba-2024-preliminar.pdf",
        "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO",
    ),
    "rio grande da serra-2024-analista de tecnologia da informação": (
        "gabarito-rio-grande-da-serra-2024-preliminar.pdf",
        "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO",
    ),
    # Provas que entraram no acervo em 15/09/2026.
    "amparo-2022-analista de tecnologia da informação": (
        "gabarito-amparo-2022-definitivo.pdf",
        "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO",
    ),
    "taboão da serra-2022-analista de tecnologia da informação": (
        "gabarito-taboao-da-serra-2022-definitivo.pdf",
        "ANALISTA DE TECNOLOGIA DA INFORMAÇÃO",
    ),
    "caçapava-2024-analista de informática": (
        "gabarito-cacapava-2024-preliminar.pdf",
        "ANALISTA DE INFORMÁTICA",
    ),
    "paraty-2024-analista de sistema": (
        "gabarito-paraty-2024-preliminar.pdf",
        "ANALISTA DE SISTEMA",
    ),
    "taubaté-2025-analista de sistema sênior": (
        "gabarito-unitau-2025-preliminar.pdf",
        "ANALISTA DE SISTEMA SÊNIOR",
    ),
    "rio claro-2026-analista em tecnologia da informação": (
        "gabarito-rio-claro-2026-definitivo.pdf",
        "ANALISTA EM TECNOLOGIA DA INFORMAÇÃO",
    ),
}

LINHA_DE_RESPOSTA = re.compile(r"^\d{2}:\s*[A-EX]\b")
RESPOSTA = re.compile(r"(\d{2}):\s*([A-EX])")
# "Instituto Avança SP · Prefeitura de Americana 2022 · <cargo> · questão 26"
ORIGEM = re.compile(
    r"·\s*(?:Prefeitura|Câmara|Universidade|Consórcio)?\s*(?:Municipal\s*)?(?:de\s*)?"
    r"([^·]+?)\s*(\d{4})\s*·\s*([^·]+?)\s*·.*questão\s*(\d+)"
)


def bloco_do_cargo(pdf: Path, cargo: str) -> dict[int, str]:
    """As respostas de um cargo. O bloco acaba na primeira linha que não é resposta."""
    texto = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True
    ).stdout
    respostas: dict[int, str] = {}
    dentro = False
    for linha in texto.split("\n"):
        s = linha.strip()
        if not s or "pcimark" in s:
            continue
        if not dentro:
            dentro = s == cargo
            continue
        if not LINHA_DE_RESPOSTA.match(s):
            break  # começou outro cargo
        respostas.update({int(n): letra for n, letra in RESPOSTA.findall(s)})
    return respostas


def main() -> int:
    if not PROVAS.is_dir():
        print(f"sem {PROVAS} — os PDFs das provas ficam fora do repositório.")
        return 1

    oficiais: dict[str, dict[int, str]] = {}
    for chave, (arquivo, cargo) in FONTES.items():
        pdf = PROVAS / arquivo
        if not pdf.is_file():
            print(f"· falta {arquivo}")
            continue
        oficiais[chave] = bloco_do_cargo(pdf, cargo)
        print(f"· {chave}: {len(oficiais[chave])} respostas em {arquivo}")

    divergem: list[str] = []
    sem_fonte: dict[str, int] = {}
    total = 0
    for arquivo in sorted(glob.glob(str(BASE / "data/estudo/*-avanca-sp.json"))):
        dados = json.loads(Path(arquivo).read_text())
        for q in dados["questoes"]:
            total += 1
            m = ORIGEM.search(q["origem"])
            if not m:
                divergem.append(f"origem ilegível: {q['origem']}")
                continue
            chave = f"{m.group(1).strip().lower()}-{m.group(2)}-{m.group(3).strip().lower()}"
            numero = int(m.group(4))
            if chave not in oficiais:
                sem_fonte[chave] = sem_fonte.get(chave, 0) + 1
                continue
            oficial = oficiais[chave].get(numero)
            if oficial != q["gabarito"]:
                divergem.append(
                    f"{Path(arquivo).name} · {q['origem']}\n"
                    f"    acervo={q['gabarito']}  oficial={oficial}"
                )

    conferidas = total - sum(sem_fonte.values())
    print(f"\n{conferidas} de {total} questões conferidas contra o PDF da banca.")
    if sem_fonte:
        print("Sem gabarito em PDF (o acervo veio da transcrição em docs/):")
        for chave, n in sorted(sem_fonte.items()):
            print(f"  {chave}: {n} questões")
    if divergem:
        print(f"\n{len(divergem)} DIVERGÊNCIAS:")
        for d in divergem:
            print(f"  {d}")
        return 1
    print("\nNenhuma divergência.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
