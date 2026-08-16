"""O importador do Perfil Mestre.

Duas coisas importam aqui: **não duplicar o perfil** (dois perfis ativos fariam
a busca devolver a versão errada metade das vezes) e **apontar os buracos** —
principalmente projeto sem número, que é o que separa currículo forte de fraco.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import select

from app.db.models.pessoal.perfil_mestre import PerfilMestre
from app.db.session import get_session

_spec = importlib.util.spec_from_file_location(
    "importar_perfil", Path(__file__).resolve().parent.parent / "scripts" / "importar_perfil.py"
)
importar_perfil = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(importar_perfil)

COMPLETO = {
    "nome": "Pablo",
    "titulo": "AI Engineer",
    "tom_escrita": "Frases curtas.",
    "habilidades": [{"nome": "Python", "nivel": "avançado"}],
    "projetos": [{"nome": "Copiloto", "descricao": "RAG local", "prova": "216 testes"}],
    "experiencias": [{"empresa": "Sechat", "cargo": "Analista", "periodo": "jan/2025 – dez/2025"}],
    "certificacoes": [{"nome": "T-SQL", "ano": 2025}],
    "o_que_procuro": {"modelo": "PJ remoto", "tipo_empresa": "startup", "pretensao": "a combinar"},
    "_leia_me": "isto não vai para o banco",
    "_falta": ["nem isto"],
}


async def test_cria_o_perfil_e_ignora_as_anotacoes():
    perfil, criou = await importar_perfil.importar(COMPLETO)

    assert criou is True and perfil.ativo is True
    assert perfil.nome == "Pablo"
    assert perfil.projetos[0]["prova"] == "216 testes"
    # `_leia_me` e `_falta` são recado para mim, não coluna.
    assert not hasattr(perfil, "_leia_me")


async def test_importar_de_novo_atualiza_em_vez_de_duplicar():
    await importar_perfil.importar(COMPLETO)
    _, criou = await importar_perfil.importar({**COMPLETO, "titulo": "Desenvolvedor Python"})

    assert criou is False
    async with get_session() as s:
        perfis = (await s.scalars(select(PerfilMestre))).all()
    # Dois perfis ativos fariam a F2.5 indexar duas versões de mim.
    assert len(perfis) == 1 and perfis[0].titulo == "Desenvolvedor Python"


def test_aponta_projeto_sem_numero():
    dados = {**COMPLETO, "projetos": [{"nome": "Churn", "descricao": "ML", "prova": None}]}
    (falta,) = [f for f in importar_perfil.buracos(dados) if "NÚMERO" in f]
    assert "Churn" in falta


def test_aponta_o_que_procuro_incompleto():
    dados = {**COMPLETO, "o_que_procuro": {"modelo": "remoto"}}
    faltas = " ".join(importar_perfil.buracos(dados))
    assert "pretensao" in faltas and "tipo_empresa" in faltas


def test_aponta_periodo_sem_mes():
    dados = {**COMPLETO, "experiencias": [{"empresa": "Sechat", "periodo": "2025"}]}
    assert any("período sem mês" in f for f in importar_perfil.buracos(dados))


def test_perfil_completo_nao_tem_buraco():
    assert importar_perfil.buracos(COMPLETO) == []
