"""O painel, num navegador de verdade.

Cada teste aqui nasceu de um defeito que a suíte de 375 testes não pegou. Se um
deles ficar vermelho, alguma coisa que o usuário faz todo dia quebrou — não é
detalhe de implementação.
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.ui

VAGA = """Desenvolvedor Python Pleno — Remoto

Buscamos pessoa desenvolvedora para atuar com APIs REST e pipelines de dados.
Requisitos: 3 anos com Python, FastAPI, SQL e PostgreSQL, Git.
Desejáveis: Docker, testes automatizados.
Enviar para vagas@acme.dev
"""


# ── o bug que apagava o meu texto (fase06 §2.1) ───────────────────


async def test_refresco_nao_apaga_o_que_estou_editando(painel, acao_na_fila):
    """O defeito mais grave da F5: 15 s depois, a edição some sem aviso.

    É o pior tipo de bug neste sistema porque `exemplo_estilo` e o dataset de
    preferência nascem exatamente desta edição — perder isso é perder o dado
    que o projeto existe para coletar.
    """
    await acao_na_fila()
    await painel.click("#atualizar")
    textarea = painel.locator("#fila textarea").first
    await textarea.wait_for(timeout=10_000)

    await textarea.fill("MINHA EDIÇÃO QUE NÃO PODE SUMIR")
    await painel.click("#atualizar")          # mesmo caminho do timer de 15 s
    await painel.wait_for_timeout(1_500)

    assert await textarea.input_value() == "MINHA EDIÇÃO QUE NÃO PODE SUMIR"
    assert not painel.erros_de_js


async def test_refresco_automatico_tambem_preserva(painel, acao_na_fila, servidor):
    """O mesmo, pelo timer — que é como o bug aparece na vida real."""
    await acao_na_fila()
    # `?refresco=1500` só existe para este teste: esperar 15 s por asserção
    # tornaria a suíte lenta demais para ser rodada.
    await painel.goto(f"{servidor}/?refresco=1500", wait_until="networkidle")
    textarea = painel.locator("#fila textarea").first
    await textarea.wait_for(timeout=10_000)

    await textarea.fill("EDIÇÃO DURANTE O REFRESCO")
    await painel.wait_for_timeout(4_000)      # dois ciclos

    assert await textarea.input_value() == "EDIÇÃO DURANTE O REFRESCO"


async def test_tela_avisa_que_pausou_a_atualizacao(painel, acao_na_fila):
    """Não atualizar em silêncio é trocar um bug por outro."""
    await acao_na_fila()
    await painel.click("#atualizar")
    textarea = painel.locator("#fila textarea").first
    await textarea.wait_for(timeout=10_000)
    await textarea.fill("editando")
    await painel.click("#atualizar")
    await painel.wait_for_timeout(1_000)

    assert await painel.locator("#fila-pausada").is_visible()


# ── o botão que "não funcionava" (era cache) ──────────────────────


async def test_o_navegador_carrega_o_js_de_agora(painel):
    """Sem revalidação, a aba fica com o JS de ontem e o front velho lê o
    backend novo — foi assim que a transcrição virou `[object Object]`.

    Testa o efeito, não o mecanismo: se o painel pinta o que o backend está
    mandando agora, o cache não está no caminho.
    """
    respostas = await painel.evaluate(
        """async () => {
            const arquivos = ["/js/main.js", "/js/vagas.js", "/js/transcricao.js"];
            const r = [];
            for (const a of arquivos) {
              const resp = await fetch(a, { cache: "no-store" });
              r.push([a, resp.status, (await resp.text()).length]);
            }
            return r;
        }"""
    )
    for caminho, status, tamanho in respostas:
        assert status == 200, caminho
        assert tamanho > 200, f"{caminho} veio vazio"

    # O sintoma que motivou tudo isto.
    assert "[object Object]" not in await painel.locator("#painel").inner_text()


async def test_colar_vaga_salva_e_abre_a_gaveta(painel):
    await painel.click("#btn-nova")
    await painel.fill("#nova-descricao", VAGA)
    await painel.fill("#nova-empresa", "Acme")
    await painel.click('#form-vaga button[data-fluxo="salvar"]')

    await painel.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)
    assert await painel.locator("table.vagas tbody tr").count() == 1
    assert await painel.locator("#form-vaga").is_hidden()
    assert not painel.erros_de_js


# ── a gaveta (fase06 §2.6: o que já funciona, e tem que continuar) ─


@pytest.fixture
async def vaga_aberta(painel):
    """Uma vaga colada, com a gaveta aberta nela."""
    await painel.click("#btn-nova")
    await painel.fill("#nova-descricao", VAGA)
    await painel.click('#form-vaga button[data-fluxo="salvar"]')
    await painel.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)
    return painel


@pytest.mark.parametrize(
    ("como", "acao"),
    [
        ("backdrop", lambda p: p.click("#gaveta-fundo")),
        ("botão X", lambda p: p.click("#gaveta-fechar")),
        ("outro campo", lambda p: p.click('#gaveta-corpo [data-campo="link"]')),
        ("Enter", lambda p: p.keyboard.press("Enter")),
    ],
)
async def test_gaveta_salva_em_todo_jeito_de_sair(vaga_aberta, como, acao):
    """Quatro jeitos de sair de um campo. Os quatro salvam.

    O quinto — `Esc` — descarta de propósito, e tem teste próprio.
    """
    campo = vaga_aberta.locator('#gaveta-corpo [data-campo="fonte"]')
    await campo.click()
    await vaga_aberta.keyboard.type("LinkedIn")
    await acao(vaga_aberta)
    await vaga_aberta.wait_for_timeout(1_500)

    from app.candidatura import vagas

    _, itens = await vagas.listar()
    assert itens[0].fonte == "LinkedIn", f"perdeu a edição ao sair por: {como}"


async def test_esc_desfaz_a_edicao_do_campo(vaga_aberta):
    """`Esc` descarta — e a gaveta diz isso, senão vira perda de dado."""
    campo = vaga_aberta.locator('#gaveta-corpo [data-campo="fonte"]')
    await campo.click()
    await vaga_aberta.keyboard.type("Indicação")
    await vaga_aberta.keyboard.press("Escape")
    await vaga_aberta.wait_for_timeout(1_000)

    from app.candidatura import vagas

    _, itens = await vagas.listar()
    assert itens[0].fonte is None

    rodape = vaga_aberta.locator("#gaveta-ajuda")
    assert await rodape.is_visible()
    assert "Esc" in (await rodape.inner_text())


# ── saúde do sistema na tela (fase06 §B3) ─────────────────────────


async def test_painel_mostra_se_o_worker_esta_vivo(painel):
    """Sem este indicador, o índice envelhece e nada na tela conta.

    Foi assim que 42 PDFs ficaram 14 h fora do índice sem ninguém notar.
    """
    await painel.wait_for_selector("#saude", timeout=10_000)
    saude = await painel.locator("#saude").inner_text()
    assert "worker" in saude.lower()


# ── avisos no lugar de alert/prompt (fase06 §D1) ──────────────────


async def test_erro_vira_aviso_e_nao_trava_a_aba(painel, servidor):
    """`alert()` congelava a aba inteira — inclusive o refresco e as requisições.

    Durante uma geração de 60 s isso não era detalhe de estilo: era o sistema
    parando de responder até eu clicar em OK.
    """
    houve_alert = []
    painel.on("dialog", lambda d: (houve_alert.append(d.message), d.accept()))

    await painel.click("#btn-nova")
    await painel.fill("#nova-descricao", "curto demais")
    await painel.click('#form-vaga button[data-fluxo="salvar"]')
    await painel.wait_for_timeout(800)

    assert not houve_alert, f"ainda usa diálogo nativo: {houve_alert}"
    assert await painel.locator("#avisos .aviso-caixa.erro").is_visible()


async def test_aviso_de_erro_nao_some_sozinho(painel):
    """Aviso de erro que desaparece em 5 s é aviso que eu não li."""
    await painel.click("#btn-nova")
    await painel.fill("#nova-descricao", "curto")
    await painel.click('#form-vaga button[data-fluxo="salvar"]')
    await painel.wait_for_selector("#avisos .aviso-caixa.erro")
    await painel.wait_for_timeout(6_000)
    assert await painel.locator("#avisos .aviso-caixa.erro").is_visible()


async def test_rejeitar_pergunta_o_motivo_numa_caixa_de_verdade(painel, acao_na_fila):
    """O motivo vira sinal de treino: merece mais que a caixinha do `prompt()`."""
    houve_prompt = []
    painel.on("dialog", lambda d: (houve_prompt.append(d.type), d.dismiss()))

    await acao_na_fila()
    await painel.click("#atualizar")
    await painel.wait_for_selector("#fila button.rejeitar", timeout=10_000)
    await painel.click("#fila button.rejeitar")
    await painel.wait_for_selector(".modal-fundo", timeout=5_000)

    assert not houve_prompt
    assert await painel.locator(".modal textarea").is_visible()


# ── botões que contam o que estão fazendo (fase06 §D2) ────────────


async def test_botao_mostra_que_esta_ocupado(painel, acao_na_fila):
    await acao_na_fila()
    await painel.click("#atualizar")
    botao = painel.locator("#fila button.aprovar")
    await botao.wait_for(timeout=10_000)

    await botao.click()
    # A decisão é rápida; o que importa é o botão nunca aceitar clique duplo.
    await painel.wait_for_timeout(1_500)
    assert await painel.locator("#avisos .aviso-caixa.ok").is_visible()
    assert not painel.erros_de_js


# ── apagar vaga (fase06 §D3) ──────────────────────────────────────


async def test_apagar_vaga_pela_gaveta(vaga_aberta):
    await vaga_aberta.click('#gaveta-corpo button[data-acao="apagar"]')
    await vaga_aberta.wait_for_selector(".modal-fundo", timeout=5_000)
    await vaga_aberta.click('.modal [data-acao="sim"]')
    await vaga_aberta.wait_for_timeout(1_500)

    assert await vaga_aberta.locator("#gaveta").is_hidden()
    assert await vaga_aberta.locator("table.vagas tbody tr").count() == 0


async def test_apagar_pede_confirmacao(vaga_aberta):
    """`ON DELETE CASCADE` leva o histórico junto: não pode ser um clique só."""
    await vaga_aberta.click('#gaveta-corpo button[data-acao="apagar"]')
    await vaga_aberta.wait_for_selector(".modal-fundo", timeout=5_000)
    await vaga_aberta.click('.modal [data-acao="nao"]')
    await vaga_aberta.wait_for_timeout(800)

    assert await vaga_aberta.locator("table.vagas tbody tr").count() == 1


# ── a transcrição na tela (fase-transcricao §P1, §U1 e §E1) ───────

ESTADO_OCIOSO = {
    "estado": "ocioso",
    "etapa": None,
    "fonte": "sistema",
    "segundos": 0,
    "palavras": 0,
    "bloco": 0,
    "blocos": 0,
    "trechos": [],
    "erro": None,
    "sugestao": None,
}


def _trecho(indice: int, texto: str, *, processado: bool = False) -> dict:
    return {
        "indice": indice,
        "segundo": indice * 20,
        "relogio": f"00:{indice * 20:02d}",
        "texto": texto,
        "anuncio": False,
        "processado": processado,
    }


async def _fingir_estado(pagina, **campos):
    """Faz `/api/transcricao/estado` responder o que o teste quiser.

    Gravar de verdade aqui exigiria uma placa de som — e o que estes testes
    cobrem é o **JavaScript**, que é justo o que a suíte de 455 testes não vê. O
    contrato do endpoint tem teste próprio em `tests/test_transcricao_api.py`.

    O `reload` é necessário porque `transcricao.ligar()` lê o estado uma vez na
    partida da página, e é dessa leitura que sai o pulso de 1 s.
    """
    corpo = json.dumps({**ESTADO_OCIOSO, **campos})

    async def responder(rota):
        await rota.fulfill(status=200, content_type="application/json", body=corpo)

    await pagina.route("**/api/transcricao/estado", responder)
    await pagina.reload(wait_until="networkidle")


async def test_a_tela_diz_em_que_bloco_a_reescrita_esta(painel):
    """Três minutos de "organizando…" é onde eu penso que travou (§U1).

    O servidor sempre soube o bloco — `logger.info("bloco 3/6 pronto")`. O que
    faltava era ele contar, e a tela pintar.
    """
    await _fingir_estado(
        painel,
        estado="processando",
        etapa="reescrevendo",
        bloco=3,
        blocos=6,
        segundos=1_560,
        palavras=3_900,
        trechos=[_trecho(0, "Uma tabela verdade tem 2^n linhas.", processado=True)],
    )

    await painel.wait_for_selector("#transcricao-progresso", timeout=10_000)
    assert "bloco 4 de 6" in await painel.locator("#transcricao-progresso").inner_text()
    # E também no badge do título, que é o que eu vejo sem rolar a página. O
    # `lower` é porque o badge é maiúsculo por CSS, e `inner_text` vê o renderizado.
    badge = (await painel.locator("#transcricao-tempo").inner_text()).lower()
    assert "bloco 4 de 6" in badge
    assert not painel.erros_de_js


async def test_a_tela_diz_o_que_o_fichamento_esta_fazendo(painel):
    """A última etapa tem nome próprio: são mais 31 s, e não é reescrita."""
    await _fingir_estado(painel, estado="processando", etapa="fichando", bloco=6, blocos=6)

    await painel.wait_for_selector("#transcricao-progresso", timeout=10_000)
    texto = await painel.locator("#transcricao-progresso").inner_text()
    assert "título" in texto and "pasta" in texto
    assert not painel.erros_de_js


async def test_trecho_ja_organizado_nao_oferece_o_x(painel):
    """O ✕ do trecho que já virou bloco reescrito sai da tela (§P1).

    Cortar depois da reescrita obrigaria a pagar o bloco de novo. O servidor
    recusa igual — isto é para eu não descobrir a recusa clicando.
    """
    await _fingir_estado(
        painel,
        estado="gravando",
        etapa="transcrevendo",
        bloco=1,
        blocos=2,
        segundos=140,
        palavras=700,
        trechos=[
            _trecho(0, "Conectivo lógico é o que liga duas proposições.", processado=True),
            _trecho(1, "E a negação inverte o valor de verdade.", processado=False),
        ],
    )

    await painel.wait_for_selector(".trecho", timeout=10_000)
    travado = painel.locator('.trecho[data-processado="1"] .trecho-cortar')
    assert await travado.is_disabled()
    assert await travado.is_hidden()
    # O trecho ainda solto continua cortável: é para ele que o ✕ existe.
    assert await painel.locator('.trecho:not([data-processado="1"]) .trecho-cortar').count() == 1

    # E o badge conta quanto da aula já está organizado — durante a aula.
    badge = (await painel.locator("#transcricao-tempo").inner_text()).lower()
    assert "1 bloco pronto" in badge
    assert not painel.erros_de_js
