"""Candidaturas pelo terminal — colar, analisar, gerar, acompanhar.

    python scripts/vaga.py --colar                    # cola a vaga (Ctrl-D no fim)
    python scripts/vaga.py --colar --arquivo v.txt
    python scripts/vaga.py                            # lista as vagas
    python scripts/vaga.py --ver <id>
    python scripts/vaga.py --analisar <id>            # requisitos + match
    python scripts/vaga.py --gerar <id>               # currículo + PDF + fila
    python scripts/vaga.py --evento <id> enviada      # marca o que aconteceu
    python scripts/vaga.py --metricas                 # o painel
    python scripts/vaga.py --followup                 # o que está vencido

O id pode ser parcial: os 8 primeiros caracteres bastam.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import UUID

from app.candidatura import metricas as painel
from app.candidatura import servico, vagas
from app.db.models.pessoal.candidatura_evento import EVENTOS
from app.db.session import dispose_engine

VERDE, AMARELO, VERMELHO, CINZA, FIM = (
    "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"
)


def _argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Candidaturas do Copiloto.")
    p.add_argument("--colar", action="store_true", help="Lê a descrição da vaga do stdin.")
    p.add_argument("--arquivo", help="Lê a descrição de um arquivo (com --colar).")
    p.add_argument("--empresa")
    p.add_argument("--titulo")
    p.add_argument("--link")
    p.add_argument("--ver", metavar="ID")
    p.add_argument("--analisar", metavar="ID")
    p.add_argument("--gerar", metavar="ID")
    p.add_argument("--pdf", metavar="ID", help="Reimprime e abre o PDF já gerado.")
    p.add_argument("--evento", nargs=2, metavar=("ID", "EVENTO"), help=f"Um de: {', '.join(EVENTOS)}")
    p.add_argument("--metricas", action="store_true")
    p.add_argument("--followup", action="store_true")
    p.add_argument("--status", help="Filtra a lista por status.")
    return p.parse_args()


async def _resolver(parcial: str) -> UUID:
    try:
        return UUID(parcial)
    except ValueError:
        pass
    _, todas = await vagas.listar(limite=500)
    achadas = [v for v in todas if str(v.id).startswith(parcial.lower())]
    if not achadas:
        raise SystemExit(f"Nenhuma vaga começa com {parcial!r}.")
    if len(achadas) > 1:
        raise SystemExit(f"{parcial!r} é ambíguo: {len(achadas)} vagas.")
    return achadas[0].id


def _cor_score(score: int | None) -> str:
    if score is None:
        return CINZA
    return VERDE if score >= 70 else (AMARELO if score >= 45 else VERMELHO)


async def _colar(args) -> int:
    if args.arquivo:
        descricao = open(args.arquivo, encoding="utf-8").read()
    else:
        print(f"{CINZA}Cole a descrição da vaga e termine com Ctrl-D:{FIM}")
        descricao = sys.stdin.read()

    vaga = await vagas.criar(
        descricao=descricao, titulo=args.titulo, empresa=args.empresa, link=args.link
    )
    print(f"\n{VERDE}salva{FIM}  {str(vaga.id)[:8]}  {vaga.titulo}")
    print(f"{CINZA}analise com: python scripts/vaga.py --analisar {str(vaga.id)[:8]}{FIM}")
    return 0


async def _listar(args) -> int:
    total, itens = await vagas.listar(status=args.status, limite=100)
    if not itens:
        print("Nenhuma vaga. Cole a primeira com `--colar`.")
        return 0

    for v in itens:
        score = f"{v.match_score:>3}" if v.match_score is not None else "  —"
        print(
            f"{CINZA}{str(v.id)[:8]}{FIM}  {_cor_score(v.match_score)}{score}{FIM}  "
            f"{v.status:<17} {v.titulo[:45]:<45} {CINZA}{v.empresa or ''}{FIM}"
        )
    print(f"\n{total} vaga(s)")
    return 0


async def _ver(args) -> int:
    vaga = await vagas.obter(await _resolver(args.ver))
    print(f"\n{vaga.titulo}")
    print(f"{CINZA}{vaga.empresa or 'sem empresa'} · {vaga.status} · {vaga.created_at:%d/%m/%Y}{FIM}")
    if vaga.match_score is not None:
        print(f"\nmatch: {_cor_score(vaga.match_score)}{vaga.match_score}/100{FIM}")
    if vaga.match_json:
        gaps = vaga.match_json.get("gaps") or []
        if gaps:
            print(f"{VERMELHO}falta:{FIM} {', '.join(gaps)}")
    if vaga.analise_json:
        print(f"\n{CINZA}obrigatórios:{FIM} {', '.join(vaga.analise_json.get('obrigatorios') or [])}")
        print(f"{CINZA}stack:{FIM} {', '.join(vaga.analise_json.get('stack') or [])}")

    print(f"\n{CINZA}histórico:{FIM}")
    for e in await vagas.historico(vaga.id):
        print(f"  {e.ocorreu_em:%d/%m %H:%M}  {e.evento}"
              + (f" — {e.detalhe}" if e.detalhe else ""))
    return 0


async def _analisar(args) -> int:
    a = await servico.analisar(await _resolver(args.analisar), forcar=True)
    print(f"\n{_cor_score(a.match.score)}{a.match.score}/100{FIM} ({a.match.veredito})")
    for i in a.match.obrigatorios:
        marca = f"{VERDE}✓{FIM}" if i.tenho else f"{VERMELHO}✗{FIM}"
        print(f"  {marca} {i.requisito}" + (f" {CINZA}({i.evidencia}){FIM}" if i.evidencia else ""))
    if a.match.gaps:
        print(f"\n{VERMELHO}gaps:{FIM} {', '.join(a.match.gaps)}")
    return 0


async def _gerar(args) -> int:
    g = await servico.gerar_curriculo(await _resolver(args.gerar))
    c = g.curriculo
    print(f"\n{VERDE}gerado{FIM}  {c.titulo}")
    print(f"{CINZA}{g.pdf}{FIM}")
    print(f"{CINZA}abra com: python scripts/vaga.py --pdf {str(g.vaga.id)[:8]}{FIM}")
    if c.rejeitados:
        print(f"\n{AMARELO}anti-alucinação derrubou {len(c.rejeitados)}:{FIM}")
        for r in c.rejeitados:
            print(f"  · {r}")
    if c.avisos:
        print(f"\n{AMARELO}avisos de ATS:{FIM}")
        for a in c.avisos:
            print(f"  · {a}")
    if g.acao_id:
        print(f"\n{CINZA}na fila: python scripts/fila.py --ver {str(g.acao_id)[:8]}{FIM}")
    return 0


async def _pdf(args) -> int:
    """Reimprime do `curriculo_json` guardado — sem LLM, sem regerar texto."""
    import subprocess

    try:
        caminho, _ = await servico.pdf_da_vaga(await _resolver(args.pdf))
    except servico.SemCurriculo as e:
        print(f"{VERMELHO}{e}{FIM}\n{CINZA}gere com: python scripts/vaga.py --gerar {args.pdf}{FIM}")
        return 1

    print(f"{VERDE}{caminho}{FIM}")
    # `xdg-open` falha em servidor sem sessão gráfica; o caminho já foi impresso.
    subprocess.run(["xdg-open", str(caminho)], check=False, capture_output=True)
    return 0


async def _evento(args) -> int:
    ident, evento = args.evento
    e = await vagas.registrar_evento(await _resolver(ident), evento)
    print(f"{VERDE}{e.evento}{FIM} registrado")
    return 0


async def _followup(args) -> int:
    vencidas = await vagas.followup_vencido()
    if not vencidas:
        print("Nada vencido. 🎉")
        return 0
    print(f"{AMARELO}follow-up vencido:{FIM}")
    for v, dias in vencidas:
        print(f"  {CINZA}{str(v.id)[:8]}{FIM}  {dias:>3}d  {v.titulo[:50]} "
              f"{CINZA}{v.empresa or ''}{FIM}")
    return 0


async def _metricas(args) -> int:
    m = await painel.calcular()

    print(f"\n{CINZA}funil{FIM}")
    for etapa, n in m.funil.items():
        print(f"  {etapa:<12} {'█' * min(n, 40)} {n}")

    print(f"\n{CINZA}números{FIM}")
    if m.taxa_resposta is not None:
        print(f"  taxa de resposta   {m.taxa_resposta}%")
    if m.dias_ate_resposta is not None:
        print(f"  dias até resposta  {m.dias_ate_resposta}")
    if m.score_medio is not None:
        print(f"  match médio        {m.score_medio}/100")
    print(f"  follow-up vencido  {m.followup_vencido}")

    if m.paradas:
        print(f"\n{AMARELO}paradas{FIM}")
        for p in m.paradas:
            print(f"  {p['parada_ha_dias']:>3}d  {p['titulo'][:50]} ({p['status']})")

    if m.gaps_frequentes:
        print(f"\n{VERMELHO}o que o mercado pede e eu não tenho{FIM} {CINZA}(sua lista de estudo){FIM}")
        for g in m.gaps_frequentes:
            print(f"  {g['vezes']:>2}× ({g['das_vagas']:>3}%)  {g['requisito']}")
    return 0


async def main() -> int:
    args = _argumentos()
    try:
        if args.colar:
            return await _colar(args)
        if args.ver:
            return await _ver(args)
        if args.analisar:
            return await _analisar(args)
        if args.gerar:
            return await _gerar(args)
        if args.pdf:
            return await _pdf(args)
        if args.evento:
            return await _evento(args)
        if args.followup:
            return await _followup(args)
        if args.metricas:
            return await _metricas(args)
        return await _listar(args)
    except (vagas.VagaErro, Exception) as e:  # noqa: BLE001
        if isinstance(e, SystemExit):
            raise
        print(f"{VERMELHO}{type(e).__name__}: {e}{FIM}")
        return 1
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
