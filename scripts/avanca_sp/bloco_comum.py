"""Transcreve o bloco comum (Português e Matemática) das provas da Avança SP de
cargos que não são de TI — as que chegaram em 07/10/2026.

    .venv/bin/python scripts/avanca_sp/bloco_comum.py          # grava os JSON
    .venv/bin/python scripts/importar_questoes.py data/estudo/<arquivo>-avanca-sp.json

Por que cargo que não é de TI serve: a Avança SP aplica o mesmo bloco comum a
todos os cargos de um concurso (Americana 2022, São Miguel Arcanjo 2023 e SAAE
Amparo 2023 confirmam pelo gabarito: as 25 primeiras respostas são idênticas
entre o cargo de TI e os outros). O Português e a Matemática do Analista
Legislativo são os mesmos que o Analista de TI faria. A parte específica
(legislação, contabilidade, fiscalização) não cai na prova de BD e ficou de
fora, assim como Noções de Informática e Atualidades, que o edital do
CRECI-SP 01/2026 não tem.

Também ficou de fora o que é de Português mas não está no programa do edital:
formação de palavras (prefixo, sufixo, elementos mórficos).

O GABARITO NÃO É DIGITADO AQUI. Cada questão diz a letra que eu cheguei
resolvendo (`g`), e o script lê a resposta oficial no PDF da banca, no bloco do
cargo, com o mesmo `bloco_do_cargo` do `conferir_gabaritos_avanca_sp.py`. Se as
duas não batem, o script para — a questão não entra com o gabarito de ninguém
até eu olhar.

A questão entra no arquivo do tópico (`<topico>-avanca-sp.json`), ao lado das
outras da banca; rodar de novo substitui pela origem, sem duplicar.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from conferir_gabaritos_avanca_sp import PROVAS, bloco_do_cargo  # noqa: E402

DESTINO = RAIZ / "data" / "estudo"

# chave → (órgão e ano como vai na origem, cargo, PDF do gabarito, cargo no PDF)
FONTES = {
    "embu": ("Câmara de Embu-Guaçu 2022", "Analista Legislativo",
             "gabarito-embu-guacu-2022-preliminar.pdf", "ANALISTA LEGISLATIVO"),
    "itupeva": ("Câmara de Itupeva 2024", "Analista Legislativo - Contabilidade Pública",
                "gabarito-itupeva-2024-preliminar.pdf", "ANALISTA LEGISLATIVO - CONTABILIDADE PÚBLICA"),
    "ituprev": ("ITUPREV Itu 2024", "Analista Previdenciário",
                "gabarito-ituprev-2024-definitivo.pdf", "ANALISTA PREVIDENCIÁRIO"),
    "jaguariuna": ("Câmara de Jaguariúna 2023", "Analista Legislativo",
                   "gabarito-jaguariuna-2023-preliminar.pdf", "ANALISTA LEGISLATIVO"),
    "saae": ("SAAE Amparo 2023", "Analista Fiscalização",
             "gabarito-saae-amparo-2023-preliminar.pdf", "ANALISTA FISCALIZAÇÃO"),
    "sma": ("Prefeitura de São Miguel Arcanjo 2023", "Analista Fiscal de Tributos Municipais",
            "gabarito-sao-miguel-arcanjo-2023-definitivo.pdf", "ANALISTA FISCAL DE TRIBUTOS MUNICIPAIS"),
}

_oficial: dict[str, dict[int, str]] = {}
QUESTOES: list[tuple[str, dict]] = []  # (arquivo do tópico, questão)


def Q(prova: str, n: int, arquivo: str, assunto: str, g: str, enunciado: str,
      alternativas: list[str], explicacao: str, *, texto: str | None = None,
      fonte_texto: str | None = None, afirmacoes: list[str] | None = None,
      imagem: str | None = None, imagem_alt: str | None = None,
      dificuldade: int = 2) -> None:
    orgao, cargo, pdf, bloco = FONTES[prova]
    if prova not in _oficial:
        _oficial[prova] = bloco_do_cargo(PROVAS / pdf, bloco)
    oficial = _oficial[prova].get(n)
    if oficial != g:
        raise SystemExit(f"{orgao} questão {n}: resolvi {g}, o gabarito da banca diz {oficial}. Olhar antes.")
    assert len(alternativas) == 5, (prova, n)
    q = {
        "formato": "afirmacoes" if afirmacoes else "multipla_escolha",
        "origem": f"Instituto Avança SP · {orgao} · {cargo} · questão {n}",
        "assunto": assunto,
        "enunciado": enunciado,
        "alternativas": [{"letra": "ABCDE"[i], "texto": t} for i, t in enumerate(alternativas)],
        "gabarito": oficial,
        "dificuldade": dificuldade,
        "explicacao": explicacao.replace("{G}", oficial),
    }
    if texto:
        q["texto_base"] = texto
        if fonte_texto:
            q["texto_base_fonte"] = fonte_texto
    if afirmacoes:
        q["afirmacoes"] = afirmacoes
    if imagem:
        q["imagem"], q["imagem_alt"] = imagem, imagem_alt
    assert "**" not in q["explicacao"] + enunciado, q["origem"]
    QUESTOES.append((arquivo, q))


NOTA = (" Em 07/10/2026 entrou o bloco comum (Português e Matemática) de seis provas da Avança SP de cargos "
        "que não são de TI — Embu-Guaçu 2022, Jaguariúna 2023, SAAE Amparo 2023, São Miguel Arcanjo 2023, "
        "Itupeva 2024 e ITUPREV 2024 —, pelo scripts/avanca_sp/bloco_comum.py: gabarito lido no PDF da banca, "
        "no bloco do cargo; explicações MINHAS, não da banca.")


def grava() -> None:
    por_arquivo: dict[str, list[dict]] = {}
    for arq, q in QUESTOES:
        por_arquivo.setdefault(arq, []).append(q)
    for arq, novas in sorted(por_arquivo.items()):
        caminho = DESTINO / f"{arq}-avanca-sp.json"
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        origens = {q["origem"] for q in novas}
        dados["questoes"] = [q for q in dados["questoes"] if q["origem"] not in origens] + novas
        if NOTA.strip() not in dados["_leia_me"]:
            dados["_leia_me"] += "\n\n" + NOTA.strip()
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {caminho.name:48} +{len(novas)}  (total {len(dados['questoes'])})")
    print(f"{len(QUESTOES)} questões, todas com o gabarito da banca conferido.")


if __name__ == "__main__":
    # Os módulos de dados registram em `bloco_comum` importado, que é outro
    # objeto que este `__main__` — por isso a gravação sai de lá.
    import bloco_comum
    import matematica  # noqa: F401
    import portugues  # noqa: F401
    bloco_comum.grava()
