"""O lead: nascer, mudar de estágio, voltar depois de 90 dias.

Três regras moram aqui, e em nenhum outro lugar:

1. **Supressão vence tudo (D9).** Quem pediu para sair não vira lead de novo,
   nem trazido da base, nem digitado à mão. O e-mail e o telefone são
   conferidos contra o hash de `prospeccao_supressao` antes de gravar.
2. **Estágio anda por transição permitida.** O LLM pode sugerir; quem muda é o
   código, e cada mudança fica em `comercial_transicao` com o motivo. Pular de
   `prospect` para `proposta` não é atalho, é dado errado no painel.
3. **"Não agora" volta em 90 dias** (README §3), sozinho, a não ser que a
   pessoa tenha pedido para sair nesse meio tempo.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.prospeccao import normalizacao as n
from app.db.models.comercial.crm import Estagio, Lead, OrigemLead, Transicao
from app.db.models.comercial.prospeccao import Supressao, TipoSupressao

VOLTA_EM = timedelta(days=90)

# Para onde cada estágio pode ir. `perdido` e `ganho` são fins; `nao_agora`
# volta a `prospect` (pela data ou à mão) ou vira `perdido`.
TRANSICOES: dict[Estagio, frozenset[Estagio]] = {
    Estagio.PROSPECT: frozenset({Estagio.CONTATADO, Estagio.NAO_AGORA, Estagio.PERDIDO}),
    Estagio.CONTATADO: frozenset({Estagio.RESPONDEU, Estagio.NAO_AGORA, Estagio.PERDIDO}),
    Estagio.RESPONDEU: frozenset({Estagio.REUNIAO, Estagio.NAO_AGORA, Estagio.PERDIDO}),
    Estagio.REUNIAO: frozenset({Estagio.PROPOSTA, Estagio.NAO_AGORA, Estagio.PERDIDO}),
    Estagio.PROPOSTA: frozenset({Estagio.GANHO, Estagio.NAO_AGORA, Estagio.PERDIDO}),
    Estagio.NAO_AGORA: frozenset({Estagio.PROSPECT, Estagio.PERDIDO}),
    Estagio.GANHO: frozenset(),
    Estagio.PERDIDO: frozenset(),
}
ABERTOS = frozenset(e for e in Estagio if e not in (Estagio.GANHO, Estagio.PERDIDO))


class CrmErro(Exception):
    """Problema de uso do CRM que o chamador precisa tratar."""


class Suprimido(CrmErro):
    """O e-mail ou o telefone está na supressão: não pode virar lead."""


class JaNoCrm(CrmErro):
    """O estabelecimento já tem lead aberto."""


class TransicaoInvalida(CrmErro):
    pass


async def suprimido(session: AsyncSession, *, email: str | None, telefone: str | None) -> bool:
    """Se algum dos dois está na supressão (pelo hash, como ela guarda)."""
    alvos: list[tuple[str, str]] = []
    if email and (e := n.email(email)):
        alvos.append((TipoSupressao.EMAIL.value, n.hash_valor(e.valor)))
    if telefone and (t := n.telefone(telefone)):
        alvos.append((TipoSupressao.TELEFONE.value, n.hash_valor(t.valor)))
    for tipo, h in alvos:
        achou = await session.scalar(
            select(Supressao.id).where(Supressao.tipo == tipo, Supressao.valor_hash == h)
        )
        if achou:
            return True
    return False


async def criar(
    session: AsyncSession,
    *,
    origem: OrigemLead,
    nome: str,
    estabelecimento_id: int | None = None,
    email: str | None = None,
    telefone: str | None = None,
    site: str | None = None,
    contato_nome: str | None = None,
    cargo: str | None = None,
) -> Lead:
    if not nome.strip():
        raise CrmErro("o lead precisa de um nome")
    if await suprimido(session, email=email, telefone=telefone):
        raise Suprimido("contato na supressão: pediu para não ser contatado")
    if estabelecimento_id is not None:
        aberto = await session.scalar(
            select(Lead.id).where(
                Lead.estabelecimento_id == estabelecimento_id,
                Lead.estagio.in_([e.value for e in ABERTOS]),
            )
        )
        if aberto:
            raise JaNoCrm(f"o estabelecimento {estabelecimento_id} já está no CRM (lead {aberto})")

    e = n.email(email) if email else None
    t = n.telefone(telefone) if telefone else None
    lead = Lead(
        origem=origem.value,
        nome=nome.strip(),
        estabelecimento_id=estabelecimento_id,
        email=e.valor if e and e.valido else None,
        telefone=t.valor if t and t.valido else None,
        site=(site or "").strip() or None,
        contato_nome=(contato_nome or "").strip() or None,
        cargo=(cargo or "").strip() or None,
        estagio=Estagio.PROSPECT.value,
    )
    session.add(lead)
    await session.flush()
    session.add(Transicao(lead_id=lead.id, de=None, para=Estagio.PROSPECT.value, motivo=f"criado ({origem.value})"))
    await session.commit()
    await session.refresh(lead)
    return lead


async def mover(
    session: AsyncSession,
    lead_id: int,
    para: Estagio,
    *,
    motivo: str | None = None,
    hoje: date | None = None,
) -> Lead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise CrmErro(f"lead {lead_id} não existe")
    de = Estagio(lead.estagio)
    if para not in TRANSICOES[de]:
        raise TransicaoInvalida(f"{de.value} → {para.value} não é permitido")
    if para is Estagio.PERDIDO and not (motivo or "").strip():
        raise TransicaoInvalida("perdido precisa de motivo: é o dado que ensina o preço e a oferta")

    lead.estagio = para.value
    lead.volta_em = (hoje or date.today()) + VOLTA_EM if para is Estagio.NAO_AGORA else None
    if para is Estagio.PERDIDO:
        lead.motivo_perda = motivo.strip()
    session.add(Transicao(lead_id=lead.id, de=de.value, para=para.value, motivo=motivo))
    await session.commit()
    await session.refresh(lead)
    return lead


async def voltar_os_de_90_dias(session: AsyncSession, *, hoje: date | None = None) -> int:
    """`nao_agora` com a data vencida volta a `prospect`; suprimido vai a `perdido`."""
    hoje = hoje or date.today()
    vencidos = list(
        await session.scalars(
            select(Lead).where(Lead.estagio == Estagio.NAO_AGORA.value, Lead.volta_em <= hoje)
        )
    )
    for lead in vencidos:
        if await suprimido(session, email=lead.email, telefone=lead.telefone):
            para, motivo = Estagio.PERDIDO, "pediu para sair enquanto estava em 'não agora'"
            lead.motivo_perda = motivo
        else:
            para, motivo = Estagio.PROSPECT, "voltou depois de 90 dias"
        session.add(Transicao(lead_id=lead.id, de=lead.estagio, para=para.value, motivo=motivo))
        lead.estagio, lead.volta_em = para.value, None
    await session.commit()
    return len(vencidos)
