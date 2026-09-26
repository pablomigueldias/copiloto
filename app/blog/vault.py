"""Do vault à pauta: as notas marcadas `blog: ideia`, e só das pastas liberadas.

A ponte entre estudar e escrever era a memória. A convenção já existia no plano
do blog (§9.3): uma propriedade `blog: ideia | rascunho | publicado` na nota do
Obsidian. Este módulo é o que faz ela chegar à redação.

## Duas travas, e as duas precisam abrir

1. **Lista branca de pastas.** O vault é um repo **público**, mas mora no
   mesmo `Pessoal/` que `Curriculos/`, `Concurso/` e `Planos/` — que ficam fora
   do git e nunca podem virar matéria-prima de post. Lista branca e não negra
   (§10.2 do plano do blog): pasta nova criada amanhã começa bloqueada.
2. **A marca explícita.** Nota da pasta liberada sem `blog: ideia` não aparece.
   Nada é puxado por busca semântica sem a marca (§10.3 C).

A matéria-prima **não** é copiada para o post. O post guarda só o caminho
relativo em `origem`, e a geração relê a nota na hora — assim a nota pode
melhorar depois da pauta, e o campo `notas` do post continua sendo só o que eu
escrevi ali (e que nunca sai da máquina).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from sqlalchemy import select

from app.blog import servico, taxonomia
from app.config import settings
from app.conhecimento.fontes import IGNORAR, _frontmatter, _titulo
from app.db.models.blog import BlogPost
from app.db.session import get_session
from app.utils.logger import get_logger

logger = get_logger()

# Relativas à raiz do vault. As pastas de estudo moram dentro de `Pessoal/`, ao
# lado das que nunca podem sair — por isso o caminho inteiro, e não o nome solto.
LIBERADAS: tuple[str, ...] = (
    "Pessoal/Machine Learning",
    "Pessoal/Como Criar Agentes de IA",
    "Pessoal/Criar valor com IA, automação e bots",
    "Pessoal/SQL Database Specialist",
    "Pessoal/Engenharia de Software",
    "Pessoal/Arquitetura e Organização de Computadores",
    "Pessoal/Introdução à Programação e Pensamento Computacional",
    "Pessoal/Matemática",
    "Pessoal/Gestão e Governança de TI",
    "Pessoal/IoT Specialist",
    "Pessoal/_Sistema-Estudos",
    # Os registros de experimento: é daqui que saem os números medidos que
    # fecham os `{{FALTA}}` (a nota vira mais uma `origem` do post).
    "Pessoal/Laboratório de Dados",
)
# Vetadas mesmo dentro de uma pasta liberada. Redundante com a lista branca de
# propósito: se alguém liberar `Pessoal` inteiro um dia, estas continuam fora.
BLOQUEADAS: frozenset[str] = frozenset(
    {"Curriculos", "Certificados", "Concurso", "Planos", "Provas", "Livros", "_inbox", "_audio"}
)

ESTADOS_NOTA = ("ideia", "rascunho", "publicado")
_LINHA_BLOG = re.compile(r"^blog:[ \t]*\S*[ \t]*$", re.MULTILINE)


class VaultErro(servico.BlogErro):
    """Nota fora da lista branca, sem a marca, ou que não existe."""


@dataclass(slots=True)
class Candidata:
    caminho: str  # relativo ao vault, com `/`
    titulo: str
    pilar: str | None
    tags: list[str]
    palavras: int
    trecho: str
    post_id: str | None  # a pauta que já nasceu desta nota, se houver


def _raiz() -> Path:
    return settings.vault_dir


def liberada(relativo: str | PurePosixPath) -> bool:
    """A regra inteira num lugar: dentro de uma pasta liberada e fora das vetadas."""
    rel = PurePosixPath(relativo)
    if rel.is_absolute() or ".." in rel.parts or rel.suffix != ".md":
        return False
    if any(p in BLOQUEADAS or p in IGNORAR for p in rel.parts):
        return False
    texto = str(rel)
    return any(texto == p or texto.startswith(p + "/") for p in LIBERADAS)


def _pilar(frontmatter: dict) -> str | None:
    valor = frontmatter.get("pilar")
    return valor if isinstance(valor, str) and valor in taxonomia.PILARES else None


def _tags(frontmatter: dict) -> list[str]:
    bruto = frontmatter.get("tags") or []
    if isinstance(bruto, str):
        bruto = [t.strip() for t in bruto.split(",")]
    return [str(t).lstrip("#") for t in bruto if str(t).strip()]


def ler_nota(relativo: str) -> tuple[dict, str]:
    """Frontmatter e corpo de uma nota **liberada**. Recusa o resto."""
    if not liberada(relativo):
        raise VaultErro(f"`{relativo}` está fora das pastas liberadas para o blog")
    arquivo = _raiz() / relativo
    if not arquivo.is_file():
        raise VaultErro(f"`{relativo}` não existe no vault")
    return _frontmatter(arquivo.read_text(encoding="utf-8"))


async def _pautas_por_nota() -> dict[str, str]:
    """`{caminho da nota: id do post}` — para a lista dizer "já virou pauta"."""
    async with get_session() as session:
        posts = (await session.scalars(select(BlogPost))).all()
    saida: dict[str, str] = {}
    for p in posts:
        for item in p.origem or []:
            if isinstance(item, dict) and item.get("vault"):
                saida[item["vault"]] = str(p.id)
    return saida


async def candidatas() -> list[Candidata]:
    """As notas com `blog: ideia` nas pastas liberadas, a mais nova primeiro."""
    raiz = _raiz()
    if not raiz.is_dir():
        logger.warning(f"Vault não encontrado: {raiz}")
        return []

    ja = await _pautas_por_nota()
    achadas: list[tuple[float, Candidata]] = []
    for pasta in LIBERADAS:
        base = raiz / pasta
        if not base.is_dir():
            continue
        for arquivo in base.rglob("*.md"):
            relativo = arquivo.relative_to(raiz).as_posix()
            if not liberada(relativo):
                continue
            try:
                frontmatter, corpo = _frontmatter(arquivo.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, OSError):
                continue
            if str(frontmatter.get("blog", "")).strip().lower() != "ideia":
                continue
            limpo = " ".join(corpo.split())
            achadas.append(
                (
                    arquivo.stat().st_mtime,
                    Candidata(
                        caminho=relativo,
                        titulo=_titulo(frontmatter, corpo, arquivo),
                        pilar=_pilar(frontmatter),
                        tags=_tags(frontmatter),
                        palavras=len(corpo.split()),
                        trecho=limpo[:280],
                        post_id=ja.get(relativo),
                    ),
                )
            )
    return [c for _, c in sorted(achadas, key=lambda t: t[0], reverse=True)]


def marcar(relativo: str, estado: str) -> bool:
    """Troca o valor de `blog:` no frontmatter da nota. Só essa linha.

    O vault é do Obsidian e tem backup automático; reescrever o arquivo inteiro
    a partir de um parser de quatro linhas seria o jeito certo de perder uma
    propriedade que o parser não entende. Aqui muda uma linha, e só dentro do
    frontmatter.
    """
    if estado not in ESTADOS_NOTA:
        raise VaultErro(f"estado de nota inválido: {estado}")
    if not liberada(relativo):
        raise VaultErro(f"`{relativo}` está fora das pastas liberadas para o blog")
    arquivo = _raiz() / relativo
    if not arquivo.is_file():
        return False
    texto = arquivo.read_text(encoding="utf-8")
    if not texto.startswith("---"):
        return False
    fim = texto.find("\n---", 3)
    if fim < 0:
        return False
    cabeca, resto = texto[:fim], texto[fim:]
    nova, n = _LINHA_BLOG.subn(f"blog: {estado}", cabeca, count=1)
    if n == 0 or nova == cabeca:
        return False
    arquivo.write_text(nova + resto, encoding="utf-8")
    return True


async def importar(relativo: str) -> BlogPost:
    """A nota vira pauta: título, pilar e `origem`. A nota passa a `rascunho`.

    Importar duas vezes devolve a pauta que já existe — clique duplo não pode
    virar dois posts sobre o mesmo assunto.
    """
    frontmatter, corpo = ler_nota(relativo)
    if str(frontmatter.get("blog", "")).strip().lower() not in ("ideia", "rascunho"):
        raise VaultErro("só nota marcada `blog: ideia` vira pauta")

    ja = (await _pautas_por_nota()).get(relativo)
    if ja:
        from uuid import UUID

        return await servico.obter(UUID(ja))

    post = await servico.criar(
        titulo=_titulo(frontmatter, corpo, Path(relativo)),
        pilar=_pilar(frontmatter),
        origem=[{"vault": relativo}],
    )
    marcar(relativo, "rascunho")
    return post
