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


async def test_colar_vaga_salva_e_abre_a_gaveta(candidaturas):
    await candidaturas.click("#btn-nova")
    await candidaturas.fill("#nova-descricao", VAGA)
    await candidaturas.fill("#nova-empresa", "Acme")
    await candidaturas.click('#form-vaga button[data-fluxo="salvar"]')

    await candidaturas.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)
    assert await candidaturas.locator("table.vagas tbody tr").count() == 1
    assert await candidaturas.locator("#form-vaga").is_hidden()
    assert not candidaturas.erros_de_js


# ── a gaveta (fase06 §2.6: o que já funciona, e tem que continuar) ─


@pytest.fixture
async def vaga_aberta(candidaturas):
    """Uma vaga colada, com a gaveta aberta nela."""
    await candidaturas.click("#btn-nova")
    await candidaturas.fill("#nova-descricao", VAGA)
    await candidaturas.click('#form-vaga button[data-fluxo="salvar"]')
    await candidaturas.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)
    return candidaturas


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


async def test_erro_vira_aviso_e_nao_trava_a_aba(candidaturas, servidor):
    """`alert()` congelava a aba inteira — inclusive o refresco e as requisições.

    Durante uma geração de 60 s isso não era detalhe de estilo: era o sistema
    parando de responder até eu clicar em OK.
    """
    houve_alert = []
    candidaturas.on("dialog", lambda d: (houve_alert.append(d.message), d.accept()))

    await candidaturas.click("#btn-nova")
    await candidaturas.fill("#nova-descricao", "curto demais")
    await candidaturas.click('#form-vaga button[data-fluxo="salvar"]')
    await candidaturas.wait_for_timeout(800)

    assert not houve_alert, f"ainda usa diálogo nativo: {houve_alert}"
    assert await candidaturas.locator("#avisos .aviso-caixa.erro").is_visible()


async def test_aviso_de_erro_nao_some_sozinho(candidaturas):
    """Aviso de erro que desaparece em 5 s é aviso que eu não li."""
    await candidaturas.click("#btn-nova")
    await candidaturas.fill("#nova-descricao", "curto")
    await candidaturas.click('#form-vaga button[data-fluxo="salvar"]')
    await candidaturas.wait_for_selector("#avisos .aviso-caixa.erro")
    await candidaturas.wait_for_timeout(6_000)
    assert await candidaturas.locator("#avisos .aviso-caixa.erro").is_visible()


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


# ── a tabela quando as vagas passam de uma dúzia (U5) ─────────────


@pytest.fixture
async def varias_vagas(candidaturas):
    """Três vagas com empresas e títulos distintos, coladas pela tela."""
    for titulo, empresa in [
        ("Desenvolvedor Python Pleno", "Acme"),
        ("Engenheiro de Dados", "Bravo Tech"),
        ("Analista de IA", "Ciclo Digital"),
    ]:
        await candidaturas.click("#btn-nova")
        await candidaturas.fill("#nova-descricao", f"{titulo}\n\n{VAGA}")
        await candidaturas.fill("#nova-titulo", titulo)
        await candidaturas.fill("#nova-empresa", empresa)
        await candidaturas.click('#form-vaga button[data-fluxo="salvar"]')
        await candidaturas.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)
        await candidaturas.click("#gaveta-fechar")
    return candidaturas


async def test_busca_filtra_a_tabela_sem_ir_ao_servidor(varias_vagas):
    p = varias_vagas
    assert await p.locator("table.vagas tbody tr").count() == 3

    await p.fill("#busca-vagas", "bravo")
    await p.wait_for_timeout(150)
    assert await p.locator("table.vagas tbody tr").count() == 1
    # A badge conta as duas coisas: sem isso ela mentiria sobre o total.
    # `.lower()` porque o CSS deixa a badge em maiúscula.
    assert "de 3" in (await p.locator("#vagas-total").inner_text()).lower()
    assert not p.erros_de_js


async def test_busca_ignora_acento(varias_vagas):
    # Eu digito "ciclo digital" sem pensar em acento; a vaga pode ter.
    await varias_vagas.fill("#busca-vagas", "digital")
    await varias_vagas.wait_for_timeout(150)
    assert await varias_vagas.locator("table.vagas tbody tr").count() == 1


async def test_busca_casa_termos_em_qualquer_ordem(varias_vagas):
    # "acme python" e "python acme" acham a mesma vaga.
    await varias_vagas.fill("#busca-vagas", "acme python")
    await varias_vagas.wait_for_timeout(150)
    assert await varias_vagas.locator("table.vagas tbody tr").count() == 1


async def test_busca_sem_resultado_oferece_limpar(varias_vagas):
    p = varias_vagas
    await p.fill("#busca-vagas", "zzz-nao-existe")
    await p.wait_for_timeout(150)
    await p.click('[data-acao="limpar-busca"]')
    assert await p.locator("table.vagas tbody tr").count() == 3
    assert await p.input_value("#busca-vagas") == ""


async def test_barra_foca_a_busca(varias_vagas):
    await varias_vagas.keyboard.press("/")
    assert await varias_vagas.evaluate("document.activeElement.id") == "busca-vagas"
    # E a "/" não foi parar dentro do campo.
    assert await varias_vagas.input_value("#busca-vagas") == ""


async def test_clicar_no_cabecalho_ordena_e_inverte(varias_vagas):
    p = varias_vagas

    def empresas():
        return p.locator("table.vagas tbody tr td:nth-child(2)").all_inner_texts()

    await p.click('th[data-ordenar="empresa"]')
    await p.wait_for_timeout(100)
    assert (await empresas())[0].startswith("Acme")

    await p.click('th[data-ordenar="empresa"]')  # de novo: inverte
    await p.wait_for_timeout(100)
    assert (await empresas())[0].startswith("Ciclo")
    assert not p.erros_de_js


# ── editar o currículo pela gaveta ────────────────────────────────


async def test_gaveta_sem_curriculo_nao_oferece_editar(vaga_aberta):
    """Sem currículo gerado não há o que editar — e o botão não aparece."""
    assert await vaga_aberta.locator('[data-acao="editar-curriculo"]').count() == 0
    assert not vaga_aberta.erros_de_js


async def test_editar_curriculo_pela_gaveta(candidaturas, com_curriculo):
    """O gesto inteiro: abrir, editar, salvar — e o PDF sair com o meu texto.

    Antes disto, um bullet ruim só tinha uma saída: regenerar tudo e torcer.
    """
    p = candidaturas
    await p.click("#btn-nova")
    await p.fill("#nova-descricao", VAGA)
    await p.click('#form-vaga button[data-fluxo="salvar"]')
    await p.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)

    vaga_id = await p.evaluate("document.querySelector('tr[data-id]').dataset.id")
    await com_curriculo(vaga_id)
    await p.click("#gaveta-fechar")
    await p.click(f'tr[data-id="{vaga_id}"]')
    await p.wait_for_selector('[data-acao="editar-curriculo"]', timeout=10_000)

    await p.click('[data-acao="editar-curriculo"]')
    await p.wait_for_selector("#curriculo-editor", timeout=10_000)
    texto = await p.input_value("#curriculo-editor")
    assert "RESUMO ORIGINAL DO MODELO." in texto

    await p.fill(
        "#curriculo-editor", texto.replace("RESUMO ORIGINAL DO MODELO.", "O QUE EU ESCREVI.")
    )
    await p.click('[data-acao="salvar-curriculo"]')
    await p.wait_for_selector('[data-acao="editar-curriculo"]', timeout=20_000)

    # A prova é reabrir: o que voltou do servidor é o que ficou gravado.
    await p.click('[data-acao="editar-curriculo"]')
    await p.wait_for_selector("#curriculo-editor", timeout=10_000)
    assert "O QUE EU ESCREVI." in await p.input_value("#curriculo-editor")
    assert not p.erros_de_js


async def test_esc_nao_fecha_a_gaveta_com_o_editor_aberto(candidaturas, com_curriculo):
    """Um Esc perdido custaria o currículo inteiro que acabei de reescrever."""
    p = candidaturas
    await p.click("#btn-nova")
    await p.fill("#nova-descricao", VAGA)
    await p.click('#form-vaga button[data-fluxo="salvar"]')
    await p.wait_for_selector("#gaveta:not([hidden])", timeout=15_000)

    vaga_id = await p.evaluate("document.querySelector('tr[data-id]').dataset.id")
    await com_curriculo(vaga_id)
    await p.click("#gaveta-fechar")
    await p.click(f'tr[data-id="{vaga_id}"]')
    await p.click('[data-acao="editar-curriculo"]')
    await p.wait_for_selector("#curriculo-editor", timeout=10_000)

    await p.fill("#curriculo-editor", "TEXTO QUE NÃO PODE SUMIR")
    await p.keyboard.press("Escape")
    await p.wait_for_timeout(300)

    assert await p.locator("#gaveta").is_visible()
    assert await p.input_value("#curriculo-editor") == "TEXTO QUE NÃO PODE SUMIR"


# ── as duas páginas (20/08/2026) ──────────────────────────────────


async def test_painel_nao_tem_mais_a_tabela_de_vagas(painel):
    """A razão da separação: a lista ia ficar ilegível junto do resto."""
    assert await painel.locator("#card-vagas").count() == 0
    assert await painel.locator("table.vagas").count() == 0
    # E o que ficou continua de pé.
    assert await painel.locator("#card-transcricao").is_visible()
    assert await painel.locator("#card-fila").is_visible()
    assert not painel.erros_de_js


async def test_candidaturas_tem_a_tabela_e_o_funil(candidaturas):
    assert await candidaturas.locator("#card-vagas").is_visible()
    assert await candidaturas.locator("#card-candidaturas").is_visible()
    # E não carrega o que não tem onde pintar.
    assert await candidaturas.locator("#card-transcricao").count() == 0
    assert not candidaturas.erros_de_js


async def test_da_para_voltar_para_o_painel(candidaturas):
    await candidaturas.click('.paginas a[href="/"]')
    await candidaturas.wait_for_selector("#card-transcricao", timeout=15_000)
    # A sessão é cookie: voltar não pede senha de novo.
    await candidaturas.wait_for_selector("#painel:not([hidden])", timeout=10_000)
    assert await candidaturas.locator("#login").is_hidden()


async def test_cada_pagina_busca_so_os_blocos_que_usa(candidaturas):
    """`?blocos=` não é enfeite: cada bloco é consulta ao banco a cada 15 s."""
    urls = await candidaturas.evaluate(
        "performance.getEntriesByType('resource').map(r => r.name).filter(n => n.includes('/api/painel'))"
    )
    assert urls, "a página nem chamou /api/painel"
    assert all("blocos=saude,candidaturas" in u for u in urls), urls


async def test_layout_do_painel_nao_desregula_com_a_fila_cheia(painel, acao_na_fila):
    """A fila fica com a coluna larga, e os medidores empilham na estreita.

    Nasceu de uma tela real: com 4 itens na fila, o "Modelo" descia para o meio
    da página. A causa era a fila ocupar duas linhas da grade — as linhas
    ganhavam a altura dela, e o segundo medidor caía junto com a segunda linha.
    """
    for _ in range(4):
        await acao_na_fila("texto\n" * 20)
    await painel.click("#atualizar")
    await painel.wait_for_selector("#fila textarea", timeout=10_000)

    m = await painel.evaluate(
        """() => {
          const r = (id) => document.getElementById(id).getBoundingClientRect();
          return {
            fila: r('card-fila').width,
            medidor: r('card-conhecimento').width,
            folga: r('card-modelo').top - r('card-conhecimento').bottom,
          };
        }"""
    )
    # A fila é superfície de trabalho: textarea de currículo inteiro não cabe
    # numa coluna estreita — na tela do defeito ela saía com 215 px.
    assert m["fila"] > m["medidor"], m
    # Os medidores encostam um no outro (o gap da grade), em vez de o segundo
    # flutuar para o meio da página.
    assert m["folga"] < 40, m
    assert not painel.erros_de_js


async def test_titulo_longo_no_indice_nao_espreme_a_fila(painel, acao_na_fila):
    """Uma faixa `1fr` tem mínimo automático de `min-content`.

    Bastava um título de índice longo — "Fase H — Híbrido: o que sai da máquina,
    e por qual medida > Fase H — …" — para a coluna da direita crescer além da
    fatia dela e espremer a fila. Medido a 1024 px antes do conserto:
    `645px 322px` viravam **`167px 800px`**, e a área de aprovar currículo
    ficava com 167 px.

    O `text-overflow: ellipsis` do `.ref` corta o texto na tela e **não**
    impede que ele empurre a faixa — foi por isso que o defeito passou
    despercebido: a tela parecia certa até o cartão ter conteúdo de verdade.
    """
    await acao_na_fila("texto\n" * 20)
    await painel.set_viewport_size({"width": 1024, "height": 866})
    await painel.click("#atualizar")
    await painel.wait_for_selector("#fila textarea", timeout=10_000)

    antes = await painel.evaluate(
        "() => document.getElementById('card-fila').getBoundingClientRect().width"
    )

    titulo = "Fase H — Híbrido: o que sai da máquina, e por qual medida > " * 2
    await painel.evaluate(
        """(t) => { document.getElementById('conhecimento').innerHTML =
             `<div class="lista"><div class="item"><span class="ref">${t}</span>
              <span class="n">26</span></div></div>`; }""",
        titulo,
    )
    await painel.wait_for_timeout(250)
    depois = await painel.evaluate(
        "() => document.getElementById('card-fila').getBoundingClientRect().width"
    )

    assert depois == antes, f"o conteúdo mexeu na coluna: {antes} → {depois}"
    assert depois > 400, depois
    assert not painel.erros_de_js
