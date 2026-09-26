"""Fonte Receita: os arquivos abertos do CNPJ → `Registro`.

Colunas conforme o dicionário oficial (`receita-cnpj-metadados.pdf`, guardado no
1.2.6). Regras que vêm do 1.2.6 §4:

- **Empresário individual (natureza 2135) e MEI são pessoa física.**
- **CPF no fim do nome empresarial sai antes de gravar.** A Receita mascara o
  CPF do sócio, mas não o que o próprio empresário pôs no nome.
- **Sócios não entram.** Este módulo nem lê o arquivo de sócios.

Os arquivos são lidos do disco, em streaming e filtrados antes de virar
registro. Baixá-los é passo separado (pendência P16 do 1.2.8).
"""
from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

from app.comercial.prospeccao import normalizacao as n
from app.comercial.prospeccao.importacao import Registro, hash_payload
from app.db.models.comercial.prospeccao import Nicho, Situacao, TipoIdentificador

# Estabelecimentos
E_BASICO, E_ORDEM, E_DV, E_FANTASIA, E_SITUACAO = 0, 1, 2, 4, 5
E_CNAE, E_CNAE_SEC, E_TIPO_LOG, E_LOG, E_NUMERO = 11, 12, 13, 14, 15
E_BAIRRO, E_CEP, E_UF, E_MUNICIPIO = 17, 18, 19, 20
E_DDD1, E_TEL1, E_DDD2, E_TEL2, E_EMAIL = 21, 22, 23, 24, 27
# Empresas
EMP_BASICO, EMP_RAZAO, EMP_NATUREZA = 0, 1, 2
# Simples
S_BASICO, S_MEI = 0, 4

SITUACAO_ATIVA = "02"
NATUREZA_EMPRESARIO_INDIVIDUAL = "2135"

# Classe CNAE (5 primeiros dígitos da subclasse) → nicho e segmento (1.2.1 §1.1).
CLASSES = {
    "86305": (Nicho.CLINICA, "clinica_medica_odontologica"),
    "86500": (Nicho.CLINICA, "outros_profissionais_saude"),
    "69117": (Nicho.ADVOCACIA, "atividades_juridicas"),
    "68218": (Nicho.IMOBILIARIA, "corretagem"),
    "68226": (Nicho.IMOBILIARIA, "administracao_imoveis"),
}

# Código de município da Receita → IBGE. Só a capital está conferida (1.2.6 §2);
# o de-para completo é a pendência P13.
MUNICIPIO_RECEITA_IBGE = {"7107": "3550308"}


def _linhas(arquivo: Path) -> Iterator[list[str]]:
    with zipfile.ZipFile(arquivo) as z, z.open(z.namelist()[0]) as f:
        yield from csv.reader(io.TextIOWrapper(f, encoding="latin1"), delimiter=";")


def estabelecimentos(arquivos: Iterable[Path], municipio: str, classes: Iterable[str] = CLASSES) -> Iterator[list[str]]:
    """Só o que interessa: município, CNAE principal de um nicho e situação ativa."""
    classes = tuple(classes)
    for arquivo in arquivos:
        for linha in _linhas(arquivo):
            if linha[E_MUNICIPIO] == municipio and linha[E_SITUACAO] == SITUACAO_ATIVA and linha[E_CNAE][:5] in classes:
                yield linha


def por_basico(arquivos: Iterable[Path], basicos: set[str], coluna_basico: int = 0) -> dict[str, list[str]]:
    """Empresas ou Simples, só das linhas cujo CNPJ básico interessa."""
    return {linha[coluna_basico]: linha for arquivo in arquivos for linha in _linhas(arquivo) if linha[coluna_basico] in basicos}


def para_registro(estab: list[str], empresa: list[str] | None, simples: list[str] | None) -> Registro:
    cnpj = estab[E_BASICO] + estab[E_ORDEM] + estab[E_DV]
    nicho, segmento = CLASSES[estab[E_CNAE][:5]]
    natureza = empresa[EMP_NATUREZA] if empresa else ""
    mei = bool(simples and simples[S_MEI] == "S")
    razao = n.sem_cpf_no_nome(empresa[EMP_RAZAO]) if empresa else None

    atividades = [(estab[E_CNAE], True)]
    atividades += [(c, False) for c in estab[E_CNAE_SEC].split(",") if len(c) == 7 and c != estab[E_CNAE]]

    telefones = [n.telefone(estab[t], estab[d]) for d, t in ((E_DDD1, E_TEL1), (E_DDD2, E_TEL2))]
    canais = [c for c in (*telefones, n.email(estab[E_EMAIL])) if c is not None]

    logradouro = " ".join(p for p in (estab[E_TIPO_LOG].strip(), estab[E_LOG].strip()) if p) or None
    return Registro(
        id_na_fonte=cnpj,
        # O hash é do que entra, não da linha inteira: a linha traz o CPF do
        # nome, e hash de dado pessoal também é dado pessoal.
        hash_payload=hash_payload({"estab": estab, "razao": razao, "natureza": natureza, "mei": mei}),
        identificadores=[(TipoIdentificador.CNPJ, cnpj)],
        nicho=nicho,
        segmento=segmento,
        pessoa_fisica=natureza == NATUREZA_EMPRESARIO_INDIVIDUAL or mei,
        situacao=Situacao.ATIVO,
        nome_fantasia=estab[E_FANTASIA].strip() or None,
        razao_social=razao,
        municipio_ibge=MUNICIPIO_RECEITA_IBGE.get(estab[E_MUNICIPIO]),
        uf=estab[E_UF] or None,
        bairro=estab[E_BAIRRO].strip() or None,
        cep=n.cep(estab[E_CEP]),
        logradouro=logradouro,
        numero=estab[E_NUMERO].strip() or None,
        canais=canais,
        atividades=list(dict(atividades).items()),
    )
