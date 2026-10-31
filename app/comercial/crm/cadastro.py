"""O cadastro do CRM: empresas, contatos, negócios e atividades, com CRUD.

O CRM do prospector ensinou o formato que funciona no dia a dia: uma tabela por
entidade, editável no lugar, e uma ficha lateral que mostra o registro e tudo o
que está ligado a ele, com um clique para ir de um para o outro. A regra mora
aqui; `app/api/routers/comercial.py` é só a porta.

O negócio é o `comercial_lead` (migration 0015): a conversa que anda pelo funil,
da empresa, com um contato dela. A atividade é a `comercial_tarefa`.

O que o CRUD não pode furar:

- **Supressão vence tudo (D9)**, também no cadastro à mão: contato com e-mail
  ou telefone suprimido não nasce, nem recebe esse dado numa edição.
- **Estágio só muda por `leads.mover`**, com a transição registrada. A edição
  genérica não conhece o campo `estagio`.
- **Negócio que já recebeu contato não se apaga**: vai para `perdido`. Apagar
  deixaria a clínica voltar da base como nova e receber outro e-mail 1, o
  terceiro contato que a regra §2 proíbe.
- **Empresa com negócio não se apaga**: os negócios primeiro.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.crm import leads
from app.comercial.prospeccao import normalizacao as n
from app.db.models.acao_pendente import AcaoPendente
from app.db.models.comercial.crm import (
    Canal,
    Contato,
    Direcao,
    Empresa,
    Estagio,
    Interacao,
    Lead,
    OrigemLead,
    StatusEmpresa,
    Tarefa,
    TipoTarefa,
    Transicao,
)
from app.db.models.comercial.prospeccao import (
    Estabelecimento,
    Identificador,
    TipoIdentificador,
)

TIPOS = ("empresa", "contato", "negocio", "atividade")


class NaoAchei(leads.CrmErro):
    pass


class NaoPode(leads.CrmErro):
    """O pedido é válido, mas o estado do registro não deixa (409)."""


# ── rótulos e opções ─────────────────────────────────────────────────────────

ESTAGIOS = {
    "prospect": "prospect",
    "contatado": "contatado",
    "respondeu": "respondeu",
    "reuniao": "reunião",
    "proposta": "proposta",
    "ganho": "ganho",
    "nao_agora": "não agora",
    "perdido": "perdido",
}
STATUS_EMPRESA = {
    "prospect": "prospect",
    "cliente": "cliente",
    "parceiro": "parceiro",
    "inativa": "inativa",
}
ORIGENS = {
    "prospeccao": "base de prospecção",
    "indicacao": "indicação",
    "site": "site",
    "whatsapp": "WhatsApp",
    "newsletter": "newsletter",
}
TIPOS_TAREFA = {
    "ligar": "ligar",
    "reuniao": "reunião",
    "outro": "outro",
    "pesquisar": "pesquisar",
    "escrever_email": "escrever o e-mail",
    "enviar_email": "enviar o e-mail",
    "lembrete": "lembrete",
    "linkedin": "LinkedIn",
    "responder": "responder",
    "marcar_raiox": "marcar o raio-x",
}
CANAIS = {
    "nota": "nota",
    "email": "e-mail",
    "whatsapp": "WhatsApp",
    "linkedin": "LinkedIn",
    "reuniao": "reunião",
}


@dataclass(frozen=True)
class Campo:
    """Um campo editável: como aparece, e como o valor que chega vira coluna."""

    rotulo: str
    tipo: str  # texto | obrigatorio | longo | email | telefone | numero | data | sim_nao | opcao | uf | ref
    opcoes: dict[str, str] = field(default_factory=dict)


CAMPOS: dict[str, dict[str, Campo]] = {
    "empresa": {
        "nome": Campo("Nome", "obrigatorio"),
        "status": Campo("Status", "opcao", STATUS_EMPRESA),
        "segmento": Campo("Segmento", "texto"),
        "razao_social": Campo("Razão social", "texto"),
        "cnpj": Campo("CNPJ", "texto"),
        "site": Campo("Site", "texto"),
        "email": Campo("E-mail", "email"),
        "telefone": Campo("Telefone", "telefone"),
        "instagram": Campo("Instagram", "texto"),
        "bairro": Campo("Bairro", "texto"),
        "cidade": Campo("Cidade", "texto"),
        "uf": Campo("UF", "uf"),
        "notas": Campo("Notas", "longo"),
    },
    "contato": {
        "nome": Campo("Nome", "obrigatorio"),
        "cargo": Campo("Cargo", "texto"),
        "decisor": Campo("Decisor", "sim_nao"),
        "email": Campo("E-mail", "email"),
        "telefone": Campo("Telefone", "telefone"),
        "linkedin": Campo("LinkedIn", "texto"),
        "empresa_id": Campo("Empresa", "ref"),
        "notas": Campo("Notas", "longo"),
    },
    "negocio": {
        "nome": Campo("Nome", "obrigatorio"),
        "origem": Campo("Origem", "opcao", ORIGENS),
        "valor_estimado": Campo("Valor estimado", "numero"),
        "proxima_acao": Campo("Próxima ação", "texto"),
        "proxima_em": Campo("Quando", "data"),
        "empresa_id": Campo("Empresa", "ref"),
        "contato_id": Campo("Contato", "ref"),
        "notas": Campo("Notas", "longo"),
    },
    "atividade": {
        "tipo": Campo("Tipo", "opcao", TIPOS_TAREFA),
        "descricao": Campo("Descrição", "texto"),
        "vence_em": Campo("Vence em", "data"),
        "feita": Campo("Feita", "sim_nao"),
        "lead_id": Campo("Negócio", "ref"),
    },
}


def _texto(v: Any) -> str | None:
    return None if v is None or not str(v).strip() else str(v).strip()


def _coagir(nome: str, c: Campo, v: Any) -> Any:
    """O valor que chegou do formulário ou da célula, pronto para a coluna."""
    if c.tipo == "sim_nao":
        return bool(v)
    t = _texto(v)
    if c.tipo == "obrigatorio":
        if t is None:
            raise leads.CrmErro(f"{c.rotulo.lower()} não pode ficar vazio")
        return t
    if t is None:
        if nome == "vence_em":
            raise leads.CrmErro("a atividade precisa de data")
        return None
    match c.tipo:
        case "texto" | "longo":
            return t
        case "email":
            e = n.email(t)
            if not e or not e.valido:
                raise leads.CrmErro(f"e-mail inválido: {t}")
            return e.valor
        case "telefone":
            tel = n.telefone(t, ddd="11")
            if not tel or not tel.valido:
                raise leads.CrmErro(f"telefone inválido: {t}")
            return tel.valor
        case "numero":
            try:
                return Decimal(t.replace(".", "").replace(",", ".") if "," in t else t)
            except InvalidOperation as e:
                raise leads.CrmErro(f"{c.rotulo.lower()}: número inválido") from e
        case "data":
            try:
                return date.fromisoformat(t[:10])
            except ValueError as e:
                raise leads.CrmErro(f"{c.rotulo.lower()}: data inválida") from e
        case "opcao":
            if t not in c.opcoes:
                raise leads.CrmErro(f"{c.rotulo.lower()}: '{t}' não é uma opção")
            return t
        case "uf":
            if len(t) != 2 or not t.isalpha():
                raise leads.CrmErro("UF tem duas letras")
            return t.upper()
        case "ref":
            try:
                return int(t)
            except ValueError as e:
                raise leads.CrmErro(f"{c.rotulo.lower()}: referência inválida") from e
    raise leads.CrmErro(f"tipo de campo desconhecido: {c.tipo}")


async def _pegar(session: AsyncSession, modelo: type, id_: int, rotulo: str):
    obj = await session.get(modelo, id_)
    if obj is None:
        raise NaoAchei(f"{rotulo} {id_} não existe")
    return obj


_MODELO = {"empresa": Empresa, "contato": Contato, "negocio": Lead, "atividade": Tarefa}
_ROTULO = {"empresa": "empresa", "contato": "contato", "negocio": "negócio", "atividade": "atividade"}


async def _aplicar(session: AsyncSession, tipo: str, obj: Any, campos: dict[str, Any]) -> None:
    """Valida e grava `campos` em `obj`. Nada é gravado se um campo não passar."""
    permitidos = CAMPOS[tipo]
    fora = [c for c in campos if c not in permitidos]
    if fora:
        raise leads.CrmErro(f"campo que não se edita aqui: {', '.join(fora)}")
    valores = {nome: _coagir(nome, permitidos[nome], v) for nome, v in campos.items()}

    # Supressão: o dado de quem pediu para sair não entra por edição.
    if tipo in ("contato", "empresa") and ("email" in valores or "telefone" in valores):
        if await leads.suprimido(session, email=valores.get("email"), telefone=valores.get("telefone")):
            raise leads.Suprimido("contato na supressão: pediu para não ser contatado")

    if valores.get("empresa_id") is not None:
        await _pegar(session, Empresa, valores["empresa_id"], "empresa")
    if valores.get("contato_id") is not None:
        contato = await _pegar(session, Contato, valores["contato_id"], "contato")
        empresa_id = valores.get("empresa_id", getattr(obj, "empresa_id", None))
        if contato.empresa_id and empresa_id and contato.empresa_id != empresa_id:
            raise leads.CrmErro(f"{contato.nome} é contato de outra empresa")
        if contato.empresa_id and not empresa_id:
            valores["empresa_id"] = contato.empresa_id
    if valores.get("lead_id") is not None:
        await _pegar(session, Lead, valores["lead_id"], "negócio")
    if tipo == "atividade" and "lead_id" in valores and valores["lead_id"] is None:
        raise leads.CrmErro("a atividade é de um negócio")

    for nome, v in valores.items():
        if nome == "feita":
            obj.feita_em = (obj.feita_em or datetime.now(UTC)) if v else None
        else:
            setattr(obj, nome, v)


# ── criar, editar, excluir ───────────────────────────────────────────────────


async def criar(session: AsyncSession, tipo: str, campos: dict[str, Any], *, hoje: date | None = None) -> int:
    if tipo == "empresa":
        obj: Any = Empresa(status=StatusEmpresa.PROSPECT.value)
        await _aplicar(session, tipo, obj, campos)
    elif tipo == "contato":
        obj = Contato()
        await _aplicar(session, tipo, obj, campos)
    elif tipo == "atividade":
        obj = Tarefa(tipo=TipoTarefa.OUTRO.value, vence_em=hoje or date.today())
        await _aplicar(session, tipo, obj, {"vence_em": (hoje or date.today()).isoformat(), **campos})
        if obj.lead_id is None:
            raise leads.CrmErro("a atividade é de um negócio")
    elif tipo == "negocio":
        return await _criar_negocio(session, campos)
    else:
        raise NaoAchei(f"tipo desconhecido: {tipo}")
    session.add(obj)
    await session.commit()
    return obj.id


async def _criar_negocio(session: AsyncSession, campos: dict[str, Any]) -> int:
    """Pela porta do `leads.criar`: supressão e "já está no CRM" valem aqui também."""
    rascunho = Lead()
    await _aplicar(session, "negocio", rascunho, {**campos, "nome": _texto(campos.get("nome")) or "-"})
    empresa = await session.get(Empresa, rascunho.empresa_id) if rascunho.empresa_id else None
    contato = await session.get(Contato, rascunho.contato_id) if rascunho.contato_id else None
    nome = _texto(campos.get("nome")) or (empresa.nome if empresa else None) or (contato.nome if contato else None)
    if not nome:
        raise leads.CrmErro("o negócio precisa de um nome, uma empresa ou um contato")
    lead = await leads.criar(
        session,
        origem=OrigemLead(rascunho.origem or OrigemLead.INDICACAO.value),
        nome=nome,
        estabelecimento_id=empresa.estabelecimento_id if empresa else None,
        email=(contato and contato.email) or (empresa and empresa.email),
        telefone=(contato and contato.telefone) or (empresa and empresa.telefone),
        site=empresa.site if empresa else None,
        contato_nome=contato.nome if contato else None,
        cargo=contato.cargo if contato else None,
    )
    for coluna in ("empresa_id", "contato_id", "valor_estimado", "proxima_acao", "proxima_em", "notas"):
        setattr(lead, coluna, getattr(rascunho, coluna))
    await session.commit()
    return lead.id


async def editar(session: AsyncSession, tipo: str, id_: int, campos: dict[str, Any]) -> None:
    if tipo not in _MODELO:
        raise NaoAchei(f"tipo desconhecido: {tipo}")
    if not campos:
        raise leads.CrmErro("nada a alterar")
    obj = await _pegar(session, _MODELO[tipo], id_, _ROTULO[tipo])
    await _aplicar(session, tipo, obj, campos)
    if tipo == "negocio" and "contato_id" in campos:
        contato = await session.get(Contato, obj.contato_id) if obj.contato_id else None
        obj.contato_nome = contato.nome if contato else None
        obj.cargo = contato.cargo if contato else None
    await session.commit()


async def _ja_contatado(session: AsyncSession, lead: Lead) -> bool:
    if lead.estagio != Estagio.PROSPECT.value:
        return True
    saiu = await session.scalar(
        select(Interacao.id).where(Interacao.lead_id == lead.id, Interacao.direcao == Direcao.SAIDA.value).limit(1)
    )
    return saiu is not None


async def excluir(session: AsyncSession, tipo: str, id_: int) -> None:
    if tipo not in _MODELO:
        raise NaoAchei(f"tipo desconhecido: {tipo}")
    obj = await _pegar(session, _MODELO[tipo], id_, _ROTULO[tipo])
    if tipo == "empresa":
        negocios = await session.scalar(select(func.count()).where(Lead.empresa_id == id_))
        if negocios:
            raise NaoPode(f"{obj.nome} tem {negocios} negócio(s): apague ou mude a empresa deles antes")
    if tipo == "negocio":
        if await _ja_contatado(session, obj):
            raise NaoPode(
                "este negócio já recebeu contato: mova para 'perdido' em vez de apagar, "
                "para a clínica não voltar da base e receber outro e-mail 1"
            )
        # Os rascunhos ainda na fila eram para este negócio: saem com ele. O que
        # já foi decidido fica, porque é sinal de treino.
        await session.execute(
            delete(AcaoPendente).where(
                AcaoPendente.alvo_ref == f"comercial_lead:{id_}", AcaoPendente.status == "pendente"
            )
        )
    await session.delete(obj)
    await session.commit()


async def mover(session: AsyncSession, lead_id: int, para: str, motivo: str | None) -> None:
    try:
        estagio = Estagio(para)
    except ValueError as e:
        raise leads.CrmErro(f"estágio desconhecido: {para}") from e
    await leads.mover(session, lead_id, estagio, motivo=_texto(motivo))


async def registrar(
    session: AsyncSession, lead_id: int, *, texto: str, canal: str = "nota", direcao: str | None = None
) -> None:
    """Uma nota, ou um contato feito fora do sistema (liguei, respondeu no WhatsApp)."""
    await _pegar(session, Lead, lead_id, "negócio")
    if not _texto(texto):
        raise leads.CrmErro("escreva o que aconteceu")
    if canal not in CANAIS:
        raise leads.CrmErro(f"canal desconhecido: {canal}")
    direcao = Direcao.INTERNA.value if canal == Canal.NOTA.value else (direcao or Direcao.SAIDA.value)
    if direcao not in {d.value for d in Direcao}:
        raise leads.CrmErro(f"direção desconhecida: {direcao}")
    session.add(Interacao(lead_id=lead_id, canal=canal, direcao=direcao, tipo="manual", texto=texto.strip()))
    await session.commit()


async def empresa_da_base(
    session: AsyncSession,
    e: Estabelecimento,
    *,
    nome: str,
    email: str | None,
    telefone: str | None,
    site: str | None,
) -> Empresa:
    """A empresa do CRM daquele estabelecimento: a que já existe, ou uma nova."""
    existente = await session.scalar(select(Empresa).where(Empresa.estabelecimento_id == e.id))
    if existente:
        return existente
    cnpj = await session.scalar(
        select(Identificador.valor).where(
            Identificador.estabelecimento_id == e.id, Identificador.tipo == TipoIdentificador.CNPJ.value
        )
    )
    empresa = Empresa(
        nome=nome, razao_social=e.razao_social, cnpj=cnpj, estabelecimento_id=e.id,
        status=StatusEmpresa.PROSPECT.value, segmento=e.segmento, site=site, email=email,
        telefone=telefone, bairro=e.bairro, uf=e.uf,
    )
    session.add(empresa)
    await session.flush()
    return empresa


# ── listas ───────────────────────────────────────────────────────────────────


def _dinheiro(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def _busca(termo: str | None, *colunas) -> Any:
    padrao = f"%{termo.strip()}%"
    return or_(*(c.ilike(padrao) for c in colunas))


async def listar_empresas(
    session: AsyncSession, *, busca: str | None = None, status: str | None = None, limite: int = 500
) -> tuple[int, list[dict]]:
    n_contatos = select(func.count()).where(Contato.empresa_id == Empresa.id).scalar_subquery()
    abertos = [e.value for e in leads.ABERTOS]
    n_negocios = (
        select(func.count()).where(Lead.empresa_id == Empresa.id, Lead.estagio.in_(abertos)).scalar_subquery()
    )
    filtros = []
    if busca and busca.strip():
        filtros.append(_busca(busca, Empresa.nome, Empresa.razao_social, Empresa.bairro, Empresa.email))
    if status:
        filtros.append(Empresa.status == status)
    total = await session.scalar(select(func.count()).select_from(Empresa).where(*filtros)) or 0
    linhas = (
        await session.execute(
            select(Empresa, n_contatos.label("n_contatos"), n_negocios.label("n_negocios"))
            .where(*filtros)
            .order_by(Empresa.atualizado_em.desc())
            .limit(limite)
        )
    ).all()
    return total, [
        {
            "id": e.id, "nome": e.nome, "status": e.status, "segmento": e.segmento, "site": e.site,
            "email": e.email, "telefone": e.telefone, "bairro": e.bairro, "cidade": e.cidade, "uf": e.uf,
            "estabelecimento_id": e.estabelecimento_id, "n_contatos": nc, "n_negocios": nn,
        }
        for e, nc, nn in linhas
    ]


async def listar_contatos(
    session: AsyncSession, *, busca: str | None = None, empresa_id: int | None = None, limite: int = 500
) -> tuple[int, list[dict]]:
    filtros = []
    if busca and busca.strip():
        filtros.append(_busca(busca, Contato.nome, Contato.email, Contato.cargo, Empresa.nome))
    if empresa_id is not None:
        filtros.append(Contato.empresa_id == empresa_id)
    base = select(Contato, Empresa.nome).outerjoin(Empresa, Empresa.id == Contato.empresa_id).where(*filtros)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    linhas = (await session.execute(base.order_by(Contato.nome).limit(limite))).all()
    return total, [
        {
            "id": c.id, "nome": c.nome, "cargo": c.cargo, "decisor": c.decisor, "email": c.email,
            "telefone": c.telefone, "linkedin": c.linkedin, "empresa_id": c.empresa_id, "empresa_nome": en,
        }
        for c, en in linhas
    ]


def pode_ir(estagio: str) -> list[str]:
    """Para onde o negócio pode ir daqui, na ordem do funil."""
    destinos = leads.TRANSICOES[Estagio(estagio)]
    return [e for e in ESTAGIOS if Estagio(e) in destinos]


async def listar_negocios(
    session: AsyncSession, *, busca: str | None = None, empresa_id: int | None = None, limite: int = 1000
) -> list[dict]:
    filtros = []
    if busca and busca.strip():
        filtros.append(_busca(busca, Lead.nome, Empresa.nome, Contato.nome, Lead.email))
    if empresa_id is not None:
        filtros.append(Lead.empresa_id == empresa_id)
    abertas = (
        select(func.count())
        .where(Tarefa.lead_id == Lead.id, Tarefa.feita_em.is_(None))
        .scalar_subquery()
    )
    linhas = (
        await session.execute(
            select(Lead, Empresa.nome, Contato.nome, abertas.label("tarefas"))
            .outerjoin(Empresa, Empresa.id == Lead.empresa_id)
            .outerjoin(Contato, Contato.id == Lead.contato_id)
            .where(*filtros)
            .order_by(Lead.atualizado_em.desc())
            .limit(limite)
        )
    ).all()
    return [
        {
            "id": lead.id, "nome": lead.nome, "estagio": lead.estagio, "origem": lead.origem,
            "valor_estimado": _dinheiro(lead.valor_estimado), "empresa_id": lead.empresa_id,
            "empresa_nome": en, "contato_id": lead.contato_id, "contato_nome": cn or lead.contato_nome,
            "email": lead.email, "email_confirmado": lead.email_fonte is not None,
            "proxima_acao": lead.proxima_acao, "proxima_em": lead.proxima_em,
            "motivo_perda": lead.motivo_perda, "tarefas_abertas": ta, "pode_ir": pode_ir(lead.estagio),
            "criado_em": lead.criado_em, "atualizado_em": lead.atualizado_em,
        }
        for lead, en, cn, ta in linhas
    ]


async def listar_atividades(
    session: AsyncSession, *, situacao: str = "abertas", lead_id: int | None = None, hoje: date | None = None
) -> list[dict]:
    hoje = hoje or date.today()
    filtros = []
    if situacao == "abertas":
        filtros.append(Tarefa.feita_em.is_(None))
    elif situacao == "atrasadas":
        filtros += [Tarefa.feita_em.is_(None), Tarefa.vence_em < hoje]
    elif situacao == "feitas":
        filtros.append(Tarefa.feita_em.is_not(None))
    elif situacao != "todas":
        raise leads.CrmErro(f"situação desconhecida: {situacao}")
    if lead_id is not None:
        filtros.append(Tarefa.lead_id == lead_id)
    ordem = (Tarefa.feita_em.desc(),) if situacao == "feitas" else (Tarefa.vence_em, Tarefa.id)
    linhas = (
        await session.execute(
            select(Tarefa, Lead.nome, Lead.estagio, Lead.empresa_id, Empresa.nome)
            .join(Lead, Lead.id == Tarefa.lead_id)
            .outerjoin(Empresa, Empresa.id == Lead.empresa_id)
            .where(*filtros)
            .order_by(*ordem)
            .limit(500)
        )
    ).all()
    return [
        {
            "id": t.id, "tipo": t.tipo, "descricao": t.descricao, "vence_em": t.vence_em,
            "feita_em": t.feita_em, "atrasada": t.feita_em is None and t.vence_em < hoje,
            "lead_id": t.lead_id, "negocio_nome": ln, "negocio_estagio": le,
            "empresa_id": eid, "empresa_nome": en,
        }
        for t, ln, le, eid, en in linhas
    ]


# ── a ficha: o registro e o que está ligado a ele ────────────────────────────


def _exibir(c: Campo, v: Any) -> str:
    if v is None or v == "":
        return ""
    if c.tipo == "sim_nao":
        return "sim" if v else "não"
    if c.tipo == "opcao":
        return c.opcoes.get(v, v)
    if c.tipo == "numero":
        # Espaço inseparável, como o `toLocaleString` da tela: o valor não quebra.
        return f"R$\u00a0{float(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if c.tipo == "data":
        return v.strftime("%d/%m/%Y")
    return str(v)


def _campos(tipo: str, obj: Any) -> list[dict]:
    saida = []
    for nome, c in CAMPOS[tipo].items():
        if c.tipo == "ref" or nome == "nome" or c.tipo == "longo":
            continue  # referência vira grupo; nome é o título; notas têm bloco próprio
        v = obj.feita_em is not None if nome == "feita" else getattr(obj, nome)
        bruto = v.isoformat() if isinstance(v, date) else (float(v) if isinstance(v, Decimal) else v)
        saida.append(
            {
                "campo": nome, "rotulo": c.rotulo, "tipo": c.tipo, "valor": bruto,
                "exibicao": _exibir(c, v), "opcoes": [{"valor": k, "rotulo": r} for k, r in c.opcoes.items()],
            }
        )
    return saida


def _fixo(rotulo: str, exibicao: str | None) -> dict | None:
    """Um campo que se lê mas não se edita aqui (tem porta própria)."""
    if not exibicao:
        return None
    return {"campo": None, "rotulo": rotulo, "tipo": "fixo", "valor": exibicao, "exibicao": exibicao, "opcoes": []}


def _link(tipo: str, id_: int, nome: str, sub: str | None = None) -> dict:
    return {"tipo": tipo, "id": id_, "nome": nome, "sub": sub}


def _link_negocio(lead: Lead) -> dict:
    partes = [ESTAGIOS.get(lead.estagio, lead.estagio)]
    if lead.valor_estimado is not None:
        partes.append(_exibir(Campo("", "numero"), lead.valor_estimado))
    return _link("negocio", lead.id, lead.nome, " · ".join(partes))


def _link_atividade(t: Tarefa) -> dict:
    situacao = "feita" if t.feita_em else f"vence {t.vence_em:%d/%m}"
    titulo = TIPOS_TAREFA.get(t.tipo, t.tipo) + (f": {t.descricao}" if t.descricao else "")
    return _link("atividade", t.id, titulo, situacao)


async def _linha_do_tempo(session: AsyncSession, lead_ids: list[int], nomes: dict[int, str]) -> list[dict]:
    if not lead_ids:
        return []
    interacoes = await session.scalars(
        select(Interacao).where(Interacao.lead_id.in_(lead_ids)).order_by(Interacao.criado_em.desc()).limit(200)
    )
    transicoes = await session.scalars(
        select(Transicao).where(Transicao.lead_id.in_(lead_ids)).order_by(Transicao.criado_em.desc()).limit(200)
    )
    eventos = [
        {
            "quando": i.criado_em, "tipo": "interacao", "canal": i.canal, "direcao": i.direcao,
            "rotulo": i.tipo, "texto": (i.dados or {}).get("assunto") or i.texto,
            "lead_id": i.lead_id, "negocio_nome": nomes.get(i.lead_id),
        }
        for i in interacoes
    ] + [
        {
            "quando": t.criado_em, "tipo": "transicao", "canal": None, "direcao": None,
            "rotulo": f"{ESTAGIOS.get(t.de or '', t.de or 'novo')} → {ESTAGIOS.get(t.para, t.para)}",
            "texto": t.motivo, "lead_id": t.lead_id, "negocio_nome": nomes.get(t.lead_id),
        }
        for t in transicoes
    ]
    return sorted(eventos, key=lambda e: e["quando"], reverse=True)


async def registro(session: AsyncSession, tipo: str, id_: int) -> dict:
    if tipo not in _MODELO:
        raise NaoAchei(f"tipo desconhecido: {tipo}")
    obj = await _pegar(session, _MODELO[tipo], id_, _ROTULO[tipo])
    grupos: list[dict] = []
    fixos: list[dict | None] = []
    linha: list[dict] = []
    notas = getattr(obj, "notas", None)
    titulo = getattr(obj, "nome", None)

    if tipo == "empresa":
        contatos = list(await session.scalars(select(Contato).where(Contato.empresa_id == id_).order_by(Contato.nome)))
        negocios = list(
            await session.scalars(select(Lead).where(Lead.empresa_id == id_).order_by(Lead.criado_em.desc()))
        )
        ids = [lead.id for lead in negocios]
        tarefas = (
            list(await session.scalars(select(Tarefa).where(Tarefa.lead_id.in_(ids)).order_by(Tarefa.vence_em)))
            if ids
            else []
        )
        fixos.append(_fixo("Na base", f"estabelecimento {obj.estabelecimento_id}" if obj.estabelecimento_id else None))
        grupos = [
            {"titulo": "Contatos", "tipo": "contato",
             "itens": [_link("contato", c.id, c.nome, " · ".join(x for x in [c.cargo, "decisor" if c.decisor else None] if x) or None) for c in contatos]},
            {"titulo": "Negócios", "tipo": "negocio", "itens": [_link_negocio(lead) for lead in negocios]},
            {"titulo": "Atividades", "tipo": "atividade", "itens": [_link_atividade(t) for t in tarefas]},
        ]
        linha = await _linha_do_tempo(session, ids, {lead.id: lead.nome for lead in negocios})

    elif tipo == "contato":
        empresa = await session.get(Empresa, obj.empresa_id) if obj.empresa_id else None
        negocios = list(await session.scalars(select(Lead).where(Lead.contato_id == id_)))
        if empresa:
            grupos.append({"titulo": "Empresa", "tipo": "empresa", "itens": [_link("empresa", empresa.id, empresa.nome, STATUS_EMPRESA.get(empresa.status))]})
        grupos.append({"titulo": "Negócios", "tipo": "negocio", "itens": [_link_negocio(lead) for lead in negocios]})
        linha = await _linha_do_tempo(session, [lead.id for lead in negocios], {lead.id: lead.nome for lead in negocios})

    elif tipo == "negocio":
        empresa = await session.get(Empresa, obj.empresa_id) if obj.empresa_id else None
        contato = await session.get(Contato, obj.contato_id) if obj.contato_id else None
        tarefas = list(await session.scalars(select(Tarefa).where(Tarefa.lead_id == id_).order_by(Tarefa.feita_em.is_not(None), Tarefa.vence_em)))
        fixos += [
            {"campo": "estagio", "rotulo": "Estágio", "tipo": "estagio", "valor": obj.estagio,
             "exibicao": ESTAGIOS.get(obj.estagio, obj.estagio),
             "opcoes": [{"valor": e, "rotulo": ESTAGIOS[e]} for e in pode_ir(obj.estagio)]},
            _fixo("Motivo da perda", obj.motivo_perda),
            _fixo("Volta em", obj.volta_em and obj.volta_em.strftime("%d/%m/%Y")),
            _fixo("Criado em", obj.criado_em.strftime("%d/%m/%Y")),
        ]
        if empresa:
            grupos.append({"titulo": "Empresa", "tipo": "empresa", "itens": [_link("empresa", empresa.id, empresa.nome, STATUS_EMPRESA.get(empresa.status))]})
        grupos.append({"titulo": "Contato", "tipo": "contato", "itens": [_link("contato", contato.id, contato.nome, contato.cargo)] if contato else []})
        grupos.append({"titulo": "Atividades", "tipo": "atividade", "itens": [_link_atividade(t) for t in tarefas]})
        linha = await _linha_do_tempo(session, [id_], {id_: obj.nome})

    else:  # atividade
        lead = await session.get(Lead, obj.lead_id)
        titulo = TIPOS_TAREFA.get(obj.tipo, obj.tipo) + (f": {obj.descricao}" if obj.descricao else "")
        fixos.append(_fixo("Feita em", obj.feita_em and obj.feita_em.strftime("%d/%m/%Y %H:%M")))
        grupos.append({"titulo": "Negócio", "tipo": "negocio", "itens": [_link_negocio(lead)]})
        if lead.empresa_id:
            empresa = await session.get(Empresa, lead.empresa_id)
            grupos.append({"titulo": "Empresa", "tipo": "empresa", "itens": [_link("empresa", empresa.id, empresa.nome)]})

    return {
        "tipo": tipo, "id": id_, "titulo": titulo,
        "campos": [c for c in fixos if c] + _campos(tipo, obj),
        "grupos": grupos, "notas": notas, "linha_do_tempo": linha,
        # Os valores crus, para o formulário de edição abrir preenchido.
        "valores": {k: _cru(obj, k) for k in CAMPOS[tipo]},
    }


def _cru(obj: Any, nome: str) -> Any:
    v = obj.feita_em is not None if nome == "feita" else getattr(obj, nome)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


# ── o painel ─────────────────────────────────────────────────────────────────


async def painel(session: AsyncSession, *, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    por_estagio = {
        e: (t, float(v or 0))
        for e, t, v in (
            await session.execute(
                select(Lead.estagio, func.count(), func.sum(Lead.valor_estimado)).group_by(Lead.estagio)
            )
        ).all()
    }
    abertos = [e.value for e in leads.ABERTOS]
    tarefas = (
        await session.execute(
            select(
                func.count().filter(Tarefa.feita_em.is_(None)),
                func.count().filter(Tarefa.feita_em.is_(None), Tarefa.vence_em < hoje),
                func.count().filter(Tarefa.feita_em.is_(None), Tarefa.vence_em == hoje),
            )
        )
    ).one()
    empresas = dict(
        (await session.execute(select(Empresa.status, func.count()).group_by(Empresa.status))).all()
    )
    perdas = (
        await session.execute(
            select(Lead.motivo_perda, func.count())
            .where(Lead.estagio == Estagio.PERDIDO.value, Lead.motivo_perda.is_not(None))
            .group_by(Lead.motivo_perda)
            .order_by(func.count().desc())
            .limit(5)
        )
    ).all()
    return {
        "negocios_abertos": sum(t for e, (t, _) in por_estagio.items() if e in abertos),
        "valor_aberto": round(sum(v for e, (_, v) in por_estagio.items() if e in abertos), 2),
        "ganhos": por_estagio.get("ganho", (0, 0))[0],
        "valor_ganho": round(por_estagio.get("ganho", (0, 0.0))[1], 2),
        "perdidos": por_estagio.get("perdido", (0, 0))[0],
        "por_estagio": [
            {"estagio": e, "rotulo": r, "total": por_estagio.get(e, (0, 0))[0], "valor": round(por_estagio.get(e, (0, 0.0))[1], 2)}
            for e, r in ESTAGIOS.items()
        ],
        "tarefas_abertas": tarefas[0],
        "tarefas_atrasadas": tarefas[1],
        "tarefas_hoje": tarefas[2],
        "empresas": sum(empresas.values()),
        "clientes": empresas.get(StatusEmpresa.CLIENTE.value, 0),
        "contatos": await session.scalar(select(func.count()).select_from(Contato)) or 0,
        "motivos_perda": [{"motivo": m, "total": t} for m, t in perdas],
        "proximas": (await listar_atividades(session, situacao="abertas", hoje=hoje))[:8],
    }


# O vocabulário que a tela usa para rótulos, filtros e selects.
OPCOES: dict[str, dict[str, str]] = {
    "estagio": ESTAGIOS,
    "status_empresa": STATUS_EMPRESA,
    "origem": ORIGENS,
    "tipo_tarefa": TIPOS_TAREFA,
    "canal": CANAIS,
}
