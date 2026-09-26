"""Parser da base do CNPJ — as regras do 1.2.6 §4, com linhas inventadas.

Nenhum arquivo real da Receita entra aqui: as linhas seguem o leiaute oficial e
os valores são fictícios.
"""
from __future__ import annotations

import zipfile

from app.comercial.prospeccao import receita
from app.db.models.comercial.prospeccao import Nicho, TipoCanal, TipoIdentificador


def _estab(**kw) -> list[str]:
    linha = [""] * 30
    campos = {
        receita.E_BASICO: "12345678", receita.E_ORDEM: "0001", receita.E_DV: "95",
        receita.E_FANTASIA: "Exemplo Imóveis", receita.E_SITUACAO: "02",
        receita.E_CNAE: "6821801", receita.E_CNAE_SEC: "6822600,6821801",
        receita.E_TIPO_LOG: "RUA", receita.E_LOG: "DO EXEMPLO", receita.E_NUMERO: "100",
        receita.E_BAIRRO: "CENTRO", receita.E_CEP: "01001000", receita.E_UF: "SP",
        receita.E_MUNICIPIO: "7107", receita.E_DDD1: "11", receita.E_TEL1: "33334444",
        receita.E_DDD2: "11", receita.E_TEL2: "", receita.E_EMAIL: "Contato@Exemplo.com.br",
    }
    campos.update({getattr(receita, k): v for k, v in kw.items()})
    for i, v in campos.items():
        linha[i] = v
    return linha


def _empresa(natureza="2062", razao="EXEMPLO IMOVEIS LTDA"):
    return ["12345678", razao, natureza, "49", "1000,00", "01", ""]


def _simples(mei="N"):
    return ["12345678", "S", "20200101", "", mei, "", ""]


def test_empresa_limitada_nao_e_pessoa_fisica():
    r = receita.para_registro(_estab(), _empresa(), _simples())
    assert not r.pessoa_fisica
    assert r.identificadores == [(TipoIdentificador.CNPJ, "12345678000195")]
    assert (r.nicho, r.segmento) == (Nicho.IMOBILIARIA, "corretagem")
    assert r.municipio_ibge == "3550308"
    assert r.logradouro == "RUA DO EXEMPLO"


def test_empresario_individual_e_pessoa_fisica_e_perde_o_cpf_do_nome():
    r = receita.para_registro(_estab(), _empresa("2135", "MARIA EXEMPLO 52998224725"), _simples())
    assert r.pessoa_fisica
    assert r.razao_social == "MARIA EXEMPLO"


def test_cpf_do_nome_nao_entra_nem_no_hash():
    com_cpf = receita.para_registro(_estab(), _empresa("2135", "MARIA EXEMPLO 52998224725"), _simples())
    sem_cpf = receita.para_registro(_estab(), _empresa("2135", "MARIA EXEMPLO"), _simples())
    assert com_cpf.hash_payload == sem_cpf.hash_payload


def test_mei_e_pessoa_fisica_mesmo_com_outra_natureza():
    assert receita.para_registro(_estab(), _empresa(), _simples(mei="S")).pessoa_fisica


def test_cnae_principal_e_secundarios_sem_repeticao():
    r = receita.para_registro(_estab(), _empresa(), _simples())
    assert r.atividades == [("6821801", True), ("6822600", False)]


def test_ddd_separado_vira_telefone_e_email_normaliza():
    r = receita.para_registro(_estab(), _empresa(), _simples())
    assert [(c.tipo, c.valor) for c in r.canais] == [
        (TipoCanal.TELEFONE, "+551133334444"),
        (TipoCanal.EMAIL, "contato@exemplo.com.br"),
    ]


def test_advocacia_pelo_cnae():
    r = receita.para_registro(_estab(E_CNAE="6911701", E_CNAE_SEC=""), _empresa("2321"), _simples())
    assert r.nicho == Nicho.ADVOCACIA


def test_leitura_filtra_municipio_cnae_e_situacao(tmp_path):
    linhas = [
        _estab(),
        _estab(E_BASICO="11111111", E_MUNICIPIO="6477"),  # outro município
        _estab(E_BASICO="22222222", E_CNAE="4711302"),  # outro ramo
        _estab(E_BASICO="33333333", E_SITUACAO="08"),  # baixada
    ]
    arquivo = tmp_path / "Estabelecimentos0.zip"
    with zipfile.ZipFile(arquivo, "w") as z:
        z.writestr("ESTABELE", "\n".join(";".join(f'"{c}"' for c in linha) for linha in linhas).encode("latin1"))
    achados = list(receita.estabelecimentos([arquivo], "7107"))
    assert [a[receita.E_BASICO] for a in achados] == ["12345678"]
