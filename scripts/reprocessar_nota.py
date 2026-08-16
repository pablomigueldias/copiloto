"""Passa uma nota de transcrição pelo pipeline atual, de novo.

    python scripts/reprocessar_nota.py "<caminho>"              # mostra o que faria
    python scripts/reprocessar_nota.py "<caminho>" --aplicar

## Por que existe

O pipeline melhora com o uso: o glossário aprende termos, o prompt aprende a
descartar "se inscreve no canal", o fichamento passou a produzir a seção
**Para lembrar**. Mas as notas já escritas ficam como estavam — congeladas na
versão do dia em que foram gravadas.

Reprocessar resolve isso **sem o áudio**: a nota já tem o texto, e o texto é o
que o pipeline consome. O que muda é tudo que vem depois — limpeza, fichamento,
vizinhos, destaques.

## O que ele preserva

`titulo`, `tags` e a pasta que **eu** escolhi na tela. O modelo sugeriu uma vez
e eu corrigi; reprocessar não pode desfazer essa correção — seria o mesmo
defeito do currículo que ignorava a minha edição.

O arquivo original é guardado como `<nome>.bak` antes de qualquer escrita.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import sys
from pathlib import Path

from app.conhecimento import transcricao as tr
from app.conhecimento.fontes import _frontmatter
from app.conhecimento.varredura import ingerir
from app.db.session import dispose_engine

VERDE, AMARELO, CINZA, NEGRITO, FIM = "\033[32m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"

# O corpo da nota fica depois de `## Conteúdo`; o resto (resumo, conceitos,
# perguntas) é fichamento antigo e vai ser refeito.
_MARCA_CONTEUDO = "## Conteúdo"
# Seções geradas que não fazem parte do conteúdo e não devem voltar como
# entrada — senão o modelo reescreve a própria lista de wikilinks.
_MARCAS_FIM = ("## Relacionado", "## Revisão da transcrição")


# `⏱ 08:20` no começo de um bloco. Reprocessar sem ler isto apagava os carimbos
# da nota: a gravação original sabia o instante de cada pedaço, e o texto é a
# única cópia dessa informação depois que o áudio foi embora.
_CARIMBO = re.compile(r"^`⏱ (\d+):(\d\d)`\s*$", re.MULTILINE)


def marcas_do_corpo(corpo: str) -> list[tuple[int, str]] | None:
    """Reconstrói `[(segundo, texto)]` a partir dos carimbos que a nota já tem.

    Sem isto, reprocessar uma nota gravada devolvia uma nota sem `⏱` — o
    pipeline melhorava e a navegação pelo vídeo se perdia junto.
    """
    marcas: list[tuple[int, str]] = []
    achados = list(_CARIMBO.finditer(corpo))
    if not achados:
        return None

    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(corpo)
        trecho = corpo[m.end() : fim].strip()
        if trecho:
            marcas.append((int(m.group(1)) * 60 + int(m.group(2)), trecho))
    return marcas or None


def corpo_da_nota(texto: str) -> str:
    """Só o conteúdo — sem frontmatter, sem as seções que o fichamento monta."""
    _, sem_fm = _frontmatter(texto)
    if _MARCA_CONTEUDO in sem_fm:
        sem_fm = sem_fm.split(_MARCA_CONTEUDO, 1)[1]
    for marca in _MARCAS_FIM:
        sem_fm = sem_fm.split(marca, 1)[0]
    return sem_fm.strip()


async def reprocessar(
    caminho: Path, *, aplicar: bool, vault: Path, refazer_titulo: bool = False
) -> int:
    if not caminho.is_file():
        sys.exit(f"Nota não encontrada: {caminho}")

    original = caminho.read_text(encoding="utf-8")
    fm, _ = _frontmatter(original)
    corpo = corpo_da_nota(original)
    if not corpo:
        sys.exit("Não achei o conteúdo da nota (falta a seção '## Conteúdo'?).")

    print(f"{NEGRITO}{caminho.name}{FIM}  {CINZA}{len(corpo.split())} palavras{FIM}")
    print(f"{CINZA}o modelo local está reprocessando…{FIM}\n")

    marcas = marcas_do_corpo(corpo)
    if marcas:
        # Recuperados, os carimbos viram metadado e saem do texto. Deixá-los
        # ali fazia o filtro de ruído engolir um junto com a frase seguinte —
        # `⏱ 00:00` não tem ponto final, então grudava em "Professor X aqui".
        corpo = _CARIMBO.sub("", corpo).strip()
        print(f"{CINZA}{len(marcas)} carimbo(s) de tempo recuperados do texto{FIM}")

    nota = await tr.processar(
        corpo,
        tema=str(fm.get("titulo") or caminho.stem),
        raiz_vault=vault,
        # Senão a nota vira vizinha de si mesma e linka para o próprio arquivo.
        excluir=caminho,
        marcas=marcas,
    )

    # O que eu escolhi na tela continua meu: reprocessar não desfaz correção.
    # Mas o script não distingue "título que eu corrigi" de "título que o modelo
    # errou e ninguém tocou" — daí o `--refazer-titulo`.
    ficha = nota.fichamento
    if not refazer_titulo:
        ficha.titulo = str(fm.get("titulo") or ficha.titulo)
    ficha.pasta = str(caminho.parent.relative_to(vault))
    if fm.get("tags") and not refazer_titulo:
        ficha.tags = [str(t).strip() for t in fm["tags"] if str(t).strip()]

    marca = "(refeito)" if refazer_titulo else "(preservado)"
    print(f"{NEGRITO}título{FIM}   {ficha.titulo}   {CINZA}{marca}{FIM}")
    print(f"{NEGRITO}pasta{FIM}    {ficha.pasta}   {CINZA}(preservada){FIM}")
    print(f"{NEGRITO}tags{FIM}     {', '.join(ficha.tags)}")
    if ficha.destaques:
        print(f"\n{NEGRITO}para lembrar{FIM}")
        for d in ficha.destaques:
            print(f"  · {d}")
    if ficha.relacionadas:
        print(f"\n{NEGRITO}vai linkar para{FIM}  {', '.join(ficha.relacionadas)}")
    if nota.corrigidos:
        print(f"\n{NEGRITO}glossário corrigiu{FIM}")
        for c in nota.corrigidos:
            print(f"  · {c}")

    antes, depois = len(corpo.split()), len(nota.corpo.split())
    print(f"\n{CINZA}conteúdo: {antes} → {depois} palavras "
          f"({100 * (depois - antes) // max(antes, 1):+d}%){FIM}")

    if not aplicar:
        print(f"\n{AMARELO}Nada foi gravado. Rode com --aplicar.{FIM}")
        return 0

    backup = caminho.with_suffix(".md.bak")
    shutil.copy2(caminho, backup)
    caminho.write_text(
        tr.montar_markdown(
            nota,
            fonte=str(fm.get("fonte") or "gravação"),
            duracao_min=float(fm["duracao_min"]) if fm.get("duracao_min") else None,
        ),
        encoding="utf-8",
    )
    print(f"\n{VERDE}✓ nota reescrita{FIM}  {caminho}")
    print(f"{CINZA}  original em {backup.name}{FIM}")

    for tipo, r in (await ingerir(tipos=["nota"], caminho=str(caminho))).items():
        print(f"{CINZA}  {tipo}: {r}{FIM}")
    return 0


async def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("nota", help="Caminho do .md a reprocessar.")
    p.add_argument("--aplicar", action="store_true")
    p.add_argument(
        "--refazer-titulo",
        action="store_true",
        help="Deixa o modelo propor titulo e tags de novo (use quando eu nunca os corrigi).",
    )
    p.add_argument("--vault", help="Raiz do vault (padrão: a fonte 'nota' do .env).")
    args = p.parse_args()

    from app.conhecimento.gravacao import vault as vault_padrao

    vault = Path(args.vault).expanduser() if args.vault else vault_padrao()
    try:
        return await reprocessar(
            Path(args.nota).expanduser(),
            aplicar=args.aplicar,
            vault=vault,
            refazer_titulo=args.refazer_titulo,
        )
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
