"""O simulado, num navegador de verdade — o ciclo inteiro pela tela.

Começar pelo menu, marcar pela folha de respostas, entregar, ler a nota e o
assunto errado, fazer o reforço e ver o próximo simulado liberar. As questões de
reforço entram pelo mesmo caminho do script (`vincular_reforco`), porque na vida
real quem as escreve não é a tela.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.db.models.estudo.questao import Modulo, Topico
from app.db.session import get_session
from app.estudo import servico
from app.estudo import simulado as sim

pytestmark = pytest.mark.ui

SHOTS = Path(__file__).resolve().parent.parent.parent / "logs" / "ui-simulado"
ALTS = [{"letra": letra, "texto": f"alternativa {letra}"} for letra in "ABCDE"]


def sem_erros(pagina):
    assert not pagina.erros_de_js, f"JS quebrou: {pagina.erros_de_js}"


async def _estoque() -> uuid.UUID:
    """Uma questão por matéria: Crase, Pitágoras, referência pronominal, Triggers."""
    async with get_session() as s:
        mod = Modulo(nome="Estoque", trilha="concurso")
        s.add(mod)
        await s.flush()
        top = Topico(modulo_id=mod.id, nome="Tudo")
        s.add(top)
        await s.commit()
        topico_id = top.id
    for assunto in ("Crase", "Teorema de Pitágoras", "Referência pronominal", "Triggers"):
        await servico.criar_questao({
            "topico_id": topico_id, "assunto": assunto, "formato": "multipla_escolha",
            "enunciado": f"Questão de {assunto}.", "alternativas": ALTS, "afirmacoes": [],
            "gabarito": "A", "explicacao": f"Explicação de {assunto}.", "dificuldade": 2,
        })
    return topico_id


async def test_ciclo_simulado_reforco_pela_tela(painel):
    SHOTS.mkdir(parents=True, exist_ok=True)
    topico_id = await _estoque()

    # Entra pelo menu: prova de graça que o link existe.
    await painel.click('aside nav a:has-text("Simulado")')
    await painel.wait_for_selector('button:has-text("Começar o simulado")', timeout=60000)
    await painel.screenshot(path=str(SHOTS / "1-entrada.png"), full_page=True)
    await painel.click('button:has-text("Começar o simulado")')
    await painel.wait_for_selector("text=Folha de respostas", timeout=60000)

    # Marca E na de Triggers, que é a primeira (os específicos abrem o caderno),
    # e A nas outras três (certas).
    for n in range(4):
        await painel.wait_for_selector(f"text=Questão {n + 1}", timeout=10000)
        letra = "E" if n == 0 else "A"
        await painel.click(f'button:has-text("alternativa {letra}")')
        if n < 3:
            await painel.click('button:has-text("Próxima")')
    await painel.screenshot(path=str(SHOTS / "2-prova.png"), full_page=True)
    assert await painel.is_visible("text=4 marcadas · 0 em branco")

    await painel.click('main button:has-text("Entregar a prova") >> nth=-1')
    await painel.click('button:has-text("entregar e ver a nota")')
    await painel.wait_for_selector("text=O que reforçar", timeout=60000)
    await painel.screenshot(path=str(SHOTS / "3-resultado.png"), full_page=True)

    corpo = await painel.inner_text("body")
    assert "75,00" in corpo  # P = 100/4 × 3
    assert "Habilitado na objetiva" in corpo
    assert "Triggers" in corpo and "errou 1 de 1" in corpo
    assert "marcou E · gabarito A" in corpo
    assert "Explicação de Triggers." in corpo
    # O assunto errado oferece o botão (que aqui não é clicado: dispararia o Claude Code).
    assert await painel.is_visible('button:has-text("Gerar reforço")')

    # A trava: com reforço pendente, a entrada não oferece novo simulado.
    await painel.click('a:has-text("← Simulado")')
    await painel.wait_for_selector("text=Reforço antes do próximo simulado", timeout=60000)
    assert not await painel.is_visible('button:has-text("Começar o simulado")')

    # As 5 de reforço chegam (o que o script de importação faz).
    estado = await sim.estado()
    (reforco,) = estado["reforcos_pendentes"]
    ids = []
    for n in range(5):
        q = await servico.criar_questao({
            "topico_id": topico_id, "assunto": "Triggers", "formato": "multipla_escolha",
            "enunciado": f"Reforço de trigger {n + 1}.", "alternativas": ALTS, "afirmacoes": [],
            "gabarito": "B", "explicacao": "BEFORE altera NEW; AFTER audita.", "dificuldade": 2,
        })
        ids.append(q.id)
    await sim.vincular_reforco(uuid.UUID(reforco["id"]), ids)

    await painel.reload(wait_until="domcontentloaded")
    await painel.click('a:has-text("Fazer as 5")', timeout=60000)
    for n in range(5):
        await painel.wait_for_selector(f"text=Reforço de trigger {n + 1}.", timeout=60000)
        letra = "C" if n == 0 else "B"  # 4 de 5 = 80%
        await painel.click(f'button:has-text("alternativa {letra}")')
        await painel.click('button:has-text("Responder")')
        await painel.wait_for_selector("text=Por quê", timeout=10000)
        if n == 0:
            await painel.screenshot(path=str(SHOTS / "4-reforco.png"), full_page=True)
        await painel.click('button:has-text("Próxima"), button:has-text("Ver o resultado")')
    await painel.wait_for_selector("text=Reforço aprovado", timeout=10000)
    assert "4 de 5" in await painel.inner_text("body")

    await painel.click('a:has-text("Voltar ao simulado")')
    await painel.wait_for_selector('button:has-text("Começar o simulado")', timeout=60000)
    await painel.screenshot(path=str(SHOTS / "5-liberado.png"), full_page=True)
    sem_erros(painel)
