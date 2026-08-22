"""O painel, num navegador de verdade.

Cada teste aqui nasceu de um defeito que a suíte sem navegador não pegou. Se um
deles ficar vermelho, alguma coisa que eu faço todo dia quebrou — não é detalhe
de implementação.

Portados do painel estático para o Next.js em 22/08/2026. O alvo mudou, as
regras não: o refresco que não pode apagar o meu rascunho, o `Esc` que fecha a
gaveta menos quando o editor está aberto, a busca que filtra sem ir ao servidor.
Os que sumiram sumiram porque o defeito deixou de ser possível — o teste do
cache de módulos ES não sobrevive a um bundler que versiona o grafo inteiro.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.ui

VAGA = """Desenvolvedor Python Pleno — Remoto

Buscamos pessoa desenvolvedora para atuar com APIs REST e pipelines de dados.
Requisitos: 3 anos com Python, FastAPI, SQL e PostgreSQL, Git.
Desejáveis: Docker, testes automatizados.
Enviar para vagas@acme.dev
"""

ORIGINAL = "TEXTO ORIGINAL DO MODELO"
CARTAO = "article:has(textarea)"
TEXTO = f"{CARTAO} textarea"


def sem_erros(pagina):
    assert not pagina.erros_de_js, f"JS quebrou: {pagina.erros_de_js}"


# ── A fila: o que o refresco não pode fazer ───────────────────────

async def test_refresco_nao_apaga_o_que_estou_editando(fila, acao_na_fila):
    """O defeito original: repintar a cada 15 s trocava o textarea inteiro."""
    await acao_na_fila(ORIGINAL)
    await fila.reload(wait_until="domcontentloaded")
    await fila.wait_for_selector(TEXTO, timeout=60000)

    await fila.fill(TEXTO, "MINHA VERSÃO, AINDA NÃO SALVA")
    # O mesmo caminho do timer de 15 s, sem esperar por ele: o botão força o
    # refresco que a edição tinha pausado.
    await fila.click('button:has-text("atualizar mesmo assim")')
    await fila.wait_for_timeout(500)

    assert await fila.input_value(TEXTO) == "MINHA VERSÃO, AINDA NÃO SALVA"
    sem_erros(fila)


async def test_tela_avisa_que_pausou_a_atualizacao(fila, acao_na_fila):
    """Pausar sem dizer é o mesmo que travar: a tela tem que confessar."""
    await acao_na_fila(ORIGINAL)
    await fila.reload(wait_until="domcontentloaded")
    await fila.wait_for_selector(TEXTO, timeout=60000)

    assert not await fila.is_visible("text=refresco pausado")
    await fila.fill(TEXTO, "mexi aqui")
    await fila.wait_for_selector("text=refresco pausado", timeout=5000)
    sem_erros(fila)


async def test_atualizar_mesmo_assim_libera_o_refresco(fila, acao_na_fila):
    """Perder o rascunho é decisão minha, não do timer."""
    await acao_na_fila(ORIGINAL)
    await fila.reload(wait_until="domcontentloaded")
    await fila.wait_for_selector(TEXTO, timeout=60000)

    await fila.fill(TEXTO, "rascunho descartável")
    await fila.wait_for_selector("text=refresco pausado", timeout=5000)
    await fila.click('button:has-text("atualizar mesmo assim")')
    await fila.wait_for_selector("text=refresco pausado", state="detached", timeout=10000)
    sem_erros(fila)


async def test_rejeitar_pergunta_o_motivo_numa_caixa_de_verdade(fila, acao_na_fila):
    """`prompt()` trava a aba inteira e cabe uma linha.

    O motivo vira sinal de treino — precisa de um campo que aceite um parágrafo,
    e de uma caixa que não congele o polling do resto da tela.
    """
    await acao_na_fila(ORIGINAL)
    await fila.reload(wait_until="domcontentloaded")
    await fila.wait_for_selector(TEXTO, timeout=60000)

    await fila.click('button:has-text("rejeitar")')
    caixa = await fila.wait_for_selector('[role="dialog"]', timeout=10000)
    assert await caixa.query_selector("textarea"), "o motivo precisa de um campo multilinha"

    await fila.fill('[role="dialog"] textarea', "inventou tecnologia que eu não tenho")
    await fila.click('[role="dialog"] button:has-text("rejeitar")')
    await fila.wait_for_selector("text=Rejeitado", timeout=15000)
    sem_erros(fila)


async def test_aprovar_com_edicao_diz_que_virou_par_de_treino(fila, acao_na_fila):
    """Se a tela não distingue aprovar de editar, o dataset morre de omissão."""
    await acao_na_fila(ORIGINAL)
    await fila.reload(wait_until="domcontentloaded")
    await fila.wait_for_selector(TEXTO, timeout=60000)

    assert await fila.is_visible('button:has-text("aprovar")')
    await fila.fill(TEXTO, "o texto que eu de fato mandaria")
    await fila.wait_for_selector('button:has-text("aprovar com a edição")', timeout=5000)

    await fila.click('button:has-text("aprovar com a edição")')
    await fila.wait_for_selector("text=par de preferência", timeout=15000)
    sem_erros(fila)


# ── As candidaturas: colar, abrir, apagar, buscar ─────────────────

@pytest.fixture
async def vaga_aberta(candidaturas):
    """Uma vaga colada, com a gaveta aberta nela."""
    await candidaturas.click('button:has-text("Colar uma vaga")')
    await candidaturas.fill("#nova-descricao", VAGA)
    await candidaturas.click('button:has-text("só salvar")')
    await candidaturas.wait_for_selector('aside:has-text("Dados da vaga")', timeout=30000)
    return candidaturas


async def test_colar_vaga_salva_e_abre_a_gaveta(candidaturas):
    """Salvar e não mostrar o que salvou obriga a procurar na tabela."""
    await candidaturas.click('button:has-text("Colar uma vaga")')
    await candidaturas.fill("#nova-descricao", VAGA)
    await candidaturas.fill("#nova-titulo", "Desenvolvedor Python Pleno")
    await candidaturas.click('button:has-text("só salvar")')

    await candidaturas.wait_for_selector('aside:has-text("Dados da vaga")', timeout=30000)
    assert await candidaturas.input_value("#campo-titulo") == "Desenvolvedor Python Pleno"
    sem_erros(candidaturas)


async def test_descricao_curta_nao_deixa_salvar(candidaturas):
    """Abaixo de 50 caracteres o extrator não tem o que ler — a tela diz isso."""
    await candidaturas.click('button:has-text("Colar uma vaga")')
    await candidaturas.fill("#nova-descricao", "vaga boa")
    await candidaturas.wait_for_selector("text=faltam", timeout=5000)
    assert await candidaturas.is_disabled('button:has-text("só salvar")')
    sem_erros(candidaturas)


async def test_esc_fecha_a_gaveta(vaga_aberta):
    await vaga_aberta.keyboard.press("Escape")
    await vaga_aberta.wait_for_selector(
        'aside:has-text("Dados da vaga")', state="detached", timeout=10000
    )
    sem_erros(vaga_aberta)


async def test_apagar_pede_confirmacao(vaga_aberta):
    """O histórico de eventos vai junto — um clique não pode bastar."""
    await vaga_aberta.click('button:has-text("apagar esta vaga")')
    await vaga_aberta.wait_for_selector('[role="dialog"]', timeout=10000)
    assert await vaga_aberta.is_visible("text=irreversível")

    await vaga_aberta.click('[role="dialog"] button:has-text("cancelar")')
    await vaga_aberta.wait_for_selector('[role="dialog"]', state="detached", timeout=5000)
    assert await vaga_aberta.is_visible('aside:has-text("Dados da vaga")')
    sem_erros(vaga_aberta)


async def test_apagar_vaga_pela_gaveta(vaga_aberta):
    await vaga_aberta.click('button:has-text("apagar esta vaga")')
    await vaga_aberta.click('[role="dialog"] button:has-text("apagar")')
    await vaga_aberta.wait_for_selector("text=Vaga apagada", timeout=15000)
    await vaga_aberta.wait_for_selector(
        'aside:has-text("Dados da vaga")', state="detached", timeout=10000
    )
    sem_erros(vaga_aberta)


async def test_busca_filtra_a_tabela_sem_ir_ao_servidor(vaga_aberta):
    """Filtrar no cliente é o que faz a busca responder enquanto eu digito."""
    await vaga_aberta.keyboard.press("Escape")
    await vaga_aberta.wait_for_selector("table tbody tr", timeout=15000)

    pedidos = []
    vaga_aberta.on("request", lambda r: pedidos.append(r.url))

    await vaga_aberta.fill('input[type="search"]', "zzzznaoexiste")
    await vaga_aberta.wait_for_timeout(600)
    assert await vaga_aberta.locator("table tbody tr").count() == 0

    assert not [u for u in pedidos if "/api/vagas" in u], (
        f"a busca foi ao servidor: {pedidos}"
    )
    sem_erros(vaga_aberta)


# ── O estudo ──────────────────────────────────────────────────────

@pytest.fixture
async def questao():
    """Um módulo, um tópico e uma questão vencendo hoje — sem passar pelo LLM."""
    from app.db.models.estudo.questao import Modulo, Topico
    from app.db.session import get_session
    from app.estudo import servico

    async with get_session() as s:
        m = Modulo(nome="Matemática e raciocínio lógico", trilha="concurso")
        s.add(m)
        await s.flush()
        t = Topico(modulo_id=m.id, nome="Lógica proposicional")
        s.add(t)
        await s.flush()
        await s.commit()
        topico_id = t.id

    return await servico.criar_questao(
        {
            "topico_id": topico_id,
            "formato": "certo_errado",
            "comando": "Acerca da proposição “se p então q”, julgue o item.",
            "enunciado": "A negação de “se p então q” é “p e não q”.",
            "alternativas": [],
            "afirmacoes": [],
            "gabarito": "C",
            "dificuldade": 2,
        }
    )


async def test_o_gabarito_nao_desce_para_o_cliente_na_revisao(painel, questao):
    """Gabarito no DevTools apaga a diferença entre "eu sabia" e "eu vi".

    E é essa diferença que agenda a próxima revisão.
    """
    respostas = []
    painel.on(
        "response",
        lambda r: respostas.append(r.url) if "/api/estudo/fila" in r.url else None,
    )

    await painel.click('aside nav a:has-text("Revisar")')
    await painel.wait_for_selector("text=A negação de", timeout=60000)

    corpo = await painel.evaluate(
        "async () => (await fetch('/api/estudo/fila')).text()"
    )
    assert '"gabarito":null' in corpo.replace(" ", ""), (
        "a fila mandou o gabarito junto com a questão"
    )
    sem_erros(painel)


async def test_responder_mostra_quando_a_questao_volta(painel, questao):
    """Sem a data na tela, a repetição espaçada é invisível — e não se confia."""
    await painel.click('aside nav a:has-text("Revisar")')
    await painel.wait_for_selector("text=A negação de", timeout=60000)

    await painel.click('button:has-text("Certo")')
    await painel.click('button:has-text("Responder")')

    await painel.wait_for_selector("text=Certo.", timeout=20000)
    await painel.wait_for_selector("text=Volta em 7 dias", timeout=10000)
    sem_erros(painel)


async def test_errar_devolve_em_dois_dias_e_deixa_tentar_de_novo(painel, questao):
    """A resposta só aparece depois da segunda tentativa — errar é para pensar."""
    await painel.click('aside nav a:has-text("Revisar")')
    await painel.wait_for_selector("text=A negação de", timeout=60000)

    await painel.click('button:has-text("Errado")')
    await painel.click('button:has-text("Responder")')

    await painel.wait_for_selector("text=Tente de novo", timeout=20000)
    assert not await painel.is_visible("text=esta é a resposta")
    sem_erros(painel)


async def test_criar_modulo_aparece_na_sidebar_sem_trocar_de_rota(modulos):
    """A sidebar mostra contadores escritos noutra tela.

    Recarregá-la só na troca de rota deixava no menu um módulo já apagado.
    """
    await modulos.click('button:has-text("Novo módulo")')
    await modulos.fill("#modulo-nome", "Estatística e probabilidade")
    await modulos.click('[role="dialog"] button:has-text("criar")')

    await modulos.wait_for_selector(
        "aside >> text=Estatística e probabilidade", timeout=20000
    )
    sem_erros(modulos)


async def test_apagar_modulo_com_questoes_avisa_quantas_vao_junto(modulos, questao):
    """Meses de repetição espaçada são o que não se refaz."""
    await modulos.reload(wait_until="domcontentloaded")
    await modulos.wait_for_selector('button:has-text("apagar")', timeout=60000)

    await modulos.click('article button:has-text("apagar")')
    await modulos.wait_for_selector('[role="dialog"]', timeout=10000)
    assert await modulos.is_visible("text=1 questão")
    assert await modulos.is_visible("text=histórico de respostas")
    sem_erros(modulos)


# ── A sessão, atravessando as telas ───────────────────────────────

async def test_sessao_atravessa_a_navegacao_entre_telas(painel):
    """Cookie por página quebraria aqui, e em nenhum teste de API."""
    for rotulo, marca in (
        ("Módulos", 'h1:has-text("Módulos")'),
        ("Formatos", 'h1:has-text("Formatos de questão")'),
        ("Candidaturas", 'h1:has-text("O que foi enviado")'),
        ("Hoje", "text=Progresso por módulo"),
    ):
        await painel.click(f'aside nav a:has-text("{rotulo}")')
        await painel.wait_for_selector(marca, timeout=60000)
    sem_erros(painel)


async def test_sem_sessao_a_tela_manda_para_o_login(pagina, servidor):
    """Tela vazia sem dizer por quê é o pior resultado possível."""
    await pagina.goto(f"{servidor}/modulos", wait_until="domcontentloaded")

    # Sem cookie, a rota protegida tem que trocar de tela sozinha — e o campo
    # de senha é a prova de que trocou, não a URL apenas.
    await pagina.wait_for_selector("#senha", timeout=60000)
    assert pagina.url.endswith("/login")
