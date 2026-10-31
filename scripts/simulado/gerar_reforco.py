"""Escreve as 5 questões de um ou mais reforços — o que o botão "Gerar reforço" dispara.

    .venv/bin/python scripts/simulado/gerar_reforco.py <reforco_id> [<reforco_id> ...]

Roda o Claude Code sem cabeça (`claude -p`), o mesmo agente que escreve o
reforço quando o Pablo diz "gera o reforço" numa conversa, com o mesmo
procedimento (`prompts/reforco-simulado.md`): lê o erro, escreve o gerador em
`scripts/simulado/reforco/`, roda, importa. A diferença é que aqui ninguém
aprova nada, e por isso as ferramentas vão travadas: ler o repositório,
escrever SÓ em `scripts/simulado/reforco/`, e rodar só o gerador e o
importador do reforço.

Quem decide se deu certo não é a resposta do modelo, é o banco: terminou e o
reforço está `pronto` → 'ok'. Qualquer outra coisa → 'erro', com o fim do log.
Até três assuntos em paralelo; mais que isso compete pela mesma máquina.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from app.db.models.estudo.simulado import Reforco  # noqa: E402
from app.db.session import dispose_engine, get_session  # noqa: E402
from app.estudo import simulado  # noqa: E402

LOGS = RAIZ / "logs" / "reforco"
PROMPT = RAIZ / "prompts" / "reforco-simulado.md"
PARALELO = 3
PRAZO_S = 25 * 60

FERRAMENTAS = [
    "Read", "Glob", "Grep",
    # Edit(...) cobre toda ferramenta que grava arquivo, Write inclusive; uma
    # regra Write(caminho) o CLI ignora para checagem de caminho.
    "Edit(scripts/simulado/reforco/**)",
    "Bash(python3 scripts/simulado/reforco/*)",
    "Bash(.venv/bin/python scripts/simulado/importar_reforco.py *)",
]


def claude_bin() -> str:
    # A API sobe por systemd/uvicorn sem o ~/.local/bin no PATH.
    return (os.environ.get("COPILOTO_CLAUDE_BIN") or shutil.which("claude")
            or str(Path.home() / ".local" / "bin" / "claude"))


def _slug(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]


def _questao(q) -> str:
    partes = []
    if q.texto_base:
        partes.append(f"Texto de apoio:\n{q.texto_base}")
    if q.codigo:
        partes.append(f"Código:\n{q.codigo}")
    if q.comando:
        partes.append(q.comando)
    partes.append(q.enunciado)
    partes += [f"{'I' * i if i < 4 else i}. {a}" for i, a in enumerate(q.afirmacoes or [], 1)]
    partes += [f"{a['letra']}) {a['texto']}" for a in (q.alternativas or [])]
    if q.explicacao:
        partes.append(f"Explicação que ele leu depois: {q.explicacao}")
    return "\n".join(partes)


def montar_prompt(insumo: dict, nome: str) -> str:
    erros = "\n\n".join(
        f"### {e['onde']} — marcou {e['marcou'] or '(em branco)'}, gabarito {e['questao'].gabarito}\n"
        f"{_questao(e['questao'])}"
        for e in insumo["erros"]
    ) or "(nenhuma questão registrada)"
    usadas = "\n".join(f"- {o}" for o in insumo["origens_ja_usadas"] if o) or "(nenhuma)"
    arquivo_py = f"scripts/simulado/reforco/s{insumo['simulado']:02d}_{nome.replace('-', '_')}.py"
    arquivo_json = f"data/estudo/reforco/simulado-{insumo['simulado']:02d}-{nome}.json"
    valores = {
        "simulado": insumo["simulado"], "materia": insumo["materia"], "assunto": insumo["assunto"],
        "rodada": insumo["rodada"], "erros": erros, "ja_usadas": usadas, "nome": nome,
        "arquivo_py": arquivo_py, "arquivo_json": arquivo_json,
    }
    texto = PROMPT.read_text(encoding="utf-8")
    return re.sub(r"\{(\w+)\}", lambda m: str(valores.get(m.group(1), m.group(0))), texto)


async def _marcar(reforco_id: uuid.UUID, **campos) -> Reforco | None:
    async with get_session() as s:
        r = await s.get(Reforco, reforco_id)
        if r is None:
            return None
        for k, v in campos.items():
            setattr(r, k, v)
        await s.commit()
        return r


async def finalizar(reforco_id: uuid.UUID, log: str) -> str:
    """Decide pelo banco, não pela resposta do modelo."""
    async with get_session() as s:
        r = await s.get(Reforco, reforco_id)
        if r is None:
            return "sumiu"
        if r.estado == "pronto":
            r.geracao_estado, r.geracao_erro = "ok", None
        else:
            r.geracao_estado = "erro"
            r.geracao_erro = (log.strip()[-1500:] or "o processo terminou sem importar as questões")
        r.geracao_pid = None
        await s.commit()
        return r.geracao_estado


async def gerar_um(reforco_id: uuid.UUID, vaga: asyncio.Semaphore) -> str:
    async with vaga:
        insumos = {i["reforco_id"]: i for i in await simulado.para_escrever()}
        insumo = insumos.get(str(reforco_id))
        if insumo is None:
            await _marcar(reforco_id, geracao_estado="erro", geracao_pid=None,
                          geracao_erro="Este reforço não está mais aguardando questões.")
            return "erro"
        nome = f"{_slug(insumo['assunto'])}-r{insumo['rodada']}"
        await _marcar(reforco_id, geracao_estado="gerando", geracao_pid=os.getpid(),
                      geracao_em=datetime.now(UTC), geracao_erro=None)
        LOGS.mkdir(parents=True, exist_ok=True)
        caminho_log = LOGS / f"{reforco_id}.log"
        cmd = [claude_bin(), "-p", montar_prompt(insumo, nome),
               "--allowedTools", *FERRAMENTAS,
               "--output-format", "text", "--no-session-persistence"]
        with caminho_log.open("w", encoding="utf-8") as saida:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, cwd=RAIZ, stdout=saida, stderr=asyncio.subprocess.STDOUT,
                    stdin=asyncio.subprocess.DEVNULL)
                await asyncio.wait_for(proc.wait(), timeout=PRAZO_S)
            except TimeoutError:
                proc.kill()
                saida.write(f"\n[passou de {PRAZO_S // 60} minutos e foi interrompido]\n")
            except FileNotFoundError:
                saida.write(f"\n[não achei o Claude Code em {cmd[0]}]\n")
        return await finalizar(reforco_id, caminho_log.read_text(encoding="utf-8", errors="replace"))


async def main(ids: list[str]) -> int:
    vaga = asyncio.Semaphore(PARALELO)
    try:
        resultados = await asyncio.gather(*(gerar_um(uuid.UUID(i), vaga) for i in ids))
    finally:
        await dispose_engine()
    for i, r in zip(ids, resultados, strict=True):
        print(f"{i}: {r}")
    return 0 if all(r == "ok" for r in resultados) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
