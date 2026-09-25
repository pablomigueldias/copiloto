"""Conversas-tipo: o conjunto de teste dos atendentes.

As falas do atendente são a resposta de referência. As regras rodam sobre elas
hoje, para a referência não ensinar o erro, e sobre as respostas do bot depois.

Regra com padrão em `PADROES` é verificada por regex, que não varia como um
juiz LLM. As outras ("avaliou sintoma") não cabem num regex: ficam declaradas
para o juiz LLM e a revisão humana.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

PASTA = Path(__file__).resolve().parents[2] / "data" / "comercial" / "conversas"

MAX_LINHAS_POR_MENSAGEM = 3


class Atendente(StrEnum):
    CLIENTE = "cliente"  # instalado no cliente
    PROPRIO = "proprio"  # bot comercial, no número do Pablo


class Nicho(StrEnum):
    CLINICA = "clinica"
    ADVOCACIA = "advocacia"
    IMOBILIARIA = "imobiliaria"


class Papel(StrEnum):
    PESSOA = "pessoa"
    ATENDENTE = "atendente"


class TipoVariacao(StrEnum):
    PARAFRASE = "parafrase"
    DIGITACAO = "digitacao"
    AUDIO = "audio"
    DESVIO = "desvio"  # tenta tirar o atendente da regra
    PERFIL = "perfil"  # outra profissão ou negócio no mesmo nicho
    MULTIPLA = "multipla"
    INSISTENCIA = "insistencia"


class Acao(StrEnum):
    AGENDAR = "agendar"
    REMARCAR = "remarcar"
    CANCELAR = "cancelar"
    PEDIR_OPTIN = "pedir_optin"
    PASSAR_HUMANO = "passar_humano"
    PASSAR_PRIORIDADE = "passar_prioridade"
    ALERTA_IMEDIATO = "alerta_imediato"
    REGISTRAR_OPTOUT = "registrar_optout"
    OPTOUT_CENTRAL = "optout_central"
    CRIAR_TAREFA = "criar_tarefa"
    ABRIR_CHAMADO = "abrir_chamado"
    ANEXAR_DOCUMENTO = "anexar_documento"
    DESCARTAR_ANEXO = "descartar_anexo"
    REGISTRAR_LEAD = "registrar_lead"
    DISTRIBUIR = "distribuir"
    AVISAR_GESTOR = "avisar_gestor"
    MARCAR_PERDIDO = "marcar_perdido"
    AGENDAR_REUNIAO = "agendar_reuniao"
    AVISAR_PABLO = "avisar_pablo"
    LEMBRETE_UNICO = "lembrete_unico"  # no máximo um por janela (06 §5, §7)
    PAUSAR = "pausar"
    NENHUMA = "nenhuma"


class Regra(StrEnum):
    PROMETER = "prometer"
    FALAR_PRECO = "falar_preco"
    DESCONTO = "desconto"
    VOCABULARIO_CONSUMO = "vocabulario_consumo"
    FINGIR_HUMANO = "fingir_humano"
    AVALIAR_SINTOMA = "avaliar_sintoma"
    ORIENTAR_JURIDICO = "orientar_juridico"
    INFORMAR_SEM_VERIFICAR = "informar_sem_verificar"
    INSISTIR_APOS_NAO = "insistir_apos_nao"
    INVENTAR = "inventar"  # integração, plano, disponibilidade, case
    PEDIR_DADO_DESNECESSARIO = "pedir_dado_desnecessario"
    FALAR_MAL_CONCORRENTE = "falar_mal_concorrente"


# Voz do bot comercial (06): nunca "garanto", "100%", nem fingir ser o Pablo.
SEMPRE_PROIBIDO = (Regra.PROMETER, Regra.FINGIR_HUMANO)

PADROES: dict[Regra, re.Pattern[str]] = {
    Regra.PROMETER: re.compile(
        r"\bgaranto\b|\bgarantid[oa]\b|\b100 ?%|com certeza vai|vai ganhar|\bchance de ganhar",
        re.IGNORECASE,
    ),
    Regra.FALAR_PRECO: re.compile(r"R\$ ?\d|\breais\b|\bvalor é\b|\bcusta\b", re.IGNORECASE),
    Regra.DESCONTO: re.compile(r"\bdesconto\b|\bpromo[çc][ãa]o\b|\bmais barato\b", re.IGNORECASE),
    Regra.VOCABULARIO_CONSUMO: re.compile(r"\blead\b|\bfunil\b|\bconsumidor\b", re.IGNORECASE),
    Regra.FINGIR_HUMANO: re.compile(
        r"\b(sou|aqui é) o pablo\b|\bsou (uma )?pessoa\b|\bnão sou (um )?rob[ôo]\b",
        re.IGNORECASE,
    ),
}

_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_TELEFONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


class Turno(BaseModel):
    model_config = ConfigDict(extra="forbid")

    papel: Papel
    texto: str = Field(min_length=1)


class Esperado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acoes: list[Acao] = Field(min_length=1)
    nao_pode: list[Regra] = Field(default_factory=list)
    estado_final: str | None = None
    # Bot próprio: dados preenchidos e a temperatura que `funil.temperatura` dá.
    dados: dict[str, str | int] = Field(default_factory=dict)
    quer_agendar: bool = False
    temperatura: str | None = None


class Conversa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[CAIP]\d{2}(-v\d{2})?$")
    atendente: Atendente
    nicho: Nicho | None  # None: bot próprio antes de saber o nicho
    perfil: str | None = None  # C-1, A-2, I-3… do 1.2.7
    titulo: str
    config: dict[str, str] = Field(default_factory=dict)  # ex.: profissao=dentista
    base: list[str] = Field(min_length=1)  # IDs das fontes do 1.2.1–1.2.6
    testa: str
    caso_de_borda: bool = False
    sintetica: bool = False
    variacao_de: str | None = None
    tipo_variacao: TipoVariacao | None = None
    turnos: list[Turno] = Field(min_length=2)
    esperado: Esperado

    @model_validator(mode="after")
    def _coerente(self) -> Conversa:
        if self.sintetica != (self.variacao_de is not None):
            raise ValueError(f"{self.id}: sintética precisa de variacao_de, e só ela")
        if self.sintetica != (self.tipo_variacao is not None):
            raise ValueError(f"{self.id}: tipo_variacao só em conversa sintética")
        if self.turnos[0].papel is not Papel.PESSOA:
            raise ValueError(f"{self.id}: quem começa é a pessoa (o atendente não inicia conversa)")
        if not any(t.papel is Papel.ATENDENTE for t in self.turnos):
            raise ValueError(f"{self.id}: sem fala do atendente não há o que testar")
        return self

    def falas_do_atendente(self) -> list[str]:
        return [t.texto for t in self.turnos if t.papel is Papel.ATENDENTE]

    def regras(self) -> list[Regra]:
        """O que a conversa proíbe, mais o que vem do nicho sem precisar marcar:
        escritório nunca usa vocabulário de consumo (1.2.3, A9); dentista nunca
        fala preço (CFO, art. 44, I)."""
        herdadas: list[Regra] = list(SEMPRE_PROIBIDO)
        if self.nicho is Nicho.ADVOCACIA:
            herdadas.append(Regra.VOCABULARIO_CONSUMO)
        if self.config.get("profissao") == "dentista":
            herdadas.append(Regra.FALAR_PRECO)
        return list(dict.fromkeys([*herdadas, *self.esperado.nao_pode]))

    def regras_de_texto(self) -> list[Regra]:
        return [r for r in self.regras() if r in PADROES]


def violacoes(conversa: Conversa, falas: Iterable[str] | None = None) -> list[str]:
    """O que as falas quebram. Sem `falas`, verifica a própria referência; com
    elas, as respostas do bot."""
    falas = list(conversa.falas_do_atendente() if falas is None else falas)
    erros: list[str] = []
    for i, fala in enumerate(falas):
        for regra in conversa.regras_de_texto():
            achado = PADROES[regra].search(fala)
            if achado:
                erros.append(f"{conversa.id} fala {i}: {regra} ({achado.group(0)!r})")
        linhas = [linha for linha in fala.splitlines() if linha.strip()]
        if len(linhas) > MAX_LINHAS_POR_MENSAGEM:
            erros.append(f"{conversa.id} fala {i}: {len(linhas)} linhas")
    return erros


def dado_pessoal(conversa: Conversa) -> list[str]:
    """CPF, telefone ou e-mail em qualquer turno. Placeholder `{assim}` passa."""
    achados = []
    for t in conversa.turnos:
        for nome, padrao in (("cpf", _CPF), ("telefone", _TELEFONE), ("email", _EMAIL)):
            if padrao.search(t.texto):
                achados.append(f"{conversa.id}: {nome} em {t.texto[:40]!r}")
    return achados


def carregar(pasta: Path = PASTA) -> list[Conversa]:
    conversas: list[Conversa] = []
    for arquivo in sorted(pasta.glob("*.json")):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        conversas.extend(Conversa.model_validate(c) for c in dados["conversas"])
    return conversas
