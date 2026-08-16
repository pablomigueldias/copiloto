"""O que já está no Postgres também é conhecimento.

Perfil Mestre e vagas salvas moram no banco desde a F0, em JSONB — estruturado
para a aplicação ler, invisível para a busca. Este módulo os transforma em texto
indexável, fechando o ciclo que a F5 vai usar: *"o que eu já fiz que parece com
esta vaga?"* é uma busca no índice, e a resposta sai do próprio banco.

Duas escolhas que valem explicação:

**Um documento por bloco**, não um por perfil. O Perfil Mestre inteiro vira um
texto de vários milhares de caracteres onde certificações e projetos se
misturam; buscando "AWS", o trecho devolvido precisa ser *a certificação*, não
um pedaço no meio da emenda entre dois assuntos.

**Renderizado como markdown**, com heading por item. O chunker da F2.1 já sabe
quebrar por seção e guardar a trilha — reaproveitar isso é de graça, e o título
do chunk sai "Perfil Mestre > Projetos > Copiloto" sem nenhum código novo.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.conhecimento.fontes import Documento
from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.models.pessoal.vaga import Vaga
from app.db.session import get_session

# Chave que serve de título do item, na ordem em que se procura. É a diferença
# entre "### Copiloto" e "### item 3".
_TITULO_DO_ITEM = ("nome", "titulo", "cargo", "empresa", "instituicao", "curso")

# Blocos de lista do Perfil Mestre: atributo → título da seção.
_BLOCOS = {
    "habilidades": "Habilidades",
    "projetos": "Projetos",
    "experiencias": "Experiências",
    "formacao": "Formação",
    "certificacoes": "Certificações",
    "blocos_curriculo": "Blocos de currículo",
}


def _valor(v: Any) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x not in (None, ""))
    if isinstance(v, dict):
        return "; ".join(f"{k}: {_valor(x)}" for k, x in v.items() if x not in (None, ""))
    return str(v)


def _item(item: Any) -> str:
    """Um item do JSONB vira uma subseção com heading próprio."""
    if not isinstance(item, dict):
        return f"- {_valor(item)}"

    chave_titulo = next((k for k in _TITULO_DO_ITEM if item.get(k)), None)
    titulo = str(item[chave_titulo]) if chave_titulo else None
    linhas = [
        f"{k}: {_valor(v)}"
        for k, v in item.items()
        if k != chave_titulo and v not in (None, "", [], {})
    ]
    if titulo:
        return "\n".join([f"### {titulo}", *linhas])
    return "\n".join(f"- {x}" for x in linhas)


def _lista(itens: Any) -> str:
    if not isinstance(itens, list):
        return _valor(itens)
    return "\n\n".join(_item(i) for i in itens if i not in (None, "", [], {}))


def _identidade(p: PerfilMestre) -> str:
    partes = [f"# {p.nome}"]
    if p.titulo:
        partes.append(p.titulo)
    for rotulo, valor in (
        ("Resumo", p.resumo),
        ("Tom de escrita", p.tom_escrita),
        ("O que procuro", p.o_que_procuro),
        ("Contato", p.contato),
    ):
        if valor:
            partes.append(f"## {rotulo}\n{_valor(valor)}")
    return "\n\n".join(partes)


async def ler_perfil_mestre(*, fonte_tipo: str = "perfil") -> list[Documento]:
    """Um documento por bloco do perfil ativo.

    Só o perfil ativo: indexar um perfil velho faria a busca devolver fato
    verdadeiro sobre uma versão de mim que não vale mais — pior que não achar,
    porque parece certo.
    """
    async with get_session() as session:
        perfis = (
            await session.scalars(select(PerfilMestre).where(PerfilMestre.ativo.is_(True)))
        ).all()

    documentos: list[Documento] = []
    for p in perfis:
        base = {"perfil_id": str(p.id), "tags": ["perfil"]}
        blocos: list[tuple[str, str, str]] = [("identidade", "Identidade", _identidade(p))]
        blocos += [
            (attr, rotulo, f"# {rotulo}\n\n{_lista(getattr(p, attr))}")
            for attr, rotulo in _BLOCOS.items()
            if getattr(p, attr)
        ]
        documentos += [
            Documento(
                fonte_tipo=fonte_tipo,
                # `#bloco` no ref para o bloco poder ser reindexado sozinho — e
                # para um bloco esvaziado sumir do índice na varredura seguinte.
                fonte_ref=f"perfil:{p.id}#{attr}",
                titulo=f"Perfil Mestre > {rotulo}",
                conteudo=conteudo,
                metadados={**base, "bloco": attr},
            )
            for attr, rotulo, conteudo in blocos
            if conteudo.strip()
        ]
    return documentos


def _vaga_para_texto(v: Vaga) -> str:
    cabecalho = [f"# {v.titulo}"]
    ficha = [
        f"{rotulo}: {valor}"
        for rotulo, valor in (
            ("Empresa", v.empresa),
            ("Local", v.localizacao),
            ("Modelo", v.modelo),
            ("Senioridade", v.senioridade),
            ("Fonte", v.fonte),
        )
        if valor
    ]
    if ficha:
        cabecalho.append("\n".join(ficha))
    cabecalho.append(f"## Descrição\n{v.descricao}")
    if v.notas:
        cabecalho.append(f"## Notas\n{v.notas}")
    return "\n\n".join(cabecalho)


async def ler_vagas(*, fonte_tipo: str = "vaga") -> list[Documento]:
    """Cada vaga salva vira um documento — é o vocabulário do mercado (camada 3).

    Vale qualquer status, inclusive as recusadas: o que se indexa aqui é *como o
    mercado descreve o trabalho*, e isso não depende do desfecho da candidatura.
    """
    async with get_session() as session:
        vagas = (await session.scalars(select(Vaga))).all()

    return [
        Documento(
            fonte_tipo=fonte_tipo,
            fonte_ref=f"vaga:{v.id}",
            titulo=" — ".join(x for x in (v.titulo, v.empresa) if x),
            conteudo=_vaga_para_texto(v),
            metadados={
                "vaga_id": str(v.id),
                "empresa": v.empresa,
                "status": v.status,
                "link": v.link,
                "tags": ["vaga"],
            },
        )
        for v in vagas
        if v.descricao and v.descricao.strip()
    ]
