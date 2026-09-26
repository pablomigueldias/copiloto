"""Importação contra o Postgres de verdade — o aceite do 1.2.9.

Registros inventados no formato da API do CNES e da Receita. O que se prova:
rodar duas vezes não duplica, o mesmo CNPJ de duas fontes vira um
estabelecimento, supressão vence importação, ninguém fica inativo por sumir uma
vez só, e uma importação que falha não inativa ninguém.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.comercial.prospeccao import cnes
from app.comercial.prospeccao.importacao import Registro, importar
from app.comercial.prospeccao.retencao import aplicar_retencao, suprimir
from app.db.models.comercial.prospeccao import (
    Canal,
    Entidade,
    Estabelecimento,
    Identificador,
    Importacao,
    MotivoSupressao,
    Nicho,
    Origem,
    Situacao,
    StatusImportacao,
    Supressao,
    TipoIdentificador,
    TipoSupressao,
)
from app.db.session import get_session

PARAMS = {"municipio": "355030", "tipos": [36, 22], "so_ativos": True}


def _cnes(codigo: int, **kw) -> dict:
    bruto = {
        "codigo_cnes": codigo,
        "numero_cnpj": None,
        "nome_razao_social": f"CLINICA EXEMPLO {codigo}",
        "nome_fantasia": f"Clínica Exemplo {codigo}",
        "codigo_tipo_unidade": 36,
        "codigo_cep_estabelecimento": "01001000",
        "endereco_estabelecimento": "RUA DO EXEMPLO",
        "numero_estabelecimento": "10",
        "bairro_estabelecimento": "CENTRO",
        "numero_telefone_estabelecimento": "(11) 3333-4444",
        "latitude_estabelecimento_decimo_grau": -23.5505,
        "longitude_estabelecimento_decimo_grau": -46.6333,
        "endereco_email_estabelecimento": f"contato{codigo}@exemplo.com.br",
        "estabelecimento_faz_atendimento_ambulatorial_sus": "NAO",
        "codigo_uf": 35,
        "codigo_municipio": 355030,
        "codigo_motivo_desabilitacao_estabelecimento": None,
    }
    bruto.update(kw)
    return bruto


def _registros(*brutos: dict) -> list[Registro]:
    return [cnes.para_registro(b, "11") for b in brutos]


async def _importar(*brutos: dict, fonte: str = "cnes", params=PARAMS) -> Importacao:
    async with get_session() as s:
        return await importar(s, fonte, params, _registros(*brutos))


async def _contar(modelo, *filtros) -> int:
    async with get_session() as s:
        return await s.scalar(select(func.count()).select_from(modelo).where(*filtros))


async def test_importar_duas_vezes_nao_duplica():
    primeira = await _importar(_cnes(1), _cnes(2))
    segunda = await _importar(_cnes(1), _cnes(2))

    assert (primeira.inseridos, primeira.lidos, primeira.status) == (2, 2, StatusImportacao.OK)
    assert (segunda.inseridos, segunda.atualizados, segunda.sem_mudanca) == (0, 0, 2)
    assert await _contar(Estabelecimento) == 2
    assert await _contar(Canal) == 4


async def test_proveniencia_diz_de_onde_veio_cada_linha():
    imp = await _importar(_cnes(1))
    async with get_session() as s:
        origens = (await s.scalars(select(Origem))).all()
    entidades = sorted(o.entidade for o in origens)
    assert entidades == ["canal", "canal", "estabelecimento", "identificador"]
    assert all(o.id_na_fonte == "0000001" and o.primeira_importacao_id == imp.id for o in origens)
    estab = next(o for o in origens if o.entidade == Entidade.ESTABELECIMENTO)
    assert len(estab.hash_payload) == 64


async def test_mudanca_na_fonte_atualiza_e_troca_o_canal():
    await _importar(_cnes(1))
    imp = await _importar(_cnes(1, numero_telefone_estabelecimento="(11) 2222-5555"))

    assert (imp.atualizados, imp.inseridos) == (1, 0)
    async with get_session() as s:
        telefones = (await s.scalars(select(Canal.valor).where(Canal.tipo == "telefone"))).all()
    assert telefones == ["+551122225555"]


async def test_pessoa_fisica_quando_nao_tem_cnpj():
    await _importar(_cnes(1), _cnes(2, numero_cnpj="11222333000181"))
    async with get_session() as s:
        pf = dict((await s.execute(select(Estabelecimento.razao_social, Estabelecimento.pessoa_fisica))).all())
    assert pf == {"CLINICA EXEMPLO 1": True, "CLINICA EXEMPLO 2": False}


async def test_mesmo_cnpj_em_duas_fontes_vira_um_estabelecimento():
    await _importar(_cnes(1, numero_cnpj="11222333000181"))
    receita = Registro(
        id_na_fonte="11222333000181",
        hash_payload="r" * 64,
        identificadores=[(TipoIdentificador.CNPJ, "11222333000181")],
        nicho=Nicho.CLINICA,
        pessoa_fisica=False,
        razao_social="CLINICA EXEMPLO 1 LTDA",
        atividades=[("8630503", True)],
    )
    async with get_session() as s:
        imp = await importar(s, "receita_cnpj", {"municipio_receita": "7107"}, [receita])

    assert (imp.inseridos, imp.atualizados) == (0, 1)
    assert await _contar(Estabelecimento) == 1
    # A Receita não traz os canais do CNES, e não pode apagá-los: não são dela.
    assert await _contar(Canal) == 2
    assert await _contar(Identificador) == 2


async def test_canal_suprimido_nao_entra():
    async with get_session() as s:
        await suprimir(s, TipoSupressao.EMAIL, "Contato1@Exemplo.com.br", MotivoSupressao.OPTOUT)
    imp = await _importar(_cnes(1))

    assert imp.suprimidos == 1
    assert await _contar(Canal, Canal.tipo == "email") == 0
    assert await _contar(Canal, Canal.tipo == "telefone") == 1


async def test_suprimir_apaga_o_que_existe_e_bloqueia_a_volta():
    await _importar(_cnes(1))
    async with get_session() as s:
        apagadas = await suprimir(s, TipoSupressao.CNES, "1", MotivoSupressao.PEDIDO_TITULAR)
    assert apagadas == 1
    assert await _contar(Estabelecimento) == 0
    assert await _contar(Origem) == 0, "a proveniência do que saiu também sai"

    imp = await _importar(_cnes(1))
    assert (imp.suprimidos, imp.inseridos) == (1, 0)


async def test_supressao_guarda_hash_e_nao_o_dado():
    async with get_session() as s:
        await suprimir(s, TipoSupressao.TELEFONE, "(11) 3333-4444", MotivoSupressao.OPTOUT)
        hashes = (await s.scalars(select(Supressao.valor_hash))).all()
    assert len(hashes) == 1 and "3333" not in hashes[0]


async def test_some_uma_vez_continua_ativo_some_duas_vira_inativo():
    await _importar(_cnes(1), _cnes(2))
    uma = await _importar(_cnes(1))
    assert uma.marcados_inativos == 0
    assert await _contar(Estabelecimento, Estabelecimento.situacao == Situacao.INATIVO) == 0

    duas = await _importar(_cnes(1))
    assert duas.marcados_inativos == 1
    assert await _contar(Estabelecimento, Estabelecimento.situacao == Situacao.INATIVO) == 1


async def test_quem_volta_para_a_fonte_volta_a_ser_ativo():
    await _importar(_cnes(1), _cnes(2))
    await _importar(_cnes(1))
    await _importar(_cnes(1))
    await _importar(_cnes(1), _cnes(2))
    assert await _contar(Estabelecimento, Estabelecimento.situacao == Situacao.ATIVO) == 2


async def test_parametros_diferentes_nao_inativam_quem_e_de_outro_recorte():
    await _importar(_cnes(1))
    outro = {**PARAMS, "municipio": "330455"}
    await _importar(_cnes(2, codigo_municipio=330455), params=outro)
    await _importar(_cnes(2, codigo_municipio=330455), params=outro)
    assert await _contar(Estabelecimento, Estabelecimento.situacao == Situacao.INATIVO) == 0


async def test_importacao_que_falha_fica_registrada_e_nao_inativa_ninguem():
    await _importar(_cnes(1), _cnes(2))
    await _importar(_cnes(1), _cnes(2))

    def quebra():
        yield cnes.para_registro(_cnes(1), "11")
        raise RuntimeError("API caiu no meio")

    async with get_session() as s:
        with pytest.raises(RuntimeError):
            await importar(s, "cnes", PARAMS, quebra())
        ultima = await s.scalar(select(Importacao).order_by(Importacao.id.desc()))
    assert ultima.status == StatusImportacao.FALHOU
    assert "API caiu" in ultima.erro
    assert await _contar(Estabelecimento, Estabelecimento.situacao == Situacao.INATIVO) == 0


async def test_retencao_apaga_inativo_ha_mais_de_um_ano():
    await _importar(_cnes(1), _cnes(2))
    agora = datetime.now(UTC)
    async with get_session() as s:
        e1, e2 = (await s.scalars(select(Estabelecimento).order_by(Estabelecimento.id))).all()
        e1.situacao, e1.inativo_desde = Situacao.INATIVO, agora - timedelta(days=400)
        e2.situacao, e2.inativo_desde = Situacao.INATIVO, agora - timedelta(days=100)
        await s.commit()
        apagados = await aplicar_retencao(s, agora)
    assert apagados == 1
    assert await _contar(Estabelecimento) == 1
