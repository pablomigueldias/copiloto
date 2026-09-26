"""Kit documental: o modelo vira documento sem nenhum `{{campo}}` sobrando."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from app.comercial.documentos import (
    CampoFaltando,
    campos_do_modelo,
    gerar_pdf,
    ler_modelo,
    preencher,
)

MODELO = """---
codigo: M99
titulo: Modelo de teste
versao: 2
---

# Proposta para {{cliente_razao_social}}

| Oferta | Mensal |
|---|---|
| {{oferta}} | {{mensal_valor}} |

Obrigado, {{cliente_razao_social}}.
"""

FIXOS = {
    "contratada_nome": "Pablo Ortiz",
    "contratada_identificacao": "Pablo Ortiz · pabloortiz.dev",
    "documento_numero": "PROP-2026-001",
    "data": "26/09/2026",
}
VALORES = {"cliente_razao_social": "Clínica Fictícia Ltda.", "oferta": "A", "mensal_valor": "R$ 450"}


def test_le_o_cabecalho():
    m = ler_modelo(MODELO)
    assert (m.codigo, m.titulo, m.versao) == ("M99", "Modelo de teste", "2")
    assert m.corpo.startswith("\n# Proposta")


def test_modelo_sem_cabecalho_ou_incompleto_falha():
    with pytest.raises(ValueError, match="sem cabeçalho"):
        ler_modelo("# só corpo")
    with pytest.raises(ValueError, match="versao"):
        ler_modelo("---\ncodigo: M1\ntitulo: X\n---\ncorpo")


def test_campos_na_ordem_sem_repetir():
    assert campos_do_modelo(MODELO) == ["cliente_razao_social", "oferta", "mensal_valor"]


def test_preenche_todas_as_ocorrencias():
    texto = preencher(ler_modelo(MODELO).corpo, VALORES)
    assert "{{" not in texto
    assert texto.count("Clínica Fictícia Ltda.") == 2


def test_campo_faltando_ou_vazio_nao_preenche():
    with pytest.raises(CampoFaltando) as e:
        preencher(MODELO, {"cliente_razao_social": "X", "oferta": "  "})
    assert e.value.faltando == ["oferta", "mensal_valor"]


def test_pdf_exige_os_campos_fixos_antes_de_abrir_o_navegador(tmp_path):
    with pytest.raises(CampoFaltando) as e:
        gerar_pdf(MODELO, VALORES, tmp_path / "x.pdf")
    assert set(e.value.faltando) == set(FIXOS)
    assert not (tmp_path / "x.pdf").exists()


@pytest.mark.ui
@pytest.mark.skipif(not shutil.which("pandoc") or not shutil.which("pdftotext"), reason="pandoc/pdftotext ausente")
def test_gera_pdf_com_cabecalho_rodape_e_tabela(tmp_path):
    destino = gerar_pdf(MODELO, VALORES | FIXOS, tmp_path / "doc.pdf")
    texto = subprocess.run(["pdftotext", "-layout", str(destino), "-"], capture_output=True, text=True).stdout
    for esperado in ("PROP-2026-001", "M99 v2", "26/09/2026", "pabloortiz.dev", "página 1 de 1", "R$ 450"):
        assert esperado in texto
    assert "{{" not in texto


COM_NOTAS = MODELO + """
<!-- notas -->

## Pontos para o advogado

1. A cláusula de [nome] vale?
"""


def test_notas_ficam_fora_do_corpo_e_dos_campos():
    m = ler_modelo(COM_NOTAS)
    assert "advogado" not in m.corpo
    assert m.notas.lstrip().startswith("## Pontos para o advogado")
    assert preencher(m.corpo, VALORES)  # os [colchetes] das notas não são cobrados


def test_notas_com_campo_nao_entram_na_versao_de_revisao(tmp_path):
    ruim = MODELO + "\n<!-- notas -->\n\nFalta {{cliente_razao_social}} aqui.\n"
    with pytest.raises(ValueError, match="colchetes"):
        gerar_pdf(ruim, VALORES | FIXOS, tmp_path / "x.pdf", com_notas=True)
