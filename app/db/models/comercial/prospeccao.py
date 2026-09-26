"""Base de prospecção: o universo de negócios públicos, um fato por linha.

Especificação em `docs/motor-comercial/fase-0/base-prospeccao.md` (D9). Três
regras moldam as tabelas:

- **Atômico.** Telefone, e-mail, CNPJ e CNAE são linhas, não colunas nem JSON.
  É o que deixa responder "de onde veio este telefone?" e apagar só ele.
- **Proveniência.** `prospeccao_origem` liga cada linha à fonte e à importação
  que a trouxe, com o hash do registro na fonte. O payload bruto não é
  guardado (LGPD, dado mínimo).
- **Supressão vence importação.** `prospeccao_supressao` guarda só o hash do
  valor: quem pediu para sair continua bloqueado sem que o dado dele fique.

Estabelecimento não é lead. O CRM da Fase 1 aponta para cá; aqui não entra
conversa, estágio nem nota comercial.

Desvio da especificação: `prospeccao_atividade` ganhou `id` próprio. A
especificação dava PK composta, mas `prospeccao_origem.entidade_id` precisa de
um id único para apontar para a atividade.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Nicho(StrEnum):
    CLINICA = "clinica"
    ADVOCACIA = "advocacia"
    IMOBILIARIA = "imobiliaria"


class Situacao(StrEnum):
    ATIVO = "ativo"
    INATIVO = "inativo"


class StatusImportacao(StrEnum):
    RODANDO = "rodando"
    OK = "ok"
    FALHOU = "falhou"


class TipoIdentificador(StrEnum):
    CNES = "cnes"
    CNPJ = "cnpj"


class TipoCanal(StrEnum):
    TELEFONE = "telefone"
    CELULAR = "celular"
    EMAIL = "email"
    SITE = "site"


class Entidade(StrEnum):
    ESTABELECIMENTO = "estabelecimento"
    CANAL = "canal"
    ATIVIDADE = "atividade"
    IDENTIFICADOR = "identificador"


class TipoSupressao(StrEnum):
    TELEFONE = "telefone"  # vale para telefone e celular
    EMAIL = "email"
    CNPJ = "cnpj"
    CNES = "cnes"


class MotivoSupressao(StrEnum):
    OPTOUT = "optout"
    PEDIDO_TITULAR = "pedido_titular"
    ERRO = "erro"
    NAO_E_ALVO = "nao_e_alvo"


def _check(coluna: str, enum: type[StrEnum], nome: str) -> CheckConstraint:
    valores = ", ".join(f"'{v.value}'" for v in enum)
    return CheckConstraint(f"{coluna} IN ({valores})", name=nome)


def _agora() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Fonte(Base):
    __tablename__ = "prospeccao_fonte"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    licenca: Mapped[str] = mapped_column(Text, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)


class Importacao(Base):
    __tablename__ = "prospeccao_importacao"
    __table_args__ = (_check("status", StatusImportacao, "ck_prospeccao_importacao_status"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    fonte_id: Mapped[int] = mapped_column(ForeignKey("prospeccao_fonte.id"), nullable=False)
    parametros: Mapped[dict] = mapped_column(JSONB, nullable=False)
    iniciada_em: Mapped[datetime] = _agora()
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inseridos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    atualizados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sem_mudanca: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marcados_inativos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    suprimidos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    erro: Mapped[str | None] = mapped_column(Text)


class Estabelecimento(Base):
    __tablename__ = "prospeccao_estabelecimento"
    __table_args__ = (
        _check("nicho", Nicho, "ck_prospeccao_estabelecimento_nicho"),
        _check("situacao", Situacao, "ck_prospeccao_estabelecimento_situacao"),
        Index("ix_prospeccao_estabelecimento_busca", "nicho", "situacao", "municipio_ibge"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nicho: Mapped[str] = mapped_column(String(20), nullable=False)
    segmento: Mapped[str | None] = mapped_column(String(40))
    nome_fantasia: Mapped[str | None] = mapped_column(Text)
    razao_social: Mapped[str | None] = mapped_column(Text)
    # Sem CNPJ, empresário individual ou MEI: a pessoa é o negócio, e a LGPD
    # pesa mais. Não entra em e-mail frio sem revisão manual.
    pessoa_fisica: Mapped[bool] = mapped_column(Boolean, nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False)
    atende_sus: Mapped[bool | None] = mapped_column(Boolean)
    municipio_ibge: Mapped[str | None] = mapped_column(String(7))
    uf: Mapped[str | None] = mapped_column(String(2))
    bairro: Mapped[str | None] = mapped_column(Text)
    cep: Mapped[str | None] = mapped_column(String(8))
    logradouro: Mapped[str | None] = mapped_column(Text)
    numero: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    inativo_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _agora()
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Identificador(Base):
    __tablename__ = "prospeccao_identificador"
    __table_args__ = (
        UniqueConstraint("tipo", "valor", name="ux_prospeccao_identificador_tipo_valor"),
        _check("tipo", TipoIdentificador, "ck_prospeccao_identificador_tipo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("prospeccao_estabelecimento.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    valor: Mapped[str] = mapped_column(String(20), nullable=False)


class Atividade(Base):
    __tablename__ = "prospeccao_atividade"
    __table_args__ = (
        UniqueConstraint("estabelecimento_id", "cnae_subclasse", name="ux_prospeccao_atividade"),
        CheckConstraint("cnae_subclasse ~ '^[0-9]{7}$'", name="ck_prospeccao_atividade_cnae"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("prospeccao_estabelecimento.id", ondelete="CASCADE"), nullable=False
    )
    cnae_subclasse: Mapped[str] = mapped_column(String(7), nullable=False)
    principal: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Canal(Base):
    __tablename__ = "prospeccao_canal"
    __table_args__ = (
        UniqueConstraint("estabelecimento_id", "tipo", "valor", name="ux_prospeccao_canal"),
        _check("tipo", TipoCanal, "ck_prospeccao_canal_tipo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    estabelecimento_id: Mapped[int] = mapped_column(
        ForeignKey("prospeccao_estabelecimento.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    valor_original: Mapped[str] = mapped_column(Text, nullable=False)
    valido: Mapped[bool] = mapped_column(Boolean, nullable=False)


class Origem(Base):
    __tablename__ = "prospeccao_origem"
    __table_args__ = (
        UniqueConstraint("entidade", "entidade_id", "fonte_id", name="ux_prospeccao_origem"),
        _check("entidade", Entidade, "ck_prospeccao_origem_entidade"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    entidade: Mapped[str] = mapped_column(String(20), nullable=False)
    entidade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fonte_id: Mapped[int] = mapped_column(ForeignKey("prospeccao_fonte.id"), nullable=False)
    id_na_fonte: Mapped[str] = mapped_column(String(20), nullable=False)
    primeira_importacao_id: Mapped[int] = mapped_column(
        ForeignKey("prospeccao_importacao.id"), nullable=False
    )
    ultima_importacao_id: Mapped[int] = mapped_column(
        ForeignKey("prospeccao_importacao.id"), nullable=False
    )
    visto_primeiro_em: Mapped[datetime] = _agora()
    visto_ultimo_em: Mapped[datetime] = _agora()
    hash_payload: Mapped[str | None] = mapped_column(String(64))


class Supressao(Base):
    __tablename__ = "prospeccao_supressao"
    __table_args__ = (
        UniqueConstraint("tipo", "valor_hash", name="ux_prospeccao_supressao"),
        _check("tipo", TipoSupressao, "ck_prospeccao_supressao_tipo"),
        _check("motivo", MotivoSupressao, "ck_prospeccao_supressao_motivo"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    valor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)
    criado_em: Mapped[datetime] = _agora()
