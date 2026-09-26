"""Empresas: procurar na base de prospecção e trazer para o CRM (Fase 1, passo 2).

A base é o universo (25 mil estabelecimentos de saúde na capital); o CRM é quem
eu escolhi abordar. Esta tela é a ponte, e o padrão dela é o foco da D11/D13:
**clínica de psicologia com equipe** (`clinica_especialidade` com "psic" no
nome), com e-mail. Consultório isolado é o psicólogo solo, fora do foco.

Duas regras de `regras-prospeccao.md` §4 moram aqui:

- **Pessoa física só com revisão manual, uma por uma.** Trazer em lote pula
  quem é pessoa física; trazer uma só, com `confirmar_pessoa_fisica`, passa.
- **O e-mail da base ainda não é destinatário.** Ele entra no lead, mas o
  Pesquisador (passo 3) confere se a clínica o publica no próprio site antes
  de qualquer envio.

Dez por vez, não mil: o gargalo é a atenção, não a lista.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.crm import leads
from app.db.models.comercial.crm import Lead, OrigemLead, Tarefa, TipoTarefa
from app.db.models.comercial.prospeccao import (
    Canal,
    Estabelecimento,
    Identificador,
    Situacao,
    TipoCanal,
    TipoIdentificador,
)

MAX_POR_VEZ = 10
SEGMENTOS = ("clinica_especialidade", "consultorio_isolado")


@dataclass
class Linha:
    id: int
    nome: str
    segmento: str | None
    bairro: str | None
    pessoa_fisica: bool
    cnes: str | None
    emails: list[str] = field(default_factory=list)
    telefones: list[str] = field(default_factory=list)
    lead_id: int | None = None


@dataclass
class Resultado:
    trazidos: list[int] = field(default_factory=list)  # ids dos leads criados
    pulados: dict[int, str] = field(default_factory=dict)  # estabelecimento → motivo


def _nome(e: Estabelecimento) -> str:
    return (e.nome_fantasia or e.razao_social or f"Estabelecimento {e.id}").strip()


async def buscar(
    session: AsyncSession,
    *,
    termo: str = "psic",
    segmento: str | None = "clinica_especialidade",
    bairro: str | None = None,
    so_com_email: bool = True,
    incluir_no_crm: bool = True,
    limite: int = 50,
    offset: int = 0,
) -> tuple[int, list[Linha]]:
    """(total, página) de estabelecimentos ativos, com os canais e o lead, se houver."""
    filtros = [Estabelecimento.situacao == Situacao.ATIVO.value]
    if termo.strip():
        padrao = f"%{termo.strip()}%"
        filtros.append(
            or_(Estabelecimento.nome_fantasia.ilike(padrao), Estabelecimento.razao_social.ilike(padrao))
        )
    if segmento:
        filtros.append(Estabelecimento.segmento == segmento)
    if bairro and bairro.strip():
        filtros.append(Estabelecimento.bairro.ilike(f"%{bairro.strip()}%"))
    if so_com_email:
        filtros.append(
            exists().where(
                and_(Canal.estabelecimento_id == Estabelecimento.id, Canal.tipo == TipoCanal.EMAIL.value)
            )
        )
    lead_aberto = (
        select(Lead.id)
        .where(
            Lead.estabelecimento_id == Estabelecimento.id,
            Lead.estagio.in_([e.value for e in leads.ABERTOS]),
        )
        .limit(1)
        .scalar_subquery()
    )
    if not incluir_no_crm:
        filtros.append(lead_aberto.is_(None))

    total = await session.scalar(select(func.count()).select_from(Estabelecimento).where(*filtros))
    linhas = (
        await session.execute(
            select(Estabelecimento, lead_aberto.label("lead_id"))
            .where(*filtros)
            .order_by(Estabelecimento.bairro.nulls_last(), Estabelecimento.nome_fantasia)
            .limit(limite)
            .offset(offset)
        )
    ).all()
    ids = [e.id for e, _ in linhas]
    canais = (
        await session.execute(select(Canal.estabelecimento_id, Canal.tipo, Canal.valor).where(Canal.estabelecimento_id.in_(ids)))
    ).all() if ids else []
    cnes = dict(
        (
            await session.execute(
                select(Identificador.estabelecimento_id, Identificador.valor).where(
                    Identificador.estabelecimento_id.in_(ids), Identificador.tipo == TipoIdentificador.CNES.value
                )
            )
        ).all()
    ) if ids else {}

    saida: list[Linha] = []
    for e, lead_id in linhas:
        linha = Linha(
            id=e.id, nome=_nome(e), segmento=e.segmento, bairro=e.bairro,
            pessoa_fisica=e.pessoa_fisica, cnes=cnes.get(e.id), lead_id=lead_id,
        )
        for est_id, tipo, valor in canais:
            if est_id != e.id:
                continue
            if tipo == TipoCanal.EMAIL.value:
                linha.emails.append(valor)
            elif tipo in (TipoCanal.TELEFONE.value, TipoCanal.CELULAR.value):
                linha.telefones.append(valor)
        saida.append(linha)
    return total or 0, saida


async def trazer(
    session: AsyncSession,
    ids: list[int],
    *,
    confirmar_pessoa_fisica: bool = False,
    hoje: date | None = None,
) -> Resultado:
    """Cria o lead e a tarefa "pesquisar" de cada um. Pula, com o motivo, quem não pode."""
    if len(ids) > MAX_POR_VEZ:
        raise leads.CrmErro(f"no máximo {MAX_POR_VEZ} por vez")
    if confirmar_pessoa_fisica and len(ids) != 1:
        raise leads.CrmErro("pessoa física é uma por vez, com revisão (regras-prospeccao §4)")
    hoje = hoje or date.today()
    resultado = Resultado()
    for est_id in ids:
        e = await session.get(Estabelecimento, est_id)
        if e is None:
            resultado.pulados[est_id] = "não está mais na base"
            continue
        if e.pessoa_fisica and not confirmar_pessoa_fisica:
            resultado.pulados[est_id] = "pessoa física: só uma por vez, com revisão"
            continue
        canais = (
            await session.execute(
                select(Canal.tipo, Canal.valor).where(Canal.estabelecimento_id == est_id).order_by(Canal.id)
            )
        ).all()
        email = next((v for t, v in canais if t == TipoCanal.EMAIL.value), None)
        telefone = next(
            (v for t, v in canais if t in (TipoCanal.CELULAR.value, TipoCanal.TELEFONE.value)), None
        )
        site = next((v for t, v in canais if t == TipoCanal.SITE.value), None)
        if not email:
            # O e-mail frio é o canal. Sem e-mail na base (inclusive porque a
            # supressão apagou), o lead nasceria sem destinatário.
            resultado.pulados[est_id] = "sem e-mail na base"
            continue
        try:
            lead = await leads.criar(
                session, origem=OrigemLead.PROSPECCAO, nome=_nome(e), estabelecimento_id=est_id,
                email=email, telefone=telefone, site=site,
            )
        except leads.Suprimido:
            resultado.pulados[est_id] = "pediu para não ser contatado"
            continue
        except leads.JaNoCrm:
            resultado.pulados[est_id] = "já está no CRM"
            continue
        session.add(Tarefa(lead_id=lead.id, tipo=TipoTarefa.PESQUISAR.value, vence_em=hoje))
        await session.commit()
        resultado.trazidos.append(lead.id)
    return resultado
