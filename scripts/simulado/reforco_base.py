"""O molde das questões de reforço — o mesmo `mc`/`fixa` das inéditas.

Cada simulado ganha um arquivo `scripts/simulado/reforco/sNN.py`:

    from reforco_base import Reforco
    from base import AF3, confere            # helpers das inéditas (SQL no SQLite)

    R = Reforco(simulado=1)
    t = R.assunto("Triggers", rodada=1)
    t.mc("enunciado", "certa", ["errada 1", "errada 2", "errada 3", "errada 4"],
         "explicação com {G} no lugar da letra")
    ...                                       # 5 por assunto
    R.grava()

e roda com `python3 scripts/simulado/reforco/sNN.py`, que grava
`data/estudo/reforco/simulado-NN.json` para o `importar_reforco.py`.

O gabarito gira por uma sequência só do simulado, então as 5 de um assunto não
saem com a mesma letra. Rodada 2 de um assunto entra no mesmo arquivo, com
`rodada=2`; o importador só vincula reforço que ainda espera questões.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "ineditas_bd"))
from base import Sequencia, Topico  # noqa: E402

DESTINO = RAIZ / "data" / "estudo" / "reforco"


class Reforco:
    def __init__(self, simulado: int, nome: str | None = None):
        # `nome` separa o arquivo quando cada assunto é gerado sozinho (o botão
        # da tela roda um processo por assunto, e dois escrevendo o mesmo JSON
        # se apagariam): simulado-01-triggers-r1.json.
        self.simulado = simulado
        self.nome = nome
        self._seq = Sequencia()
        self._blocos: list[tuple[str, int, Topico]] = []

    def assunto(self, nome: str, *, rodada: int = 1) -> Topico:
        t = Topico(nome, 0, "reforco", f"reforço do simulado nº {self.simulado}",
                   materia="Reforço", cargo="Reforço do simulado", sequencia=self._seq)
        self._blocos.append((nome, rodada, t))
        return t

    def grava(self) -> Path:
        reforcos = []
        for nome, rodada, t in self._blocos:
            assert len(t.questoes) == 5, f"{nome}: {len(t.questoes)} questões, o reforço tem 5"
            for q in t.questoes:
                q.pop("origem", None)  # o importador numera: simulado · assunto · rodada · nº
                q["fonte"] = f"Reforço do simulado nº {self.simulado} — escrito para o erro em {nome}"
            reforcos.append({"assunto": nome, "rodada": rodada, "questoes": t.questoes})
        DESTINO.mkdir(parents=True, exist_ok=True)
        sufixo = f"-{self.nome}" if self.nome else ""
        caminho = DESTINO / f"simulado-{self.simulado:02d}{sufixo}.json"
        conteudo = {
            "_leia_me": "Questões de REFORÇO escritas por mim (Claude) depois do simulado, sob medida para cada "
                        "assunto errado — sem banca; gabarito e explicação são meus. Importar com "
                        "scripts/simulado/importar_reforco.py.",
            "simulado": self.simulado,
            "reforcos": reforcos,
        }
        caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        letras = [q["gabarito"] for _, _, t in self._blocos for q in t.questoes]
        print(f"{caminho.relative_to(RAIZ)}: {len(reforcos)} assunto(s), {len(letras)} questões, "
              f"gabaritos {dict(sorted({x: letras.count(x) for x in letras}.items()))}")
        return caminho
