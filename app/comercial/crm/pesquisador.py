"""Pesquisador (N1): a ficha da clínica, com a fonte de cada fato (Fase 1, passo 3).

**Varre o site público da própria clínica** (`varredura.py`: página por
página, as de contato e equipe primeiro, parando quando acha tudo o que
importa, com JavaScript pelo Playwright quando a página precisa) e monta a
ficha que o Redator (passo 4) usa para escrever o e-mail. Duas camadas, e a
divisão é de propósito:

- **O que o código acha, a IA não inventa.** E-mails publicados, WhatsApp
  publicado, sinal de agendamento online e os números de CRP (quantos
  psicólogos aparecem) saem por regra, com a URL da página onde estavam.
- **A IA só resume e sugere o gancho**, e cada campo precisa apontar para uma
  das URLs lidas. Sem fonte, o campo fica vazio. Se a IA falhar, a ficha sai
  do mesmo jeito, só sem os dois campos.

E a regra que fecha o passo (`regras-prospeccao.md` §4): **o e-mail só vira
destinatário se a clínica o publica no próprio site.** O e-mail da base que
não aparece lá não é usado; se o site mostra outro, é o do site que vale.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html import unescape
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.crm import leads, varredura
from app.db.models.comercial.crm import Canal, Direcao, Interacao, Lead, Tarefa, TipoTarefa
from app.llm import gateway
from app.llm.tipos import LLMErro
from app.utils.logger import get_logger

logger = get_logger()

AGENTE = "comercial.pesquisador"
MAX_TEXTO_IA = 6_000

# Domínio de e-mail gratuito não é site da clínica.
GRATUITOS = frozenset({
    "gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "yahoo.com.br",
    "icloud.com", "uol.com.br", "bol.com.br", "terra.com.br", "ig.com.br", "globo.com",
    "msn.com", "protonmail.com", "proton.me",
})

_EMAIL = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", re.I)
_WHATSAPP = re.compile(r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\d{10,13})", re.I)
_CRP = re.compile(r"CRP\s*[-:–]?\s*(\d{1,2})\s*/\s*(\d{3,6})", re.I)
_AGENDA = re.compile(
    r"doctoralia|agende|agendar|agendamento online|marque sua (?:consulta|sessão)|calendly|cal\.com|agenda online",
    re.I,
)
# O site precisa ser da clínica. O e-mail da base às vezes é do contador (a H18
# do 1.2.8): o domínio dele leva a um site de contabilidade, que publica o
# mesmo e-mail e "confirmaria" um destinatário que não é da clínica. Visto na
# primeira rodada com dado real, em 27/09/2026.
_PSICOLOGIA = re.compile(r"psic[oó]log|psicoterap|\bCRP\b", re.I)


@dataclass
class Fato:
    valor: str | int | bool
    fonte: str


@dataclass
class Ficha:
    site: str
    paginas: list[str] = field(default_factory=list)
    emails: list[Fato] = field(default_factory=list)
    whatsapp: Fato | None = None
    agendamento_online: Fato | None = None
    psicologos_crp: Fato | None = None
    o_que_faz: Fato | None = None
    gancho: Fato | None = None
    com_javascript: list[str] = field(default_factory=list)
    parou_porque: str = ""

    def completa(self) -> bool:
        """Tudo o que importa para prospectar: parar de varrer aqui."""
        return bool(self.emails and self.whatsapp and self.agendamento_online and self.psicologos_crp)

    def para_json(self) -> dict:
        def f(x: Fato | None) -> dict | None:
            return {"valor": x.valor, "fonte": x.fonte} if x else None

        return {
            "site": self.site,
            "paginas": self.paginas,
            "emails": [f(e) for e in self.emails],
            "whatsapp": f(self.whatsapp),
            "agendamento_online": f(self.agendamento_online),
            "psicologos_crp": f(self.psicologos_crp),
            "o_que_faz": f(self.o_que_faz),
            "gancho": f(self.gancho),
            "com_javascript": self.com_javascript,
            "parou_porque": self.parou_porque,
        }


@dataclass
class Resultado:
    status: str  # "ok" | "sem_site" | "site_fora" | "nao_e_da_clinica"
    ficha: Ficha | None = None
    email_confirmado: bool = False
    mensagem: str = ""


def site_provavel(email: str | None) -> str | None:
    """O site pelo domínio do e-mail, quando não é e-mail gratuito."""
    if not email or "@" not in email:
        return None
    dominio = email.rsplit("@", 1)[1].strip().lower()
    return None if dominio in GRATUITOS else f"https://{dominio}"


def _normalizar_site(site: str) -> str:
    site = site.strip()
    if not re.match(r"^https?://", site, re.I):
        site = f"https://{site}"
    p = urlparse(site)
    return f"{p.scheme}://{p.netloc}".lower()


def _texto(html: str) -> str:
    return varredura.texto_visivel(html)


def extrair(site: str, paginas: list[tuple[str, str]]) -> Ficha:
    """O que dá para afirmar por regra, com a página de onde veio."""
    ficha = Ficha(site=_normalizar_site(site), paginas=[u for u, _ in paginas])
    vistos: set[str] = set()
    crps: set[tuple[str, str]] = set()
    fonte_crp = None
    for url, html in paginas:
        bruto = unescape(html)
        for e in _EMAIL.findall(bruto.replace("mailto:", " ")):
            e = e.lower().rstrip(".")
            if e not in vistos and not e.endswith((".png", ".jpg", ".webp", ".gif", ".svg")):
                vistos.add(e)
                ficha.emails.append(Fato(e, url))
        if ficha.whatsapp is None and (m := _WHATSAPP.search(bruto)):
            ficha.whatsapp = Fato(m.group(1), url)
        if ficha.agendamento_online is None and (m := _AGENDA.search(bruto)):
            ficha.agendamento_online = Fato(m.group(0).lower(), url)
        novos = {(r, n) for r, n in _CRP.findall(bruto)}
        if novos - crps and fonte_crp is None:
            fonte_crp = url
        crps |= novos
    if crps:
        ficha.psicologos_crp = Fato(len(crps), fonte_crp or ficha.paginas[0])
    return ficha


_PROMPT = """Você lê o site de uma clínica de psicologia e devolve JSON com dois campos.
Só use o que está no texto abaixo. Não invente. Se não souber, deixe o valor vazio.

- "o_que_faz": uma frase curta, factual, do que a clínica oferece (ex.: "psicoterapia
  para adultos e casais, presencial e online").
- "gancho": uma observação específica e verdadeira sobre a clínica, útil para abrir um
  e-mail curto sobre o atendimento no WhatsApp (ex.: "o site pede para marcar pelo
  WhatsApp, sem horário de atendimento informado"). Nada de elogio genérico.
- "fonte": a URL, da lista abaixo, de onde tirou os dois.

URLs lidas:
{urls}

Texto do site:
{texto}

Responda só o JSON: {{"o_que_faz": "...", "gancho": "...", "fonte": "..."}}"""


_SCHEMA = {
    "type": "object",
    "properties": {
        "o_que_faz": {"type": "string"},
        "gancho": {"type": "string"},
        "fonte": {"type": "string"},
    },
    "required": ["o_que_faz", "gancho", "fonte"],
}


async def resumir(ficha: Ficha, paginas: list[tuple[str, str]], *, alvo_ref: str | None = None) -> None:
    """Preenche `o_que_faz` e `gancho` pela IA. Falhou ou sem fonte válida: vazio."""
    texto = " ".join(_texto(h) for _, h in paginas)[:MAX_TEXTO_IA]
    if not texto:
        return
    try:
        r = await gateway.gerar(
            _PROMPT.format(urls="\n".join(ficha.paginas), texto=texto),
            tarefa="extrair",
            agente=AGENTE,
            json_schema=_SCHEMA,
            alvo_ref=alvo_ref,
        )
    except LLMErro as e:
        logger.warning(f"Pesquisador: IA indisponível, ficha sem resumo ({e})")
        return
    dados = r.json if isinstance(r.json, dict) else {}
    lidas = {u.rstrip("/"): u for u in ficha.paginas}
    fonte = lidas.get(str(dados.get("fonte") or "").strip().rstrip("/"))
    if fonte is None:
        return  # sem fonte que eu li, não entra
    for campo in ("o_que_faz", "gancho"):
        valor = str(dados.get(campo) or "").strip()
        if valor:
            setattr(ficha, campo, Fato(valor[:300], fonte))


def parece_da_clinica(paginas: list[tuple[str, str]]) -> bool:
    """O texto fala de psicologia? Senão, o site é de outra pessoa (contador, agência)."""
    return any(_PSICOLOGIA.search(_texto(h)) for _, h in paginas)


def _legivel(ficha: Ficha, email: str | None, confirmado: bool, da_clinica: bool = True) -> str:
    motivo = {
        "completo": "parou ao achar tudo",
        "teto": f"parou no teto de {varredura.MAX_PAGINAS} páginas",
        "acabaram as páginas": "leu o site inteiro",
    }.get(ficha.parou_porque, ficha.parou_porque)
    js = f"; {len(ficha.com_javascript)} com JavaScript (navegador)" if ficha.com_javascript else ""
    linhas = [f"Ficha de {ficha.site}: {len(ficha.paginas)} página(s) lida(s), {motivo}{js}."]
    if not da_clinica:
        linhas.append("ATENÇÃO: o site não fala de psicologia. Não parece ser da clínica (contador? agência?).")
    if ficha.o_que_faz:
        linhas.append(f"O que faz: {ficha.o_que_faz.valor}")
    if ficha.psicologos_crp:
        linhas.append(f"Psicólogos com CRP no site: {ficha.psicologos_crp.valor}")
    linhas.append(f"Agendamento online: {'sim (' + str(ficha.agendamento_online.valor) + ')' if ficha.agendamento_online else 'não achei'}")
    linhas.append(f"WhatsApp publicado: {'sim' if ficha.whatsapp else 'não achei'}")
    linhas.append(
        f"E-mail: {email} ({'confirmado no site' if confirmado else 'NÃO confirmado no site: não enviar'})"
        if email else "E-mail: nenhum confirmado no site"
    )
    if ficha.gancho:
        linhas.append(f"Gancho: {ficha.gancho.valor}")
    return "\n".join(linhas)


async def pesquisar(
    session: AsyncSession,
    lead_id: int,
    *,
    site: str | None = None,
    cliente: httpx.AsyncClient | None = None,
    navegador: varredura.Navegador | None = None,
    usar_ia: bool = True,
    hoje: date | None = None,
) -> Resultado:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise leads.CrmErro(f"lead {lead_id} não existe")
    alvo = site or lead.site or site_provavel(lead.email)
    if not alvo:
        lead.proxima_acao = "sem site: cole o endereço da clínica e pesquise de novo"
        await session.commit()
        return Resultado("sem_site", mensagem="Não achei o site: o e-mail da base é de provedor gratuito. Cole o endereço da clínica.")

    v = await varredura.varrer(
        alvo, lambda paginas: extrair(alvo, paginas).completa(), cliente=cliente, navegador=navegador
    )
    paginas = v.paginas
    if not paginas:
        lead.proxima_acao = f"o site {alvo} não abriu (ou o robots.txt não deixa): conferir à mão"
        await session.commit()
        return Resultado("site_fora", mensagem=f"Não consegui ler {alvo}.")

    ficha = extrair(alvo, paginas)
    ficha.com_javascript, ficha.parou_porque = v.com_javascript, v.parou_porque
    da_clinica = parece_da_clinica(paginas)
    if usar_ia and da_clinica:
        await resumir(ficha, paginas, alvo_ref=f"comercial_lead:{lead.id}")

    # A regra do §4: vale o e-mail que a clínica publica, e só ele.
    publicados = {f.valor: f.fonte for f in ficha.emails}
    confirmado = False
    if not da_clinica:
        lead.email_fonte = None
    elif lead.email and lead.email in publicados:
        lead.email_fonte, confirmado = publicados[lead.email], True
    else:
        # O domínio da própria clínica primeiro: o site pode mostrar o e-mail da
        # agência que o fez, e esse não é da clínica.
        dominio = urlparse(ficha.site).netloc.removeprefix("www.")
        candidatos = sorted(ficha.emails, key=lambda f: not str(f.valor).endswith("@" + dominio))
        for f in candidatos:
            if not await leads.suprimido(session, email=str(f.valor), telefone=None):
                lead.email, lead.email_fonte, confirmado = str(f.valor), f.fonte, True
                break
        else:
            lead.email_fonte = None

    if da_clinica:
        lead.site = ficha.site
    lead.pesquisado_em = datetime.now(UTC)
    session.add(
        Interacao(
            lead_id=lead.id, canal=Canal.NOTA.value, direcao=Direcao.INTERNA.value,
            tipo="ficha", texto=_legivel(ficha, lead.email, confirmado, da_clinica),
            dados=json.loads(json.dumps(ficha.para_json())),
        )
    )
    abertas = list(
        await session.scalars(
            select(Tarefa).where(
                Tarefa.lead_id == lead.id, Tarefa.tipo == TipoTarefa.PESQUISAR.value, Tarefa.feita_em.is_(None)
            )
        )
    )
    if confirmado:
        for t in abertas:
            t.feita_em = datetime.now(UTC)
        session.add(Tarefa(lead_id=lead.id, tipo=TipoTarefa.ESCREVER_EMAIL.value, vence_em=hoje or date.today()))
        lead.proxima_acao = "escrever o e-mail 1"
    elif not da_clinica:
        lead.proxima_acao = f"{ficha.site} não parece ser da clínica (não fala de psicologia): achar o site certo"
    else:
        lead.proxima_acao = "nenhum e-mail confirmado no site: achar o contato à mão ou descartar"
    await session.commit()
    if not da_clinica:
        return Resultado(
            "nao_e_da_clinica", ficha=ficha,
            mensagem=f"{ficha.site} não fala de psicologia: não parece ser o site da clínica. Cole o endereço certo.",
        )
    return Resultado("ok", ficha=ficha, email_confirmado=confirmado)
