"""Conserta os exemplos de estilo que foram gravados com a tarefa errada.

    python scripts/reparar_exemplos.py            # mostra o que faria
    python scripts/reparar_exemplos.py --aplicar

## O que aconteceu

`exemplos.registrar` gravava `tarefa = acao.tipo` — `"curriculo"` para as ações
de currículo. Mas `app/candidatura/curriculo.py` pede
`exemplos_para("bullet_curriculo", ...)`. **Nomes diferentes para a mesma
coisa**: cada currículo corrigido e aprovado ia para o banco e nunca era lido de
volta. O sistema parecia não aprender porque, de fato, não aprendia.

Consertado na origem (`exemplos.TAREFA_DO_TIPO`), mas os exemplos que já
existem continuam com o nome velho — e são justamente as correções que mais
valem, porque foram feitas à mão. Este script os traduz.

Também **reextrai os bullets**: os exemplos antigos guardavam o currículo
inteiro (2.000 caracteres, com contato e formação), e o few-shot que os consome
pede bullets. Ver `exemplos._texto_do_exemplo`.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.db.models.acao_pendente import AcaoPendente
from app.db.models.exemplo_estilo import ExemploEstilo
from app.db.session import dispose_engine, get_session
from app.fila.exemplos import TAREFA_DO_TIPO, _texto_do_exemplo

VERDE, AMARELO, CINZA, NEGRITO, FIM = "\033[32m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"


async def reparar(*, aplicar: bool) -> int:
    async with get_session() as session:
        exemplos = list(
            (
                await session.scalars(
                    select(ExemploEstilo).where(ExemploEstilo.tarefa.in_(TAREFA_DO_TIPO))
                )
            ).all()
        )
        if not exemplos:
            print(f"{VERDE}Nada a reparar — nenhum exemplo com tarefa antiga.{FIM}")
            return 0

        print(f"{NEGRITO}{len(exemplos)} exemplo(s) com a tarefa antiga{FIM}\n")
        mudados = 0

        for e in exemplos:
            nova = TAREFA_DO_TIPO[e.tarefa]
            texto = e.texto

            # Reextrai do texto original da ação quando ela ainda existe: é a
            # fonte, e o `texto` guardado já pode ter sido cortado.
            if e.acao_id:
                acao = await session.get(AcaoPendente, e.acao_id)
                if acao is not None:
                    texto = _texto_do_exemplo(acao) or e.texto

            print(f"  {e.tarefa} → {VERDE}{nova}{FIM}   {CINZA}{len(e.texto)} → {len(texto)} chars{FIM}")
            print(f"    {CINZA}{(texto.splitlines() or [''])[0][:88]}{FIM}")

            if aplicar:
                e.tarefa = nova
                if texto != e.texto:
                    e.texto = texto
                    # O embedding é do contexto, não do texto — não precisa refazer.
                mudados += 1

        if aplicar:
            await session.commit()
            print(f"\n{VERDE}{mudados} exemplo(s) reparados.{FIM}")
            print(f"{CINZA}O próximo currículo gerado já usa a sua voz corrigida.{FIM}")
        else:
            print(f"\n{AMARELO}Nada foi gravado. Rode com --aplicar.{FIM}")
    return 0


async def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--aplicar", action="store_true", help="Grava as mudanças.")
    args = p.parse_args()
    try:
        return await reparar(aplicar=args.aplicar)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
