"""Importação: o mesmo núcleo para qualquer fonte.

A fonte (CNES, Receita) só transforma o registro dela num `Registro`. Daqui
para baixo é igual para todas:

1. **Idempotência** pelo identificador na fonte. Rodar de novo com o mesmo dado
   dá zero inseridos e zero atualizados; quem decide se mudou é o hash do
   registro original, guardado em `prospeccao_origem`.
2. **Cruzamento entre fontes** pelo `unique (tipo, valor)` do identificador: o
   CNPJ que veio do CNES e o mesmo CNPJ vindo da Receita caem no mesmo
   estabelecimento.
3. **Supressão vence importação**: identificador ou canal cujo hash está em
   `prospeccao_supressao` não entra, e conta em `suprimidos`.
4. **Inativo só depois de sumir duas vezes** (retenção da especificação): uma
   página que a API não devolveu não pode apagar ninguém. Só importações `ok` e
   com os mesmos parâmetros contam, e nada é marcado se a importação falhar.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, delete, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.comercial.prospeccao.normalizacao import Normalizado, hash_valor
from app.db.models.comercial.prospeccao import (
    Atividade,
    Canal,
    Entidade,
    Estabelecimento,
    Fonte,
    Identificador,
    Importacao,
    Origem,
    Situacao,
    StatusImportacao,
    Supressao,
    TipoCanal,
    TipoIdentificador,
    TipoSupressao,
)

LOTE = 500
IMPORTACOES_PARA_INATIVAR = 2

CAMPOS = (
    "nicho", "segmento", "nome_fantasia", "razao_social", "pessoa_fisica", "situacao",
    "atende_sus", "municipio_ibge", "uf", "bairro", "cep", "logradouro", "numero",
    "latitude", "longitude",
)


@dataclass(slots=True)
class Registro:
    """Um estabelecimento como a fonte o descreve, já normalizado."""

    id_na_fonte: str
    hash_payload: str
    identificadores: list[tuple[TipoIdentificador, str]]
    nicho: str
    pessoa_fisica: bool
    situacao: str = Situacao.ATIVO
    segmento: str | None = None
    nome_fantasia: str | None = None
    razao_social: str | None = None
    atende_sus: bool | None = None
    municipio_ibge: str | None = None
    uf: str | None = None
    bairro: str | None = None
    cep: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    canais: list[Normalizado] = field(default_factory=list)
    atividades: list[tuple[str, bool]] = field(default_factory=list)  # (subclasse, principal)


def hash_payload(registro_bruto: dict) -> str:
    """sha256 do registro da fonte em JSON canônico. O registro em si não fica."""
    canonico = json.dumps(registro_bruto, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode()).hexdigest()


def tipo_supressao(tipo: TipoCanal | TipoIdentificador) -> TipoSupressao:
    if tipo in (TipoCanal.TELEFONE, TipoCanal.CELULAR):
        return TipoSupressao.TELEFONE
    return TipoSupressao(tipo.value)


class _Importador:
    def __init__(self, session: AsyncSession, fonte: Fonte, imp: Importacao, suprimidos: set[tuple[str, str]]):
        self.s = session
        self.fonte = fonte
        self.imp = imp
        self.suprimidos = suprimidos
        self.agora = datetime.now(UTC)

    def _suprimido(self, tipo: TipoCanal | TipoIdentificador, valor: str) -> bool:
        return (tipo_supressao(tipo).value, hash_valor(valor)) in self.suprimidos

    async def _origem(self, entidade: Entidade, entidade_id: int, id_na_fonte: str, hash_: str | None = None) -> None:
        existente = await self.s.scalar(
            select(Origem).where(
                Origem.entidade == entidade, Origem.entidade_id == entidade_id, Origem.fonte_id == self.fonte.id
            )
        )
        if existente:
            existente.ultima_importacao_id = self.imp.id
            existente.visto_ultimo_em = self.agora
            if hash_ is not None:
                existente.hash_payload = hash_
            return
        self.s.add(
            Origem(
                entidade=entidade, entidade_id=entidade_id, fonte_id=self.fonte.id, id_na_fonte=id_na_fonte,
                primeira_importacao_id=self.imp.id, ultima_importacao_id=self.imp.id,
                visto_primeiro_em=self.agora, visto_ultimo_em=self.agora, hash_payload=hash_,
            )
        )

    async def registro(self, r: Registro) -> None:
        self.imp.lidos += 1
        if any(self._suprimido(t, v) for t, v in r.identificadores):
            self.imp.suprimidos += 1
            return

        est_id = await self.s.scalar(
            select(Identificador.estabelecimento_id).where(
                tuple_(Identificador.tipo, Identificador.valor).in_([(t.value, v) for t, v in r.identificadores])
            )
        )
        if est_id is not None:
            origem = await self.s.scalar(
                select(Origem).where(
                    Origem.entidade == Entidade.ESTABELECIMENTO,
                    Origem.entidade_id == est_id,
                    Origem.fonte_id == self.fonte.id,
                )
            )
            if origem and origem.hash_payload == r.hash_payload:
                self.imp.sem_mudanca += 1
                await self._origem(Entidade.ESTABELECIMENTO, est_id, r.id_na_fonte)
                await self._reativar(est_id, r)
                await self.s.flush()
                return
            est = await self.s.get(Estabelecimento, est_id)
            for campo in CAMPOS:
                setattr(est, campo, getattr(r, campo))
            if r.situacao == Situacao.ATIVO:
                est.inativo_desde = None
            self.imp.atualizados += 1
        else:
            est = Estabelecimento(**{c: getattr(r, c) for c in CAMPOS})
            self.s.add(est)
            await self.s.flush()
            self.imp.inseridos += 1

        await self._origem(Entidade.ESTABELECIMENTO, est.id, r.id_na_fonte, r.hash_payload)
        await self._identificadores(est.id, r)
        await self._canais(est.id, r)
        await self._atividades(est.id, r)
        # A sessão da casa não faz autoflush: sem isto, a consulta de "quem
        # sumiu" lê a proveniência de antes desta importação.
        await self.s.flush()

    async def _reativar(self, est_id: int, r: Registro) -> None:
        if r.situacao == Situacao.ATIVO:
            await self.s.execute(
                update(Estabelecimento)
                .where(Estabelecimento.id == est_id, Estabelecimento.situacao == Situacao.INATIVO)
                .values(situacao=Situacao.ATIVO, inativo_desde=None)
            )

    async def _identificadores(self, est_id: int, r: Registro) -> None:
        for tipo, valor in r.identificadores:
            ident = await self.s.scalar(
                select(Identificador).where(Identificador.tipo == tipo, Identificador.valor == valor)
            )
            if ident is None:
                ident = Identificador(estabelecimento_id=est_id, tipo=tipo, valor=valor)
                self.s.add(ident)
                await self.s.flush()
            await self._origem(Entidade.IDENTIFICADOR, ident.id, r.id_na_fonte)

    async def _desta_fonte(self, entidade: Entidade, modelo, est_id: int) -> dict[int, object]:
        """Linhas do estabelecimento que só esta fonte sustenta — as que ela pode tirar."""
        outras = select(Origem.entidade_id).where(Origem.entidade == entidade, Origem.fonte_id != self.fonte.id)
        linhas = await self.s.scalars(
            select(modelo)
            .join(Origem, and_(Origem.entidade == entidade, Origem.entidade_id == modelo.id))
            .where(modelo.estabelecimento_id == est_id, Origem.fonte_id == self.fonte.id, modelo.id.not_in(outras))
        )
        return {linha.id: linha for linha in linhas}

    async def _apagar(self, entidade: Entidade, modelo, ids: Iterable[int]) -> None:
        ids = list(ids)
        if ids:
            await self.s.execute(delete(Origem).where(Origem.entidade == entidade, Origem.entidade_id.in_(ids)))
            await self.s.execute(delete(modelo).where(modelo.id.in_(ids)))

    async def _canais(self, est_id: int, r: Registro) -> None:
        sumiram = await self._desta_fonte(Entidade.CANAL, Canal, est_id)
        for n in r.canais:
            if self._suprimido(n.tipo, n.valor):
                self.imp.suprimidos += 1
                continue
            canal = await self.s.scalar(
                select(Canal).where(Canal.estabelecimento_id == est_id, Canal.tipo == n.tipo, Canal.valor == n.valor)
            )
            if canal is None:
                canal = Canal(
                    estabelecimento_id=est_id, tipo=n.tipo, valor=n.valor, valor_original=n.original, valido=n.valido
                )
                self.s.add(canal)
                await self.s.flush()
            sumiram.pop(canal.id, None)
            await self._origem(Entidade.CANAL, canal.id, r.id_na_fonte)
        await self._apagar(Entidade.CANAL, Canal, sumiram)

    async def _atividades(self, est_id: int, r: Registro) -> None:
        sumiram = await self._desta_fonte(Entidade.ATIVIDADE, Atividade, est_id)
        for subclasse, principal in r.atividades:
            ativ = await self.s.scalar(
                select(Atividade).where(Atividade.estabelecimento_id == est_id, Atividade.cnae_subclasse == subclasse)
            )
            if ativ is None:
                ativ = Atividade(estabelecimento_id=est_id, cnae_subclasse=subclasse, principal=principal)
                self.s.add(ativ)
                await self.s.flush()
            else:
                ativ.principal = principal
            sumiram.pop(ativ.id, None)
            await self._origem(Entidade.ATIVIDADE, ativ.id, r.id_na_fonte)
        await self._apagar(Entidade.ATIVIDADE, Atividade, sumiram)

    async def inativar_sumidos(self) -> None:
        recentes = (
            await self.s.scalars(
                select(Importacao.id)
                .where(
                    Importacao.fonte_id == self.fonte.id,
                    Importacao.parametros == self.imp.parametros,
                    Importacao.status == StatusImportacao.OK,
                )
                .order_by(Importacao.id.desc())
                .limit(IMPORTACOES_PARA_INATIVAR - 1)
            )
        ).all()
        janela = [self.imp.id, *recentes]
        if len(janela) < IMPORTACOES_PARA_INATIVAR:
            return
        sumidos = select(Origem.entidade_id).where(
            Origem.entidade == Entidade.ESTABELECIMENTO,
            Origem.fonte_id == self.fonte.id,
            Origem.ultima_importacao_id.not_in(janela),
            Origem.primeira_importacao_id.in_(
                select(Importacao.id).where(
                    Importacao.fonte_id == self.fonte.id, Importacao.parametros == self.imp.parametros
                )
            ),
        )
        res = await self.s.execute(
            update(Estabelecimento)
            .where(Estabelecimento.id.in_(sumidos), Estabelecimento.situacao == Situacao.ATIVO)
            .values(situacao=Situacao.INATIVO, inativo_desde=self.agora)
        )
        self.imp.marcados_inativos = res.rowcount or 0


async def importar(
    session: AsyncSession,
    fonte_codigo: str,
    parametros: dict,
    registros: Iterable[Registro] | AsyncIterable[Registro],
) -> Importacao:
    """Roda uma importação inteira e devolve o registro dela, com os contadores."""
    fonte = await session.scalar(select(Fonte).where(Fonte.codigo == fonte_codigo))
    if fonte is None:
        raise ValueError(f"fonte desconhecida: {fonte_codigo}")
    imp = Importacao(
        fonte_id=fonte.id, parametros=parametros, status=StatusImportacao.RODANDO,
        lidos=0, inseridos=0, atualizados=0, sem_mudanca=0, marcados_inativos=0, suprimidos=0,
    )
    session.add(imp)
    await session.commit()
    imp_id = imp.id

    suprimidos = {(t, h) for t, h in (await session.execute(select(Supressao.tipo, Supressao.valor_hash))).all()}
    imp_ = _Importador(session, fonte, imp, suprimidos)
    try:
        if isinstance(registros, AsyncIterable):
            async for r in registros:
                await imp_.registro(r)
                if imp.lidos % LOTE == 0:
                    await session.commit()
        else:
            for r in registros:
                await imp_.registro(r)
                if imp.lidos % LOTE == 0:
                    await session.commit()
        await imp_.inativar_sumidos()
        imp.status = StatusImportacao.OK
    except Exception as exc:
        await session.rollback()
        imp = await session.get(Importacao, imp_id)
        imp.status = StatusImportacao.FALHOU
        imp.erro = f"{type(exc).__name__}: {exc}"[:2000]
        imp.concluida_em = func.now()
        await session.commit()
        raise
    imp.concluida_em = func.now()
    await session.commit()
    await session.refresh(imp)
    return imp
