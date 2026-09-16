"""Importa um arquivo de questões para o banco de estudo.

    python scripts/importar_questoes.py data/estudo/logica-proposicional.json

Idempotente pela **origem**: cada questão de prova traz "banca · concurso ano ·
cargo · item N", e essa string é única no mundo. Rodar de novo atualiza o
conteúdo da questão e **não toca no agendamento** — que é a razão de agenda e
questão serem tabelas separadas. Um gabarito alterado pela banca entra sem
apagar o histórico de quem já respondeu.

Questão importada nasce vencendo hoje: cadastrar e só ver na tela semana que
vem é o jeito mais rápido de parar de cadastrar.

A `banca` do arquivo vira linha em `estudo_banca` e é por ela que eu pauso um
concurso inteiro sem apagar nada. Banca nova entra **ativa**: importar é dizer
"vou estudar isto".
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from sqlalchemy import select

from app.config import BASE_DIR
from app.db.models.estudo.agenda import Agenda
from app.db.models.estudo.questao import (
    FORMATOS,
    IMAGENS_DIR,
    Banca,
    Modulo,
    Questao,
    Topico,
)
from app.db.session import dispose_engine, get_session
from app.estudo import agendamento, servico

CAMPOS = (
    "formato", "comando", "enunciado", "texto_base", "texto_base_fonte",
    "codigo", "linguagem", "alternativas", "afirmacoes", "gabarito",
    "explicacao", "origem", "fonte", "dificuldade", "imagem", "imagem_alt",
)


def _valida(q: dict, i: int) -> None:
    if q["formato"] not in FORMATOS:
        raise SystemExit(f"questão {i}: formato '{q['formato']}' desconhecido")
    if not q.get("origem"):
        raise SystemExit(
            f"questão {i}: sem `origem`. É ela que torna o import idempotente — "
            "e é o que me deixa conferir o gabarito no PDF quando ele parecer errado."
        )
    # A `origem` viaja no payload da fila, junto com a questão que eu estou
    # respondendo. O `gabarito` é omitido dali de propósito; escrever a resposta
    # dentro da origem seria entregá-la pelo DevTools antes de eu responder.
    if re.search(r"gabarito\s*[:=]", q["origem"], re.IGNORECASE):
        raise SystemExit(
            f"questão {i}: a `origem` não pode conter o gabarito — ela vai para a "
            "tela junto com a questão. Identifique o documento e pare aí:\n"
            f"  {q['origem']}"
        )
    # A figura tem de estar em disco **antes** de a questão entrar no banco.
    # Falhar aqui custa uma linha de erro; falhar na tela custa uma questão
    # impossível ("que topologia é a da imagem?" sem imagem) no meio de uma
    # sessão cronometrada, quando não há nada a fazer a respeito.
    if q.get("imagem"):
        if q["imagem"].startswith(("http://", "https://", "data:")):
            raise SystemExit(
                f"questão {i}: `imagem` é nome de arquivo em {IMAGENS_DIR}/, não URL:\n"
                f"  {q['imagem'][:80]}"
            )
        if not (BASE_DIR / IMAGENS_DIR / q["imagem"]).is_file():
            raise SystemExit(
                f"questão {i}: a imagem '{q['imagem']}' não existe em {IMAGENS_DIR}/"
            )
        if not q.get("imagem_alt"):
            raise SystemExit(
                f"questão {i}: imagem sem `imagem_alt`. A descrição é o que sobra "
                "quando o arquivo se perde — e é exatamente a questão que depende "
                "dela que fica impossível sem."
            )
    elif q.get("imagem_alt"):
        # `imagem_alt` sozinha é o caso da figura que a prova tinha e eu não
        # consegui recuperar. A tela desenha a descrição no lugar da figura e
        # diz que ela é minha. O que **não** se faz é colar a descrição no
        # enunciado: a banca escreveu "analise a imagem a seguir", e reescrever
        # o enunciado dela é a mesma falta de inventar explicação em nome dela.
        if "imagem" in q["enunciado"].lower() and "prova mostra" in q["enunciado"].lower():
            raise SystemExit(
                f"questão {i}: a descrição da figura está dentro do enunciado. "
                "Ela vai em `imagem_alt`; o enunciado fica como a banca escreveu."
            )

    if q["formato"] == "certo_errado":
        if q["gabarito"] not in ("C", "E"):
            raise SystemExit(f"questão {i}: gabarito '{q['gabarito']}' fora de ('C', 'E')")
    elif q["formato"] != "flashcard":
        # Cinco alternativas é o padrão de Cespe, Quadrix e FCC, mas não é lei:
        # o IBFC aplica prova de quatro. O que a checagem existe para pegar é
        # transcrição truncada — três ou menos não é banca, é erro de digitação.
        letras = [a["letra"] for a in q.get("alternativas", [])]
        if len(letras) not in (4, 5):
            raise SystemExit(
                f"questão {i}: {len(letras)} alternativa(s). Prova de concurso tem quatro ou "
                "cinco — a menos que a transcrição tenha ficado pela metade."
            )
        if q["gabarito"] not in letras:
            raise SystemExit(
                f"questão {i}: gabarito '{q['gabarito']}' não é nenhuma das alternativas {letras}"
            )


async def _importar(caminho: Path) -> int:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    questoes = dados["questoes"]
    for i, q in enumerate(questoes, 1):
        _valida(q, i)

    hoje = servico.hoje()
    novas = atualizadas = 0

    async with get_session() as session:
        # A banca é opcional: questão inédita não tem uma, e o acervo antigo
        # foi importado antes de esta tabela existir. Quando vem, ela nasce
        # ativa — importar um arquivo é dizer que eu vou estudar aquilo.
        banca = None
        if nome_banca := (dados.get("banca") or "").strip():
            banca = await session.scalar(
                select(Banca).where(Banca.nome == nome_banca)
            )
            if banca is None:
                banca = Banca(nome=nome_banca, ativa=True, ordem=0)
                session.add(banca)
                await session.flush()

        # `ordem` é reaplicada a cada import, e nome não. O nome no banco pode
        # ter sido corrigido pela tela e o JSON não saberia; a ordem, não — ela
        # só existe para posicionar o card, e quem decide a posição é o arquivo.
        # Sem isto, reordenar a tela exigia SQL na mão.
        m = dados["modulo"]
        modulo = await session.scalar(select(Modulo).where(Modulo.nome == m["nome"]))
        if modulo is None:
            modulo = Modulo(nome=m["nome"], trilha=m.get("trilha", "concurso"), ordem=m.get("ordem", 0))
            session.add(modulo)
            await session.flush()
        elif "ordem" in m:
            modulo.ordem = m["ordem"]

        t = dados["topico"]
        topico = await session.scalar(
            select(Topico).where(Topico.modulo_id == modulo.id, Topico.nome == t["nome"])
        )
        if topico is None:
            topico = Topico(modulo_id=modulo.id, nome=t["nome"], ordem=t.get("ordem", 0))
            session.add(topico)
            await session.flush()
        elif "ordem" in t:
            topico.ordem = t["ordem"]

        for q in questoes:
            campos = {k: q.get(k) for k in CAMPOS if k in q}
            campos.setdefault("alternativas", [])
            campos.setdefault("afirmacoes", [])
            campos.setdefault("dificuldade", 2)

            existente = await session.scalar(
                select(Questao).where(Questao.origem == q["origem"])
            )
            if existente is not None:
                for k, v in campos.items():
                    setattr(existente, k, v)
                existente.topico_id = topico.id
                if banca is not None:
                    existente.banca_id = banca.id
                atualizadas += 1
                continue

            questao = Questao(
                topico_id=topico.id,
                banca_id=banca.id if banca is not None else None,
                **campos,
            )
            session.add(questao)
            await session.flush()
            e = agendamento.inicial(hoje)
            session.add(
                Agenda(
                    questao_id=questao.id,
                    proxima_em=e.proxima_em,
                    intervalo_dias=e.intervalo_dias,
                    acertos_seguidos=e.acertos_seguidos,
                    total_acertos=e.total_acertos,
                    total_erros=e.total_erros,
                    estado=e.estado,
                )
            )
            novas += 1

        await session.commit()

    etiqueta = f"{modulo.nome} / {topico.nome}"
    if banca is not None:
        etiqueta += f" [{banca.nome}{'' if banca.ativa else ' — pausada'}]"
    print(f"{etiqueta}: {novas} nova(s), {atualizadas} atualizada(s).")
    if atualizadas:
        print("Agendamento preservado — conteúdo e desempenho moram em tabelas diferentes.")
    return 0


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    caminho = Path(sys.argv[1])
    if not caminho.is_file():
        print(f"Arquivo não encontrado: {caminho}")
        return 2
    try:
        return await _importar(caminho)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
