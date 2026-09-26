"""Fronteira do módulo comercial (D1 do bot): importa só do motor.

`app/comercial/` pode usar `app.db`, `app.config`, `app.utils` e ele mesmo.
Importar de `app.estudo`, `app.blog` etc. amarraria o comercial a um módulo que
muda por outro motivo — e o dia de separar os dois ficaria caro.
"""
from __future__ import annotations

import ast
from pathlib import Path

PERMITIDOS = ("app.db", "app.config", "app.utils", "app.comercial")
RAIZ = Path(__file__).resolve().parents[1] / "app" / "comercial"


def _imports(arquivo: Path) -> list[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    nomes = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            nomes += [a.name for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes.append(no.module)
    return nomes


def test_comercial_so_importa_do_motor():
    fora = [
        f"{arquivo.relative_to(RAIZ.parents[1])}: {nome}"
        for arquivo in RAIZ.rglob("*.py")
        for nome in _imports(arquivo)
        if nome.split(".")[0] == "app" and not nome.startswith(PERMITIDOS)
    ]
    assert not fora
