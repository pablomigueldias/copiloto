"""Carrega o Perfil Mestre de um JSON para o Postgres.

    python scripts/importar_perfil.py                    # data/perfil_mestre.json
    python scripts/importar_perfil.py --arquivo outro.json
    python scripts/importar_perfil.py --conferir         # só mostra o que falta

O arquivo é a versão editável; o banco é a versão que os agentes leem. Rodar de
novo **atualiza** o perfil ativo em vez de criar outro — perfil duplicado faria
a F2.5 indexar duas versões de mim, e a busca devolveria a errada metade das
vezes.

Depois de importar, `python scripts/ingerir.py --fonte perfil` põe o perfil no
índice de conhecimento (ou o worker faz isso sozinho em até 10 min).

**Este é o arquivo mais importante do projeto que não é código.** Se o perfil
estiver raso, todo currículo sai raso — nenhum modelo conserta o que não sabe.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import DATA_DIR
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.session import dispose_engine, get_session

PADRAO = DATA_DIR / "perfil_mestre.json"

# As colunas do modelo que o JSON preenche. Chave com `_` é anotação para mim
# (`_leia_me`, `_falta`) e não vai para o banco.
CAMPOS = (
    "nome", "titulo", "resumo", "tom_escrita", "habilidades", "projetos",
    "experiencias", "formacao", "certificacoes", "o_que_procuro",
    "blocos_curriculo", "contato",
)

AMARELO, VERDE, CINZA, FIM = "\033[33m", "\033[32m", "\033[90m", "\033[0m"


def buracos(dados: dict) -> list[str]:
    """O que está faltando e importa — checado no dado, não na lista escrita à mão.

    Projeto sem `prova` é o buraco caro: é a linha com número, a que separa
    "fiz um pipeline" de "reduzi de 3h para 20min".
    """
    faltas: list[str] = []

    sem_prova = [p["nome"] for p in dados.get("projetos") or [] if not p.get("prova")]
    if sem_prova:
        faltas.append(f"{len(sem_prova)} projeto(s) sem NÚMERO de resultado: {', '.join(sem_prova)}")

    procuro = dados.get("o_que_procuro") or {}
    vazios = [k for k in ("modelo", "tipo_empresa", "pretensao") if not procuro.get(k)]
    if vazios:
        faltas.append(f"o_que_procuro sem: {', '.join(vazios)}")

    if not dados.get("tom_escrita"):
        faltas.append("tom_escrita vazio — a carta vai sair com voz de robô")

    for exp in dados.get("experiencias") or []:
        if len(str(exp.get("periodo", ""))) <= 4:
            faltas.append(f"{exp.get('empresa')}: período sem mês (só '{exp.get('periodo')}')")

    return faltas


async def importar(dados: dict) -> tuple[PerfilMestre, bool]:
    """Atualiza o perfil ativo, ou cria o primeiro."""
    campos = {k: v for k, v in dados.items() if k in CAMPOS}

    async with get_session() as session:
        perfil = await session.scalar(
            select(PerfilMestre).where(PerfilMestre.ativo.is_(True)).order_by(
                PerfilMestre.created_at
            )
        )
        criou = perfil is None
        if perfil is None:
            perfil = PerfilMestre(nome=campos.get("nome", "sem nome"))
            session.add(perfil)

        for chave, valor in campos.items():
            setattr(perfil, chave, valor)
        perfil.ativo = True

        await session.commit()
        await session.refresh(perfil)

    return perfil, criou


def _resumo(dados: dict) -> str:
    contar = lambda k: len(dados.get(k) or [])  # noqa: E731
    return (
        f"{contar('habilidades')} habilidades · {contar('projetos')} projetos · "
        f"{contar('experiencias')} experiências · {contar('certificacoes')} certificações"
    )


async def main() -> int:
    p = argparse.ArgumentParser(description="Importa o Perfil Mestre para o banco.")
    p.add_argument("--arquivo", type=Path, default=PADRAO)
    p.add_argument("--conferir", action="store_true", help="Não grava; só aponta o que falta.")
    args = p.parse_args()

    if not args.arquivo.exists():
        print(f"Não achei {args.arquivo}.")
        return 1

    dados = json.loads(args.arquivo.read_text(encoding="utf-8"))
    faltas = buracos(dados)

    try:
        if not args.conferir:
            perfil, criou = await importar(dados)
            print(f"{VERDE}{'criado' if criou else 'atualizado'}{FIM}  {perfil.nome} — {_resumo(dados)}")
            print(f"{CINZA}indexe com: python scripts/ingerir.py --fonte perfil{FIM}")
        else:
            print(f"{perfil_nome(dados)} — {_resumo(dados)}")

        if faltas:
            print(f"\n{AMARELO}o que ainda falta (o modelo NÃO vai preencher por você):{FIM}")
            for f in faltas:
                print(f"  · {f}")
        return 0
    finally:
        await dispose_engine()


def perfil_nome(dados: dict) -> str:
    return dados.get("nome") or "(sem nome)"


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
