"""Gera as inéditas: bd-*-ineditas.json (t1..t7), pt-*-ineditas.json (pt.py), mat-*-ineditas.json (mat.py) e en-*-ineditas.json (en.py).

Rodar de novo regrava; o import é idempotente pela origem."""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import en, mat, pt, t1, t2, t3, t4, t5, t6, t7  # noqa: E401

DESTINO = Path(__file__).resolve().parents[2] / "data" / "estudo"
MODULO_BD = {"nome": "Banco de dados — inéditas", "trilha": "concurso", "ordem": 2}
MODULO_PT = {"nome": "Língua portuguesa — inéditas", "trilha": "concurso", "ordem": 6}
MODULO_MAT = {"nome": "Matemática e raciocínio lógico — inéditas", "trilha": "concurso", "ordem": 4}
MODULO_EN = {"nome": "Inglês técnico — inéditas", "trilha": "concurso", "ordem": 8}

LEIA_ME = (
    "Questões INÉDITAS, escritas por mim (Claude) a pedido do Pablo em 02/10/2026 — não são de banca nenhuma, e o gabarito e a explicação "
    "são meus. Moram num módulo separado ('Banco de dados — inéditas') para nunca se misturarem com as questões de prova real. "
    "Cada tópico é um item do programa de Conhecimentos Específicos do edital CRECI-SP 01/2026 (Instituto Avança SP), cargo PAS – Analista "
    "de TI – Banco de Dados, Anexo II; o item está no campo `fonte` de cada questão. "
    "FORMATO: imita o padrão das bancas que caem nessa prova — cinco alternativas (Avança SP, Cesgranrio, FCC, Vunesp), enunciado de "
    "cenário ('Considere que...', estilo Cesgranrio), afirmações I/II/III, NÃO/INCORRETO em caixa alta e questões de código SQL. "
    "O gabarito é distribuído entre A e E de propósito, para que a posição não dê pista. "
    "VERIFICAÇÃO: as questões de código SQL do tópico de SQL rodam contra um banco SQLite com as mesmas tabelas do enunciado, "
    "no gerador (scripts/ineditas_bd/gerar.py), e o resultado é conferido com o gabarito antes de gravar. As demais foram conferidas na "
    "documentação dos SGBDs como eu a conheço — sem fonte externa citada; desconfie e corrija se a prova real disser outra coisa. "
    "Para pedir mais: 'faz mais X questões' (ver a memória `questoes-ineditas-bd`)."
)

LEIA_ME_PT = (
    "Questões INÉDITAS de Língua Portuguesa, escritas por mim (Claude) a pedido do Pablo em 02/10/2026 — sem banca; gabarito e explicação "
    "são meus. Seguem o programa de Língua Portuguesa de nível superior do edital CRECI-SP 01/2026 (Avança SP), com peso nos tópicos que o "
    "acervo de prova real tinha finos em 02/10 (análise sintática, colocação pronominal, figuras, redação oficial, regência). Base: "
    "norma-padrão da gramática tradicional e o Manual de Redação da Presidência da República, 3ª ed. (2018). Interpretação de texto e "
    "coesão ficaram de fora desta leva por já terem muitas questões reais."
)

LEIA_ME_MAT = (
    "Questões INÉDITAS de Matemática e Raciocínio Lógico, escritas por mim (Claude) a pedido do Pablo em 02/10/2026 — sem banca; gabarito e "
    "explicação são meus. Seguem o programa do edital CRECI-SP 01/2026 (Avança SP), com peso no que o acervo real tinha fino (diagramas "
    "lógicos, relações arbitrárias, média ponderada, MMC/MDC, sistemas, regra de três composta). TODA conta e todo problema de lógica é "
    "conferido por script no gerador (scripts/ineditas_bd/mat.py, `verificar`): os problemas de relações arbitrárias são resolvidos por "
    "força bruta e só entram se a solução for única."
)

LEIA_ME_EN = (
    "Questões INÉDITAS de Inglês técnico, escritas por mim (Claude) a pedido do Pablo em 07/10/2026 — sem banca; textos de apoio, gabarito e "
    "explicação são meus. A Avança SP não tem nenhuma questão de inglês nas 14 provas levantadas; o padrão vem da pesquisa em "
    "docs/avanca-sp/ingles-tecnico-padrao.md (Cesgranrio: texto + perguntas em inglês; FCC/Vunesp: perguntas em português) e o conteúdo, "
    "do programa de Inglês Técnico do edital CRECI-SP 01/2026. Cada questão traz o `assunto` do simulado. As normas citadas (RFC 2119, "
    "NIST SP 800-63B, NIST CSF 2.0, ISO/IEC 27001) foram conferidas como eu as conheço, sem fonte externa aberta na hora — desconfie e corrija."
)


def grava(T, modulo, leia_me):
    origens = [q["origem"] for q in T.questoes]
    assert len(set(origens)) == len(origens), T.nome
    conteudo = {"_leia_me": leia_me, "banca": "Inéditas", "modulo": modulo,
                "topico": {"nome": T.nome, "ordem": T.ordem}, "questoes": T.questoes}
    nome = f"{T.slug}-ineditas.json"
    (DESTINO / nome).write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return nome


def main():
    for rotulo, topicos, modulo, leia_me in (
        ("BD", [m.T for m in (t1, t2, t3, t4, t5, t6, t7)], MODULO_BD, LEIA_ME),
        ("PT", pt.TOPICOS, MODULO_PT, LEIA_ME_PT),
        ("MAT", mat.TOPICOS, MODULO_MAT, LEIA_ME_MAT),
        ("EN", en.TOPICOS, MODULO_EN, LEIA_ME_EN),
    ):
        letras = collections.Counter()
        for T in topicos:
            letras += collections.Counter(q["gabarito"] for q in T.questoes)
            print(f"  {grava(T, modulo, leia_me):44} {len(T.questoes)}")
        print(rotulo, sum(letras.values()), dict(sorted(letras.items())))


main()
