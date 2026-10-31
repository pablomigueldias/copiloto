"""Helpers das questões inéditas de BD (edital CRECI-SP 01/2026, Avança SP)."""
import sqlite3

# Ordem do gabarito por tópico: cada letra 4 vezes em 20, sem padrão visível.
SEQ = "CAEBDBDACEEBCADDCEAB"


class Sequencia:
    """Contador de gabarito compartilhado por vários tópicos pequenos de um mesmo módulo."""

    def __init__(self):
        self.i = 0


class Topico:
    def __init__(self, nome, ordem, slug, item_edital, *, materia="BD Avança SP",
                 cargo="PAS Analista de TI – Banco de Dados", sequencia=None):
        self.nome, self.ordem, self.slug, self.item = nome, ordem, slug, item_edital
        self.materia, self.cargo = materia, cargo
        self.questoes = []
        self._seq = sequencia
        self._i = 0

    def _origem(self):
        return f"Inédita (sem banca) · {self.materia} · {self.nome} · nº {len(self.questoes) + 1:02d}"

    def _proxima_letra(self):
        if self._seq is not None:
            letra = SEQ[self._seq.i % 20]
            self._seq.i += 1
            return letra
        letra = SEQ[(self._i + self.ordem * 3) % 20]
        self._i += 1
        return letra

    def mc(self, enunciado, certa, erradas, explicacao, *, formato="multipla_escolha",
           dificuldade=2, codigo=None, verificar=None, **extra):
        """Múltipla escolha: a certa vai para a letra da vez; `{G}` na explicação vira a letra.

        `extra`: `assunto` (catálogo do simulado), `texto` e `fonte_texto` (texto
        de apoio), `comando` e `linguagem`.
        """
        assert len(erradas) == 4, enunciado[:60]
        g = self._proxima_letra()
        pos = "ABCDE".index(g)
        textos = list(erradas)
        textos.insert(pos, certa)
        if verificar:
            verificar()
        self._add(formato, enunciado, textos, g, explicacao, dificuldade, codigo, **extra)

    def fixa(self, enunciado, alternativas, gabarito, explicacao, *, formato="multipla_escolha",
             afirmacoes=None, dificuldade=2, codigo=None, verificar=None, **extra):
        """Alternativas em ordem fixa (afirmações I/II/III, números em ordem)."""
        assert len(alternativas) == 5
        if verificar:
            verificar()
        self._add(formato, enunciado, alternativas, gabarito, explicacao, dificuldade, codigo,
                  afirmacoes, **extra)

    def _add(self, formato, enunciado, textos, g, explicacao, dificuldade, codigo, afirmacoes=None,
             *, assunto=None, texto=None, fonte_texto=None, comando=None, linguagem="sql"):
        q = {"formato": formato, "origem": self._origem(), "enunciado": enunciado}
        if comando:
            q["comando"] = comando
        if texto:
            q["texto_base"] = texto.strip("\n")
            if fonte_texto:
                q["texto_base_fonte"] = fonte_texto
        if codigo:
            q["codigo"], q["linguagem"] = codigo.strip("\n"), linguagem
        if afirmacoes:
            q["afirmacoes"] = afirmacoes
        if assunto:
            q["assunto"] = assunto
        q["alternativas"] = [{"letra": "ABCDE"[i], "texto": t} for i, t in enumerate(textos)]
        q["gabarito"] = g
        q["dificuldade"] = dificuldade
        q["explicacao"] = explicacao.replace("{G}", g)
        q["fonte"] = f"Edital CRECI-SP 01/2026 (Instituto Avança SP), Anexo II — {self.cargo}: {self.item}"
        assert "**" not in q["explicacao"] + enunciado, q["origem"]
        self.questoes.append(q)


# Afirmações I/II/III: alternativas canônicas.
AF3 = ["Apenas I.", "Apenas II.", "Apenas I e II.", "Apenas II e III.", "I, II e III."]
AF3b = ["Apenas I.", "Apenas III.", "Apenas I e III.", "Apenas II e III.", "I, II e III."]


# ── Banco de exemplo usado nas questões de código SQL ──
ESQUEMA = """
CREATE TABLE CLIENTE (id INTEGER PRIMARY KEY, nome VARCHAR(40), cidade VARCHAR(40));
CREATE TABLE PEDIDO  (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES CLIENTE(id), valor DECIMAL(10,2));
INSERT INTO CLIENTE VALUES (1,'Ana','Santos'),(2,'Bruno','Campinas'),(3,'Carla','Santos'),(4,'Diego','Sorocaba');
INSERT INTO PEDIDO  VALUES (10,1,100),(11,1,250),(12,2,80),(13,3,NULL),(14,3,40);
"""

TABELAS = (
    "CLIENTE\n\n| id | nome | cidade |\n|---|---|---|\n| 1 | Ana | Santos |\n| 2 | Bruno | Campinas |\n"
    "| 3 | Carla | Santos |\n| 4 | Diego | Sorocaba |\n\n"
    "PEDIDO\n\n| id | cliente_id | valor |\n|---|---|---|\n| 10 | 1 | 100 |\n| 11 | 1 | 250 |\n| 12 | 2 | 80 |\n"
    "| 13 | 3 | NULL |\n| 14 | 3 | 40 |"
)


def roda(sql):
    con = sqlite3.connect(":memory:")
    con.executescript(ESQUEMA)
    return con.execute(sql).fetchall()


def confere(sql, esperado):
    def f():
        r = roda(sql)
        assert r == esperado, (sql, r, esperado)
    return f
