"""Fonte CNES: a API aberta do Ministério da Saúde → `Registro`.

Clínica e consultório são os tipos de unidade 36 e 22 (1.2.1 §2.3). Entram só
os **ativos**, os sem motivo de desabilitação; quem some da API vira inativo
pela regra das duas importações.

A API devolve no máximo 20 registros por página, não informa o total e às
vezes repete registro entre páginas. Por isso: pagina até uma página vir
incompleta, poucas conexões ao mesmo tempo, retry com espera e dedup pelo
código CNES.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx

from app.comercial.prospeccao import normalizacao as n
from app.comercial.prospeccao.importacao import Registro, hash_payload
from app.db.models.comercial.prospeccao import Nicho, Situacao, TipoIdentificador

URL = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
POR_PAGINA = 20
CONEXOES = 4
TENTATIVAS = 4

SEGMENTOS = {22: "consultorio_isolado", 36: "clinica_especialidade"}


def _texto(valor) -> str | None:
    v = (str(valor).strip() if valor is not None else "") or None
    return v


def _coordenada(valor) -> Decimal | None:
    return Decimal(str(round(valor, 6))) if isinstance(valor, int | float) else None


def para_registro(bruto: dict, ddd_padrao: str | None = None) -> Registro:
    cnes = str(bruto["codigo_cnes"]).zfill(7)
    cnpj = n.so_digitos(bruto.get("numero_cnpj"))
    identificadores = [(TipoIdentificador.CNES, cnes)]
    if len(cnpj) == 14:
        identificadores.append((TipoIdentificador.CNPJ, cnpj))
    canais = [
        c
        for c in (
            n.telefone(bruto.get("numero_telefone_estabelecimento") or "", ddd_padrao),
            n.email(bruto.get("endereco_email_estabelecimento") or ""),
        )
        if c is not None
    ]
    uf = n.UF_POR_CODIGO.get(str(bruto.get("codigo_uf") or ""))
    return Registro(
        id_na_fonte=cnes,
        hash_payload=hash_payload(bruto),
        identificadores=identificadores,
        nicho=Nicho.CLINICA,
        segmento=SEGMENTOS.get(bruto.get("codigo_tipo_unidade")),
        pessoa_fisica=len(cnpj) != 14,
        situacao=Situacao.INATIVO if bruto.get("codigo_motivo_desabilitacao_estabelecimento") else Situacao.ATIVO,
        nome_fantasia=_texto(bruto.get("nome_fantasia")),
        razao_social=_texto(bruto.get("nome_razao_social")),
        atende_sus=(bruto.get("estabelecimento_faz_atendimento_ambulatorial_sus") == "SIM"),
        municipio_ibge=n.municipio_ibge(bruto.get("codigo_municipio") or ""),
        uf=uf,
        bairro=_texto(bruto.get("bairro_estabelecimento")),
        cep=n.cep(bruto.get("codigo_cep_estabelecimento")),
        logradouro=_texto(bruto.get("endereco_estabelecimento")),
        numero=_texto(bruto.get("numero_estabelecimento")),
        latitude=_coordenada(bruto.get("latitude_estabelecimento_decimo_grau")),
        longitude=_coordenada(bruto.get("longitude_estabelecimento_decimo_grau")),
        canais=canais,
    )


async def _pagina(cliente: httpx.AsyncClient, municipio: str, tipo: int, offset: int) -> list[dict]:
    params = {"codigo_municipio": municipio, "codigo_tipo_unidade": tipo, "limit": POR_PAGINA, "offset": offset}
    for tentativa in range(TENTATIVAS):
        try:
            resp = await cliente.get(URL, params=params)
            resp.raise_for_status()
            return resp.json()["estabelecimentos"]
        except (httpx.HTTPError, KeyError, ValueError):
            if tentativa == TENTATIVAS - 1:
                raise
            await asyncio.sleep(2 * (tentativa + 1))
    return []


async def buscar(municipio: str, tipos: tuple[int, ...], ddd_padrao: str | None = None) -> AsyncIterator[Registro]:
    """Registros ativos do município, sem repetição, na ordem em que chegam."""
    vistos: set[str] = set()
    async with httpx.AsyncClient(timeout=60) as cliente:
        for tipo in tipos:
            offset = 0
            while True:
                offsets = [offset + POR_PAGINA * k for k in range(CONEXOES * 2)]
                paginas = await asyncio.gather(*(_pagina(cliente, municipio, tipo, o) for o in offsets))
                for pagina in paginas:
                    for bruto in pagina:
                        r = para_registro(bruto, ddd_padrao)
                        if r.id_na_fonte in vistos or r.situacao != Situacao.ATIVO:
                            continue
                        vistos.add(r.id_na_fonte)
                        yield r
                if any(len(p) < POR_PAGINA for p in paginas):
                    break
                offset = offsets[-1] + POR_PAGINA
