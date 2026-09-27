"""Redator (N0): o e-mail 1 e o lembrete, pela fila de aprovação (Fase 1, passo 4).

O esqueleto é o modelo do 1.2.7 §1.4, que já passou pelas regras da forma
(`data/comercial/base/regras-prospeccao.md` §3): quem sou, **de onde tirei o
contato**, o que faço, um pedido só, e o opt-out. A IA escreve **só a
abertura**, uma ou duas frases sobre a clínica, a partir de um fato da ficha que
tem fonte. É o único trecho que muda de clínica para clínica, e é o que a voz
pede ("a primeira frase menciona algo concreto do destinatário"). O resto é
texto que eu revisei, não texto que um modelo de 4B improvisa.

O lembrete não tem IA: volta uma vez ao e-mail 1, repete a oferta e avisa que é
o último. Sai só 5 dias úteis depois do e-mail 1 (§2).

Nada é enviado daqui (D16). O texto vai para `/fila`: eu aprovo, edito ou
rejeito, copio para o webmail do `comercial@` e marco "enviei". A edição vira
par de preferência pelo caminho que a fila já tem, e o aprovado vira exemplo de
estilo para o próximo.

Antes de chegar à fila, o `verificar` barra o que é objetivo: frase proibida da
voz, jargão, preço, promessa, mais de um link, e texto sem opt-out ou sem a
origem do contato. Abertura reprovada é pedida de novo uma vez; reprovada de
novo, sai a abertura montada pelos fatos da ficha, sem IA.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.crm import calendario, leads
from app.db.models.acao_pendente import AcaoPendente
from app.db.models.comercial.crm import (
    Canal,
    Direcao,
    Estagio,
    Interacao,
    Lead,
    Tarefa,
    TipoTarefa,
)
from app.fila import exemplos
from app.fila import servico as fila
from app.llm import gateway, voz
from app.llm.tipos import LLMErro
from app.utils.logger import get_logger

logger = get_logger()

AGENTE = "redator_comercial"
EMAIL, LEMBRETE = "email_frio", "lembrete_frio"
DIAS_ATE_O_LEMBRETE = 5

ASSUNTO = "pacientes que escrevem e não conseguem marcar"
OPT_OUT = 'Se não fizer sentido, é só responder "não" que eu não escrevo mais.'
ASSINATURA = "Pablo · pabloortiz.dev"
# O modelo do 1.2.7, que eu revisei, tem ~134 palavras sem a abertura: passa das
# 120 da voz. O teto do frio é o modelo mais a abertura, que tem até 40.
MAX_PALAVRAS = 175
MAX_PALAVRAS_ABERTURA = 40


class NaoPode(leads.CrmErro):
    """O lead não está no ponto de receber este texto (e o motivo diz por quê)."""


# ── o texto ──────────────────────────────────────────────────────────

_SUFIXOS = re.compile(r"[\s,.-]+(ltda|me|epp|eireli|s/?s|s\.?a\.?|mei)\.?$", re.I)
_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o"}


def nome_da_clinica(nome: str) -> str:
    """'CLINICA AURORA DE PSICOLOGIA LTDA' → 'Clinica Aurora de Psicologia'."""
    limpo = nome.strip()
    while (sem := _SUFIXOS.sub("", limpo)) != limpo:
        limpo = sem
    if limpo.isupper():
        palavras = limpo.lower().split()
        limpo = " ".join(
            p if i and p in _MINUSCULAS else p[:1].upper() + p[1:] for i, p in enumerate(palavras)
        )
    return limpo


def saudacao(lead: Lead) -> str:
    if lead.contato_nome:
        return f"Oi, {lead.contato_nome.split()[0]}."
    clinica = nome_da_clinica(lead.nome)
    primeira = clinica.split()[0].lower() if clinica else ""
    artigo = "da" if primeira.endswith(("a", "ã")) else "do"
    return f"Oi, pessoal {artigo} {clinica}."


def origem(email_fonte: str) -> str:
    """De onde tirei o contato, sem link: o domínio no texto conta como link."""
    caminho = urlparse(email_fonte).path.strip("/").lower()
    if not caminho:
        onde = "na página inicial do site de vocês"
    elif re.search(r"contato|contact|fale", caminho):
        onde = "na página de contato do site de vocês"
    else:
        onde = "no site de vocês"
    return f"Achei este e-mail {onde}."


def montar_email(lead: Lead, abertura: str) -> str:
    partes = [
        f"Assunto: {ASSUNTO}",
        " ".join(p for p in (saudacao(lead), abertura.strip()) if p),
        f"Sou o Pablo, desenvolvedor em São Paulo. {origem(lead.email_fonte or '')}",
        "Escrevo porque a queixa mais comum de paciente sobre clínica, nas reclamações "
        "públicas, não é sobre o atendimento na consulta: é a mensagem de WhatsApp que "
        "ninguém responde, ou o agendamento que não termina.",
        "Eu monto um atendente para o WhatsApp da clínica que responde na hora, marca na "
        "agenda e passa para a recepção tudo que não for simples. Ele não fala de sintoma "
        "nem de diagnóstico.",
        "Se fizer sentido, faço uma conversa de 30 minutos, sem custo, para olhar como está "
        "o atendimento de vocês hoje e deixar 3 pontos por escrito.",
        OPT_OUT,
        ASSINATURA,
    ]
    return "\n\n".join(partes)


def montar_lembrete(lead: Lead, assunto_do_1: str, enviado_em: date) -> str:
    partes = [
        f"Assunto: Re: {assunto_do_1}",
        f"{saudacao(lead)} Volto uma vez só ao e-mail que mandei em {enviado_em:%d/%m}, sobre "
        "a mensagem de WhatsApp de paciente que fica sem resposta.",
        f"Sou o Pablo, desenvolvedor em São Paulo. {origem(lead.email_fonte or '')}",
        "Se fizer sentido, a conversa de 30 minutos continua de pé, sem custo: olho como está "
        "o atendimento de vocês hoje e deixo 3 pontos por escrito.",
        f"{OPT_OUT} Este é o último e-mail sobre isso.",
        ASSINATURA,
    ]
    return "\n\n".join(partes)


def separar(texto: str) -> tuple[str, str]:
    """'Assunto: x\\n\\ncorpo' → (x, corpo). Sem a linha de assunto, vale o padrão."""
    linhas = texto.strip().split("\n", 1)
    if linhas[0].lower().startswith("assunto:"):
        return linhas[0].split(":", 1)[1].strip(), (linhas[1] if len(linhas) > 1 else "").strip()
    return ASSUNTO, texto.strip()


# ── o verificador ────────────────────────────────────────────────────

# Palavra de dentro do meu trabalho, que a clínica não usa para falar de si.
_JARGAO = re.compile(
    r"\b(lead|leads|funil|consumidor|crm|chatbot|bot|omnichannel|roi|saas|llm|"
    r"intelig[êe]ncia artificial|automa[çc][ãa]o|machine learning|convers[ãa]o|engajamento)\b",
    re.I,
)
_IA = re.compile(r"\bIA\b")
_PRECO = re.compile(r"R\$|\breais\b|\bdesconto|\bpromo[çc][ãa]o|\bgr[áa]tis\b", re.I)
_PROMESSA = re.compile(
    r"\bgarant\w*|\d+\s?%|\b(aument|dobr|tripl)\w+ (seus|suas|o|a|os|as) "
    r"(pacientes|agendamentos|faturamento|vendas|consultas)",
    re.I,
)
_LINK = re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|dev|net|org|io)(?:\.br)?\b|\b[\w-]+\.br\b", re.I)
# O prompt pede "sem elogio"; modelo pequeno elogia mesmo assim.
_ELOGIO = re.compile(r"parab[ée]ns|admir\w*|incr[íi]ve\w*|excelente|maravilhos\w*|lind[oa]s?\b|sensaciona\w*", re.I)
_OPT_OUT = re.compile(r"responder\W+n[ãa]o\W", re.I)
_ORIGEM = re.compile(r"achei (este|seu|o) (e-?mail|contato)", re.I)


def verificar(texto: str) -> list[str]:
    """O que barra o texto antes da fila. Lista vazia = passou."""
    _, corpo = separar(texto)
    problemas = voz.checar(corpo, max_palavras=MAX_PALAVRAS)
    if m := _JARGAO.search(corpo) or _IA.search(corpo):
        problemas.append(f"jargão: {m.group(0)!r}")
    if m := _PRECO.search(corpo):
        problemas.append(f"preço ou desconto em e-mail frio: {m.group(0)!r}")
    if m := _PROMESSA.search(corpo):
        problemas.append(f"promessa de resultado: {m.group(0)!r}")
    if (n := len(_LINK.findall(corpo))) > 1:
        problemas.append(f"{n} links (máximo 1)")
    if not _OPT_OUT.search(corpo):
        problemas.append('sem opt-out ("é só responder \'não\'")')
    if not _ORIGEM.search(corpo):
        problemas.append("não diz de onde tirei o contato")
    return problemas


def verificar_abertura(abertura: str) -> list[str]:
    problemas = voz.checar(abertura, max_palavras=MAX_PALAVRAS_ABERTURA)
    if "?" in abertura:
        problemas.append("pergunta na abertura (o pedido é um só, no fim)")
    if "!" in abertura:
        problemas.append("exclamação na abertura")
    if m := _ELOGIO.search(abertura):
        problemas.append(f"elogio: {m.group(0)!r}")
    if re.match(r"\s*(eu\b|sou\b|meu nome|me chamo)", abertura, re.I):
        problemas.append("começa falando de mim")
    if m := _JARGAO.search(abertura) or _IA.search(abertura) or _PRECO.search(abertura) or _PROMESSA.search(abertura):
        problemas.append(f"termo proibido: {m.group(0)!r}")
    if _LINK.search(abertura):
        problemas.append("link na abertura")
    return problemas


# ── a abertura ───────────────────────────────────────────────────────

_PROMPT = """Você escreve a abertura de um e-mail curto para uma clínica de psicologia.
Uma ou duas frases, no máximo {max} palavras, em português do Brasil, falando com a
clínica ("vocês"). Use só os fatos abaixo, e cite de qual URL tirou.

Regras:
- Fale de algo concreto da clínica: como os pacientes marcam, o que ela oferece.
- Não elogie ("parabéns", "admiro", "incrível"), não faça pergunta, não fale de mim.
- Não mencione preço, IA, robô, automação, tecnologia.
- Não repita o nome da clínica: a saudação já tem.

Fatos da clínica (com a página de onde vieram):
{fatos}
{few_shot}
Responda só o JSON: {{"abertura": "...", "fonte": "..."}}"""

_SCHEMA = {
    "type": "object",
    "properties": {"abertura": {"type": "string"}, "fonte": {"type": "string"}},
    "required": ["abertura", "fonte"],
}


def _fatos(ficha: dict) -> list[tuple[str, str]]:
    """(frase, fonte) dos fatos da ficha que servem para abrir o e-mail."""
    fatos = []
    for campo, rotulo in (("o_que_faz", "O que a clínica faz"), ("gancho", "Observação sobre o site")):
        if f := ficha.get(campo):
            fatos.append((f"{rotulo}: {f['valor']}", f["fonte"]))
    if f := ficha.get("agendamento_online"):
        fatos.append((f"O site tem agendamento online (\"{f['valor']}\")", f["fonte"]))
    if f := ficha.get("whatsapp"):
        fatos.append(("O site publica o WhatsApp como canal", f["fonte"]))
    if (f := ficha.get("psicologos_crp")) and int(f["valor"]) > 1:
        fatos.append((f"O site mostra {f['valor']} psicólogos com CRP", f["fonte"]))
    return fatos


def abertura_pelos_fatos(ficha: dict) -> str:
    """Sem IA: uma frase montada pelo que a ficha achou. Vazia, se não achou nada."""
    whatsapp, agenda = ficha.get("whatsapp"), ficha.get("agendamento_online")
    crp = ficha.get("psicologos_crp")
    if whatsapp and agenda:
        return "Vi no site de vocês que o paciente pode chamar no WhatsApp ou marcar online."
    if whatsapp:
        return "Vi no site de vocês que o WhatsApp é o canal para o paciente chegar até a clínica."
    if agenda:
        return "Vi no site de vocês que o paciente já consegue marcar online."
    if crp and int(crp["valor"]) > 1:
        return f"Vi no site de vocês a equipe de {crp['valor']} psicólogos."
    return ""


async def escrever_abertura(ficha: dict, *, alvo_ref: str) -> tuple[str, str | None, list[str]]:
    """(abertura, fonte, avisos). A IA escreve; o verificador decide se fica."""
    fatos = _fatos(ficha)
    paginas = {u.rstrip("/"): u for u in ficha.get("paginas", [])}
    avisos: list[str] = []
    if fatos:
        contexto = f"e-mail frio para clínica de psicologia: {(ficha.get('o_que_faz') or {}).get('valor', '')}"
        try:
            achados = await exemplos.exemplos_para(EMAIL, contexto)
        except Exception as e:  # noqa: BLE001 — sem exemplo, escreve igual
            logger.warning(f"Redator: sem few-shot ({type(e).__name__})")
            achados = []
        few = exemplos.bloco_few_shot(achados)
        prompt = _PROMPT.format(
            max=MAX_PALAVRAS_ABERTURA,
            fatos="\n".join(f"- {t} [{u}]" for t, u in fatos),
            few_shot=f"\n{few}\n" if few else "",
        )
        for tentativa in range(2):
            try:
                r = await gateway.gerar(
                    prompt, tarefa="redigir", agente=AGENTE, json_schema=_SCHEMA, alvo_ref=alvo_ref
                )
            except LLMErro as e:
                avisos.append(f"IA indisponível ({type(e).__name__}): abertura montada pelos fatos da ficha")
                break
            dados = r.json if isinstance(r.json, dict) else {}
            abertura = str(dados.get("abertura") or "").strip()
            fonte = paginas.get(str(dados.get("fonte") or "").strip().rstrip("/"))
            problemas = verificar_abertura(abertura) if abertura else ["abertura vazia"]
            if fonte is None:
                problemas.append("a IA citou uma página que o Pesquisador não leu")
            if not problemas:
                return abertura, fonte, avisos
            logger.info(f"Redator: abertura reprovada ({'; '.join(problemas)})")
            prompt += f"\n\nA abertura anterior foi reprovada: {'; '.join(problemas)}. Escreva outra."
            if tentativa == 1:
                avisos.append(f"a IA errou duas vezes ({'; '.join(problemas)}): abertura montada pelos fatos da ficha")
    abertura = abertura_pelos_fatos(ficha)
    if not abertura:
        avisos.append("a ficha não tem fato para abrir o e-mail: começa direto na apresentação")
    return abertura, None, avisos


# ── o fluxo ──────────────────────────────────────────────────────────


@dataclass
class Rascunho:
    acao_id: UUID
    tipo: str
    avisos: list[str] = field(default_factory=list)


def _alvo(lead_id: int) -> str:
    return f"comercial_lead:{lead_id}"


async def _acoes(session: AsyncSession, lead_id: int) -> list[AcaoPendente]:
    return list(
        await session.scalars(
            select(AcaoPendente)
            .where(AcaoPendente.alvo_ref == _alvo(lead_id), AcaoPendente.agente == AGENTE)
            .order_by(AcaoPendente.criada_em)
        )
    )


async def _enviados(session: AsyncSession, lead_id: int) -> list[Interacao]:
    return list(
        await session.scalars(
            select(Interacao)
            .where(
                Interacao.lead_id == lead_id,
                Interacao.canal == Canal.EMAIL.value,
                Interacao.direcao == Direcao.SAIDA.value,
                Interacao.tipo.in_((EMAIL, LEMBRETE)),
            )
            .order_by(Interacao.criado_em)
        )
    )


async def _ficha(session: AsyncSession, lead_id: int) -> dict | None:
    i = await session.scalar(
        select(Interacao)
        .where(Interacao.lead_id == lead_id, Interacao.tipo == "ficha")
        .order_by(Interacao.criado_em.desc())
        .limit(1)
    )
    return i.dados if i else None


async def _fechar(session: AsyncSession, lead_id: int, *tipos: TipoTarefa) -> None:
    abertas = await session.scalars(
        select(Tarefa).where(
            Tarefa.lead_id == lead_id,
            Tarefa.tipo.in_([t.value for t in tipos]),
            Tarefa.feita_em.is_(None),
        )
    )
    for t in abertas:
        t.feita_em = datetime.now(UTC)


async def escrever(
    session: AsyncSession, lead_id: int, *, tipo: str = EMAIL, hoje: date | None = None
) -> Rascunho:
    """Escreve o e-mail 1 (ou o lembrete) e põe na fila. Não envia."""
    hoje = hoje or date.today()
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise leads.CrmErro(f"lead {lead_id} não existe")
    if tipo not in (EMAIL, LEMBRETE):
        raise NaoPode(f"tipo {tipo!r} não existe")
    if not (lead.email and lead.email_fonte):
        raise NaoPode("o e-mail não está confirmado no site da clínica: pesquise antes")
    if await leads.suprimido(session, email=lead.email, telefone=None):
        raise NaoPode("este e-mail está na supressão: não se escreve mais para ele")

    enviados = await _enviados(session, lead_id)
    ja = {i.tipo for i in enviados}
    enviadas = {(i.dados or {}).get("acao_id") for i in enviados}
    em_aberto = [
        a for a in await _acoes(session, lead_id)
        if a.tipo == tipo and a.status != "rejeitada" and str(a.id) not in enviadas
    ]
    if em_aberto:
        raise NaoPode("já há um texto deste na fila ou aprovado esperando o envio")

    if tipo == EMAIL:
        if EMAIL in ja:
            raise NaoPode("o e-mail 1 já foi enviado")
        if lead.estagio != Estagio.PROSPECT.value:
            raise NaoPode(f"o lead está em {lead.estagio}: o e-mail 1 é para quem está em prospect")
        ficha = await _ficha(session, lead_id) or {}
        abertura, fonte, avisos = await escrever_abertura(ficha, alvo_ref=_alvo(lead_id))
        texto = montar_email(lead, abertura)
        titulo = f"E-mail 1 · {nome_da_clinica(lead.nome)}"
        contexto = f"e-mail frio para clínica de psicologia: {(ficha.get('o_que_faz') or {}).get('valor') or lead.nome}"
        extra = {"abertura_fonte": fonte}
    else:
        if LEMBRETE in ja:
            raise NaoPode("o lembrete já foi enviado: depois dele, nada (regras §2)")
        primeiro = next((i for i in enviados if i.tipo == EMAIL), None)
        if primeiro is None:
            raise NaoPode("o lembrete vem depois do e-mail 1, que ainda não foi enviado")
        if lead.estagio != Estagio.CONTATADO.value:
            raise NaoPode(f"o lead está em {lead.estagio}: lembrete é só para quem não respondeu")
        enviado_em = primeiro.criado_em.date()
        pode_em = calendario.somar_dias_uteis(enviado_em, DIAS_ATE_O_LEMBRETE)
        if hoje < pode_em:
            raise NaoPode(f"o lembrete só sai em {pode_em:%d/%m}, 5 dias úteis depois do e-mail 1")
        texto = montar_lembrete(lead, (primeiro.dados or {}).get("assunto") or ASSUNTO, enviado_em)
        avisos, titulo = [], f"Lembrete · {nome_da_clinica(lead.nome)}"
        contexto, extra = "lembrete de e-mail frio para clínica de psicologia", {}

    problemas = verificar(texto)
    if problemas:
        # O esqueleto é meu e a abertura já passou: chegar aqui é defeito do código.
        raise NaoPode(f"o texto não passou no verificador: {'; '.join(problemas)}")

    acao = await fila.criar(
        agente=AGENTE, tipo=tipo, titulo=titulo, texto_gerado=texto, contexto=contexto,
        payload={"lead_id": lead.id, "para": lead.email, "email_fonte": lead.email_fonte, "avisos": avisos, **extra},
        alvo_ref=_alvo(lead.id),
    )
    await _fechar(session, lead.id, TipoTarefa.ESCREVER_EMAIL, TipoTarefa.LEMBRETE)
    session.add(Tarefa(lead_id=lead.id, tipo=TipoTarefa.ENVIAR_EMAIL.value, vence_em=hoje))
    lead.proxima_acao = f"aprovar o {'e-mail 1' if tipo == EMAIL else 'lembrete'} na fila e enviar pelo comercial@"
    lead.proxima_em = hoje
    await session.commit()
    return Rascunho(acao.id, tipo, avisos)


async def enviei(session: AsyncSession, lead_id: int, acao_id: UUID, *, hoje: date | None = None) -> Lead:
    """Registra que eu enviei o texto aprovado, pelo webmail."""
    hoje = hoje or date.today()
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise leads.CrmErro(f"lead {lead_id} não existe")
    acao = await session.get(AcaoPendente, acao_id)
    if acao is None or acao.alvo_ref != _alvo(lead_id) or acao.agente != AGENTE:
        raise NaoPode("este texto não é deste lead")
    if acao.status not in ("aprovada", "editada"):
        raise NaoPode(f"o texto está '{acao.status}': só o aprovado vai para o envio")
    if any((i.dados or {}).get("acao_id") == str(acao.id) for i in await _enviados(session, lead_id)):
        raise NaoPode("este texto já foi marcado como enviado")

    assunto, corpo = separar(acao.texto or "")
    session.add(
        Interacao(
            lead_id=lead.id, canal=Canal.EMAIL.value, direcao=Direcao.SAIDA.value, tipo=acao.tipo,
            texto=corpo, dados={"assunto": assunto, "para": lead.email, "acao_id": str(acao.id)},
        )
    )
    await _fechar(session, lead.id, TipoTarefa.ENVIAR_EMAIL)
    if acao.tipo == EMAIL:
        pode_em = calendario.somar_dias_uteis(hoje, DIAS_ATE_O_LEMBRETE)
        session.add(Tarefa(lead_id=lead.id, tipo=TipoTarefa.LEMBRETE.value, vence_em=pode_em))
        lead.proxima_acao, lead.proxima_em = f"sem resposta até {pode_em:%d/%m}: lembrete", pode_em
    else:
        lead.proxima_acao, lead.proxima_em = "aguardar resposta ao lembrete; depois dele, nada", None
    await session.flush()
    if acao.tipo == EMAIL and lead.estagio == Estagio.PROSPECT.value:
        return await leads.mover(session, lead.id, Estagio.CONTATADO, motivo="e-mail 1 enviado", hoje=hoje)
    await session.commit()
    await session.refresh(lead)
    return lead


@dataclass
class RascunhoLead:
    acao_id: UUID
    tipo: str
    status: str
    assunto: str
    corpo: str
    motivo: str | None
    avisos: list[str]
    problemas: list[str]
    criada_em: datetime
    enviado_em: datetime | None


async def rascunhos(session: AsyncSession, lead_id: int) -> list[RascunhoLead]:
    """Os textos do Redator para este lead, com o que já saiu."""
    saida = {(i.dados or {}).get("acao_id"): i.criado_em for i in await _enviados(session, lead_id)}
    lista = []
    for a in await _acoes(session, lead_id):
        assunto, corpo = separar(a.texto or "")
        lista.append(
            RascunhoLead(
                acao_id=a.id, tipo=a.tipo, status=a.status, assunto=assunto, corpo=corpo,
                motivo=a.motivo, avisos=list((a.payload or {}).get("avisos") or []),
                # O que eu editei na fila também passa pela régua, antes de copiar.
                problemas=verificar(a.texto or "") if a.status == "editada" else [],
                criada_em=a.criada_em, enviado_em=saida.get(str(a.id)),
            )
        )
    return lista
