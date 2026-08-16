"""A fila de aprovação, pelo terminal.

    python scripts/fila.py                          # o que está pendente
    python scripts/fila.py --status editada         # o histórico
    python scripts/fila.py --ver <id>               # a ação inteira
    python scripts/fila.py --aprovar <id>
    python scripts/fila.py --aprovar <id> --texto "versão minha"   # vira 'editada'
    python scripts/fila.py --rejeitar <id> --motivo "tom errado"

Aceita id parcial (os 8 primeiros caracteres bastam) — ninguém digita uuid.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from app.db.models.acao_pendente import STATUS
from app.db.session import dispose_engine
from app.fila import servico

VERDE, AMARELO, VERMELHO, CINZA, FIM = (
    "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"
)
COR = {"pendente": AMARELO, "aprovada": VERDE, "editada": VERDE, "rejeitada": VERMELHO}


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fila de aprovação do Copiloto.")
    p.add_argument("--status", choices=[*STATUS, "todas"], default="pendente")
    p.add_argument("--agente")
    p.add_argument("--ver", metavar="ID")
    p.add_argument("--aprovar", metavar="ID")
    p.add_argument("--rejeitar", metavar="ID")
    p.add_argument("--texto", help="Texto final (com --aprovar). Diferente do gerado = editada.")
    p.add_argument("--motivo", help="Por que rejeitei (com --rejeitar).")
    return p.parse_args()


async def _resolver(parcial: str) -> UUID:
    """Aceita o uuid inteiro ou só o começo dele."""
    try:
        return UUID(parcial)
    except ValueError:
        pass

    _, todas = await servico.listar(status=None, limite=500)
    achadas = [a for a in todas if str(a.id).startswith(parcial.lower())]
    if not achadas:
        raise SystemExit(f"Nenhuma ação começa com {parcial!r}.")
    if len(achadas) > 1:
        raise SystemExit(f"{parcial!r} é ambíguo: {len(achadas)} ações.")
    return achadas[0].id


def _linha(a) -> str:
    cor = COR.get(a.status, "")
    return (
        f"{CINZA}{str(a.id)[:8]}{FIM}  {cor}{a.status:<9}{FIM} "
        f"{a.criada_em:%d/%m %H:%M}  {a.agente}/{a.tipo:<15} {a.titulo[:50]}"
    )


async def _listar(args: argparse.Namespace) -> int:
    status = None if args.status == "todas" else args.status
    total, itens = await servico.listar(status=status, agente=args.agente, limite=100)

    if not itens:
        print("Nada na fila." if status == "pendente" else "Nada encontrado.")
        return 0

    for a in itens:
        print(_linha(a))
    contagem = ", ".join(f"{s}={n}" for s, n in sorted((await servico.contar_por_status()).items()))
    print(f"\n{total} ação(ões) · {CINZA}{contagem}{FIM}")
    return 0


async def _ver(args: argparse.Namespace) -> int:
    a = await servico.obter(await _resolver(args.ver))
    cor = COR.get(a.status, "")

    print(f"\n{a.titulo}")
    print(f"{CINZA}{a.agente}/{a.tipo} · {cor}{a.status}{FIM}{CINZA} · {a.criada_em:%d/%m/%Y %H:%M}{FIM}")
    if a.contexto:
        print(f"\n{CINZA}contexto:{FIM} {a.contexto}")
    if a.texto_gerado:
        print(f"\n{CINZA}--- a IA escreveu ---{FIM}\n{a.texto_gerado}")
    if a.texto_final and a.texto_final != a.texto_gerado:
        print(f"\n{VERDE}--- eu mandei ---{FIM}\n{a.texto_final}")
    if a.motivo:
        print(f"\n{VERMELHO}motivo:{FIM} {a.motivo}")
    if a.payload:
        print(f"\n{CINZA}payload: {a.payload}{FIM}")
    return 0


async def _decidir(args: argparse.Namespace) -> int:
    rejeitar = bool(args.rejeitar)
    acao_id = await _resolver(args.rejeitar or args.aprovar)

    try:
        a = await servico.decidir(
            acao_id,
            decisao="rejeitar" if rejeitar else "aprovar",
            texto_final=args.texto,
            motivo=args.motivo,
        )
    except servico.JaDecidida as e:
        print(f"{VERMELHO}{e}{FIM}")
        return 1

    cor = COR.get(a.status, "")
    print(f"{cor}{a.status}{FIM}  {a.titulo}")
    if a.status == "editada":
        print(f"{CINZA}par de treino gravado (gerado + final){FIM}")
    return 0


async def main() -> int:
    args = _argumentos()
    try:
        if args.ver:
            return await _ver(args)
        if args.aprovar or args.rejeitar:
            return await _decidir(args)
        return await _listar(args)
    except servico.AcaoNaoEncontrada as e:
        print(f"{VERMELHO}{e}{FIM}")
        return 1
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
