"""O Perfil Mestre visto pelos agentes: fatos, e a lista do que é verdade.

Duas responsabilidades:

1. **Carregar** o perfil ativo — a fonte factual de tudo que o sistema escreve
   sobre o Pablo.
2. **Listar as entidades verdadeiras** — cada tecnologia, projeto, empresa e
   certificação que realmente existe. É a lista branca da regra
   anti-alucinação: o que não está aqui, o gerador não pode escrever.

A terceira camada da defesa (§2 de `docs/fase05.md`) depende inteiramente
disto. Prompt pedindo "não invente" reduz a frequência; só a verificação contra
esta lista dá garantia — e um 4B vai querer acrescentar "Kubernetes" porque
combina com o resto.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import select

from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.session import get_session

# Palavra que aparece em qualquer texto e não identifica competência nenhuma.
# Sem isto, "experiência" entraria na lista branca e liberaria qualquer frase.
RUIDO = {
    "e", "de", "da", "do", "com", "em", "para", "por", "the", "and", "of",
    "experiência", "experiencia", "conhecimento", "avançado", "avancado",
    "intermediário", "intermediario", "básico", "basico", "anos", "ano",
}

# Nomes diferentes para a mesma coisa. Curta de propósito: cada linha é uma
# afirmação de equivalência, e errar aqui faz o sistema alegar o que não tem.
SINONIMOS: dict[str, str] = {
    "postgres": "postgresql",
    "pg": "postgresql",
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "node": "nodejs",
    "rest": "api rest",
    "restful": "api rest",
    "apis rest": "api rest",
    "sqlalchemy 2.0": "sqlalchemy",
    "sqlalchemy 2.0 async": "sqlalchemy",
    "next": "nextjs",
    "next.js": "nextjs",
    "react.js": "react",
    "vue.js": "vue",
    "ci/cd": "cicd",
    "llm": "llms",
    "large language models": "llms",
    "ia generativa": "llms",
    "gen ai": "llms",
    "genai": "llms",
    "rag": "rag",
    "banco vetorial": "pgvector",
    "bancos vetoriais": "pgvector",
    "docker compose": "docker",
    "containers": "docker",
    "containerização": "docker",
    "git e versionamento": "git",
    "controle de versão": "git",
    "testes automatizados": "pytest",
    "sql avançado": "sql",
    "bancos relacionais": "sql",
    "banco de dados relacional": "sql",
}


def normalizar(texto: str) -> str:
    """Minúsculo, sem acento, sem pontuação — e com o sinônimo resolvido."""
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9+#./ -]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return SINONIMOS.get(t, t)


# Detectar "tecnologia inventada" é caçar falso negativo sem produzir falso
# positivo — e o falso positivo é o pior dos dois: derruba bullet honesto e o
# currículo fica pobre sem ninguém entender por quê.
#
# A regra: um termo só é candidato a tecnologia se **parece** tecnologia
# (símbolo, dígito, sigla, camelCase) ou se está capitalizado **no meio da
# frase**. Palavra capitalizada que abre frase é português — "Desenvolvi",
# "Indexei", "Reduzi" — e não pode virar acusação de invenção.

_FIM_DE_FRASE = re.compile(r"[.!?\n;]")
_TOKEN = re.compile(r"[A-Za-zÀ-ÿ][\wÀ-ÿ.+#/-]*")

# Genérico demais para ser prova de nada: aparece em qualquer currículo de
# qualquer pessoa, e exigir que esteja no perfil derrubaria texto honesto.
_NAO_E_TECNOLOGIA = {
    "api", "apis", "api rest", "rest", "restful", "etl", "crud", "mvp", "poc",
    "ci", "cd", "cicd", "sql", "http", "https", "json", "xml", "csv", "ux", "ui",
    "pipeline", "pipelines", "backend", "frontend", "full-stack", "fullstack",
    "deploy", "dados", "sistema", "sistemas", "projeto", "projetos", "software",
    "plataforma", "producao", "empresa", "equipe", "cliente", "clientes",
    "testes", "teste", "codigo", "web", "app", "apps", "banco", "bancos",
    "linguagens", "frameworks", "ferramentas", "integracoes", "seguranca",
    "automacao", "infraestrutura", "devops", "cloud", "nuvem",
}



def _tem_forma_de_tecnologia(token: str) -> bool:
    """`Next.js`, `C#`, `CI/CD`, `scikit-learn`, `PostgreSQL`, `AWS` — sim.

    `Desenvolvi`, `Reduzi`, `1.773` — não.
    """
    miolo = token.strip(".,;:")
    if not miolo or not any(c.isalpha() for c in miolo):
        return False  # "1.773" é número, não tecnologia
    if any(c in miolo for c in ".+#/-"):
        return True
    if any(c.isdigit() for c in miolo):
        return True
    if miolo.isupper() and len(miolo) >= 2:
        return True
    # camelCase / PascalCase interno: PostgreSQL, FastAPI, JavaScript.
    return miolo[:1].isupper() and any(c.isupper() for c in miolo[1:])


def tecnologias_citadas(texto: str, *, generoso: bool = False) -> set[str]:
    """Termos com cara de tecnologia, ignorando o português em volta.

    `generoso=True` aceita também a palavra capitalizada que abre a frase. É o
    modo de **ler o perfil**, onde tudo é verdade e incluir demais só torna a
    lista branca mais permissiva. Ao **verificar** texto gerado vale o contrário:
    a palavra que abre frase é português ("Desenvolvi", "Reduzi") e acusá-la de
    invenção derrubaria bullet honesto.
    """
    achados: set[str] = set()

    for frase in _FIM_DE_FRASE.split(texto):
        tokens = _TOKEN.findall(frase.strip())
        for i, bruto in enumerate(tokens):
            # Primeira palavra da frase é capitalizada por gramática, não por
            # ser nome de produto.
            inicio = i == 0 and not generoso
            if not _tem_forma_de_tecnologia(bruto) and (inicio or not bruto[:1].isupper()):
                continue

            base = bruto.strip(".,;:").lower()
            n = normalizar(bruto)
            if not n or len(n) < 2:
                continue
            if base in _NAO_E_TECNOLOGIA or n in _NAO_E_TECNOLOGIA:
                continue
            achados.add(n)
    return achados



@dataclass(slots=True)
class Fatos:
    """O perfil, pronto para o gerador consumir."""

    perfil: PerfilMestre
    tecnologias: set[str] = field(default_factory=set)   # normalizadas
    entidades: set[str] = field(default_factory=set)     # tudo que é verdade
    rotulos: dict[str, str] = field(default_factory=dict)  # normalizado → como escrever

    @property
    def projetos(self) -> list[dict]:
        return list(self.perfil.projetos or [])

    @property
    def experiencias(self) -> list[dict]:
        return list(self.perfil.experiencias or [])

    @property
    def habilidades(self) -> list[dict]:
        return list(self.perfil.habilidades or [])

    @property
    def certificacoes(self) -> list[dict]:
        return list(self.perfil.certificacoes or [])

    def conheco(self, termo: str) -> bool:
        """O termo está no perfil — exato, por sinônimo ou como parte de um item?"""
        n = normalizar(termo)
        if not n or n in RUIDO:
            return False
        if n in self.entidades:
            return True
        # "3+ anos com Python" contém "python"; "Python" contém "python".
        palavras = [p for p in n.split() if p not in RUIDO and len(p) > 1]
        return any(p in self.entidades for p in palavras) or any(
            e in n for e in self.entidades if len(e) > 3
        )

    def rotulo(self, termo: str) -> str:
        """Como escrever este termo no currículo (do jeito que está no perfil)."""
        return self.rotulos.get(normalizar(termo), termo)


def _guardar_do_texto(fatos: Fatos, texto: str | None) -> None:
    """Tecnologia citada numa descrição do perfil também é verdade.

    A experiência diz "manutenção do site em React e Next.js": React e Next.js
    são fatos meus, e o gerador pode citá-los. Sem isto a verificação derrubaria
    bullet honesto — falso positivo, que é o erro mais caro dos dois.
    """
    for termo in tecnologias_citadas(texto or "", generoso=True):
        if termo not in RUIDO:
            fatos.entidades.add(termo)
            fatos.tecnologias.add(termo)


def _guardar(fatos: Fatos, bruto: str | None, *, tecnologia: bool = False) -> None:
    if not bruto:
        return
    n = normalizar(bruto)
    if not n or n in RUIDO:
        return
    fatos.entidades.add(n)
    fatos.rotulos.setdefault(n, str(bruto).strip())
    if tecnologia:
        fatos.tecnologias.add(n)


def montar_fatos(perfil: PerfilMestre) -> Fatos:
    """Varre o perfil e monta a lista branca."""
    fatos = Fatos(perfil=perfil)

    for h in perfil.habilidades or []:
        _guardar(fatos, h.get("nome"), tecnologia=True)
    for p in perfil.projetos or []:
        _guardar(fatos, p.get("nome"))
        for t in p.get("stack") or []:
            _guardar(fatos, t, tecnologia=True)
        _guardar_do_texto(fatos, p.get("descricao"))
        _guardar_do_texto(fatos, p.get("prova"))
    for e in perfil.experiencias or []:
        _guardar(fatos, e.get("empresa"))
        _guardar(fatos, e.get("cargo"))
        _guardar_do_texto(fatos, e.get("descricao"))
    for c in perfil.certificacoes or []:
        _guardar(fatos, c.get("nome"))
        _guardar(fatos, c.get("tema"), tecnologia=True)
        _guardar(fatos, c.get("instituicao"))
    for f in perfil.formacao or []:
        _guardar(fatos, f.get("instituicao"))
        _guardar(fatos, f.get("curso"))
    _guardar_do_texto(fatos, perfil.resumo)
    for bloco in perfil.blocos_curriculo or []:
        _guardar_do_texto(fatos, bloco.get("conteudo") if isinstance(bloco, dict) else None)

    return fatos


class PerfilAusente(Exception):
    """Sem Perfil Mestre não há currículo — e nenhum modelo preenche isso."""


async def carregar() -> Fatos:
    async with get_session() as session:
        perfil = await session.scalar(
            select(PerfilMestre).where(PerfilMestre.ativo.is_(True)).order_by(
                PerfilMestre.created_at
            )
        )
    if perfil is None:
        raise PerfilAusente(
            "Nenhum Perfil Mestre ativo. Rode `python scripts/importar_perfil.py`."
        )
    return montar_fatos(perfil)
