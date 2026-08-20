"""O gateway, contra um provider falso.

De propósito sem Ollama: teste que só passa com o modelo no ar é integração
disfarçada — lento, instável e mudo sobre a lógica que se quer garantir. O
modelo de verdade é exercitado pelos scripts (`bench_modelos`, `bakeoff`).
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.ai_call import AiCall
from app.db.session import get_session
from app.llm import gateway
from app.llm.tipos import JSONInvalido, LLMCircuitoAberto, LLMIndisponivel, RespostaCrua

SCHEMA = {
    "type": "object",
    "required": ["senioridade", "requisitos"],
    "properties": {
        "senioridade": {"type": "string"},
        "requisitos": {"type": "array"},
    },
}


class ProviderFalso:
    """Devolve respostas de uma fila; guarda o que recebeu."""

    nome = "falso"

    def __init__(self, respostas: list[str | Exception]) -> None:
        self.respostas = list(respostas)
        self.prompts: list[str] = []
        self.modelos: list[str] = []
        self.concorrentes = 0
        self.pico_concorrencia = 0
        self.atraso = 0.0

    async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
        self.concorrentes += 1
        self.pico_concorrencia = max(self.pico_concorrencia, self.concorrentes)
        try:
            if self.atraso:
                await asyncio.sleep(self.atraso)
            self.prompts.append(prompt)
            self.modelos.append(modelo)
            r = self.respostas.pop(0) if self.respostas else '{"ok": true}'
            if isinstance(r, Exception):
                raise r
            return RespostaCrua(texto=r, modelo=modelo, tokens_input=10, tokens_output=5)
        finally:
            self.concorrentes -= 1

    async def embedar(self, textos, *, modelo):
        return [[0.1] * 1024 for _ in textos]


@pytest.fixture(autouse=True)
def _limpar():
    gateway.resetar_breakers()
    registrados = dict(gateway._providers)
    yield
    # `None` devolve o roteamento normal. Deixar um provider forçado aqui
    # esconderia o registro por nome do teste seguinte.
    gateway.usar_provider(None)
    gateway._providers.clear()
    gateway._providers.update(registrados)
    gateway.resetar_breakers()


def usar(respostas) -> ProviderFalso:
    p = ProviderFalso(respostas)
    gateway.usar_provider(p)
    return p


@pytest.fixture
def tudo_local(monkeypatch):
    """Desliga o escape para a API — a rota volta a ser a de antes da chave.

    Os testes da tabela local usam isto porque o `.env` da máquina tem chave: sem
    a fixture, eles mediriam o roteamento externo e falhariam por estarem certos.
    """
    monkeypatch.setattr(settings, "gemini_tarefas", "")
    monkeypatch.setattr(settings, "gemini_agentes", "")
    return settings


# ── Roteamento ────────────────────────────────────────────────────


async def test_extrair_e_classificar_vao_para_o_modelo_de_extracao(tudo_local):
    p = usar(['{"senioridade": "pleno", "requisitos": []}'] * 2)
    await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    await gateway.gerar("x", tarefa="classificar", agente="t", json_schema=SCHEMA)
    assert p.modelos == [settings.ollama_model_extracao] * 2


async def test_redigir_e_resumir_vao_para_o_modelo_de_redacao(tudo_local):
    p = usar(["um texto qualquer", "outro texto"])
    await gateway.gerar("x", tarefa="redigir", agente="t")
    await gateway.gerar("x", tarefa="resumir", agente="t")
    assert p.modelos == [settings.ollama_model_redacao] * 2


async def test_modelo_explicito_ganha_da_rota():
    p = usar(["texto"])
    await gateway.gerar("x", tarefa="redigir", agente="t", modelo="modelo-do-bakeoff")
    assert p.modelos == ["modelo-do-bakeoff"]


# ── JSON, retry e reprompt ────────────────────────────────────────


async def test_json_sujo_e_limpo_sem_gastar_tentativa():
    usar(['```json\n{"senioridade": "junior", "requisitos": ["python"]}\n```'])
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.json == {"senioridade": "junior", "requisitos": ["python"]}
    assert r.tentativas == 1


async def test_reprompt_ate_o_modelo_acertar():
    p = usar(
        [
            "desculpe, não entendi",  # nem JSON é
            '{"senioridade": "pleno"}',  # falta chave obrigatória
            '{"senioridade": "pleno", "requisitos": ["fastapi"]}',
        ]
    )
    r = await gateway.gerar("Extraia da vaga", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.tentativas == 3
    assert r.json["requisitos"] == ["fastapi"]
    # O reprompt precisa dizer O QUE deu errado — senão o modelo repete o erro.
    assert "não veio JSON válido" in p.prompts[1]
    assert "requisitos" in p.prompts[2]
    assert "Extraia da vaga" in p.prompts[2]


async def test_chave_do_tipo_errado_e_rejeitada():
    p = usar(
        [
            '{"senioridade": ["pleno"], "requisitos": []}',
            '{"senioridade": "pleno", "requisitos": []}',
        ]
    )
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.tentativas == 2
    assert "deveria ser string" in p.prompts[1]


async def test_envelope_inventado_e_removido_sem_gastar_retry():
    # Caso real do phi4-mini: pedem {senioridade, requisitos}, ele devolve
    # tudo dentro de {"vaga": {...}}.
    usar(['{"vaga": {"senioridade": "pleno", "requisitos": ["python"]}}'])
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert r.tentativas == 1
    assert r.json == {"senioridade": "pleno", "requisitos": ["python"]}


async def test_objeto_de_uma_chave_legitimo_nao_e_desembrulhado():
    schema = {"type": "object", "required": ["resultado"]}
    usar(['{"resultado": {"a": 1}}'])
    r = await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=schema)
    assert r.json == {"resultado": {"a": 1}}


async def test_temperatura_sobe_a_cada_retentativa():
    # Com temperatura baixa o modelo repete a mesma resposta errada, e o retry
    # vira três vezes o mesmo custo pelo mesmo erro.
    class Espia(ProviderFalso):
        temperaturas: list[float | None] = []

        async def gerar(self, prompt, *, modelo, json_mode=False, temperatura=None, opcoes=None):
            self.temperaturas.append(temperatura)
            return await super().gerar(
                prompt, modelo=modelo, json_mode=json_mode, temperatura=temperatura
            )

    p = Espia(["lixo", "lixo", '{"senioridade": "x", "requisitos": []}'])
    p.temperaturas = []
    gateway.usar_provider(p)
    await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert p.temperaturas == sorted(p.temperaturas)
    assert p.temperaturas[0] < p.temperaturas[-1]


async def test_desiste_com_erro_explicito():
    usar(["não sei", "também não", "desisto"])
    with pytest.raises(JSONInvalido):
        await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)


async def test_texto_livre_nao_passa_pelo_parser():
    usar(["Olá, tudo bem? Segue o retorno que combinamos."])
    r = await gateway.gerar("x", tarefa="redigir", agente="t")
    assert r.json is None
    assert r.texto.startswith("Olá")


async def test_resposta_vazia_conta_como_tentativa():
    # É o caso real do modelo com raciocínio: gasta o orçamento pensando e
    # devolve `response` vazio.
    usar(["", "   ", "agora sim"])
    r = await gateway.gerar("x", tarefa="redigir", agente="t")
    assert r.tentativas == 3
    assert r.texto == "agora sim"


# ── Indisponibilidade e breaker ───────────────────────────────────


async def test_servidor_fora_falha_na_hora_sem_reprompt(tudo_local):
    p = usar([LLMIndisponivel("conexão recusada")] * 3)
    with pytest.raises(LLMIndisponivel):
        await gateway.gerar("x", tarefa="extrair", agente="t", json_schema=SCHEMA)
    assert len(p.prompts) == 1  # não insiste com quem está fora do ar


async def test_breaker_abre_apos_o_limite_de_falhas():
    usar([LLMIndisponivel("fora")] * 10)
    for _ in range(settings.llm_breaker_falhas):
        with pytest.raises(LLMIndisponivel):
            await gateway.gerar("x", tarefa="redigir", agente="t")

    with pytest.raises(LLMCircuitoAberto):
        await gateway.gerar("x", tarefa="redigir", agente="t")


async def test_sucesso_zera_a_contagem_de_falhas():
    usar([LLMIndisponivel("fora"), "voltou"])
    with pytest.raises(LLMIndisponivel):
        await gateway.gerar("x", tarefa="redigir", agente="t")
    await gateway.gerar("x", tarefa="redigir", agente="t")
    assert not gateway._breakers


# ── Observabilidade e concorrência ────────────────────────────────


async def test_grava_ai_call_no_sucesso():
    usar(["texto gerado"])
    await gateway.gerar("meu prompt", tarefa="redigir", agente="candidatura", alvo_ref="vaga:1")

    async with get_session() as s:
        call = await s.scalar(select(AiCall))
    assert call.sucesso is True
    assert call.agente == "candidatura"
    assert call.tarefa == "redigir"
    assert call.provider == "falso"
    assert call.alvo_ref == "vaga:1"
    assert call.tokens_total == 15


async def test_grava_ai_call_na_falha():
    usar(["lixo", "lixo", "lixo"])
    with pytest.raises(JSONInvalido):
        await gateway.gerar("p", tarefa="extrair", agente="vaga", json_schema=SCHEMA)

    async with get_session() as s:
        call = await s.scalar(select(AiCall))
    assert call.sucesso is False
    assert "JSONInvalido" in call.error_message
    # A última saída do modelo fica gravada — é por onde se descobre o porquê.
    assert call.resposta == "lixo"


async def test_semaforo_serializa_as_inferencias():
    p = usar(["a", "b", "c"])
    p.atraso = 0.05
    await asyncio.gather(
        *(gateway.gerar("x", tarefa="redigir", agente="t") for _ in range(3))
    )
    assert p.pico_concorrencia == 1


async def test_embedar_em_lote():
    usar([])
    vetores = await gateway.embedar(["a", "b", "c"])
    assert len(vetores) == 3
    assert len(vetores[0]) == 1024


def test_compreender_vai_para_o_modelo_pesado(tudo_local):
    """"extrair" e achar o que esta escrito; "compreender" e ler 3.000 palavras
    e dizer do que elas tratam. O fichamento de uma transcricao caia na
    primeira e rodava no menor modelo instalado: 2 destaques contra 5, e um
    titulo que repetia a mesma palavra duas vezes."""
    settings = tudo_local

    assert gateway.rota("compreender").modelo == settings.ollama_model_pesado
    assert gateway.rota("compreender").json_mode
    # Catalogar nao ganha nada com variedade.
    assert gateway.rota("compreender").temperatura <= 0.2

    # E continua distinto das outras duas rotas.
    assert gateway.rota("extrair").modelo == settings.ollama_model_extracao
    assert gateway.rota("redigir").modelo == settings.ollama_model_redacao


# ── o escape para a API ───────────────────────────────────────────


def test_sem_chave_nada_sai_da_maquina(monkeypatch):
    """A garantia que o README promete: sem chave, é tudo local.

    Vale para a suíte, para uma máquina sem internet, e para o dia em que a
    chave for revogada — nenhum desses casos pode precisar de tratamento.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender,redigir,extrair")

    for tarefa in ("compreender", "redigir", "extrair", "classificar", "resumir"):
        assert gateway.rota(tarefa).provider == "ollama"


def test_com_chave_so_a_tarefa_listada_sai(monkeypatch):
    """Uma tarefa, não todas — `redigir` fica local porque lá o que decide é a
    minha voz, que está nos exemplos de estilo, não a capacidade do modelo."""
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender")

    assert gateway.rota("compreender").provider == "gemini"
    # Qual modelo do Gemini é outra decisão, com testes próprios mais abaixo.
    assert gateway.rota("compreender").modelo.startswith("gemini-")
    for tarefa in ("redigir", "extrair", "classificar", "resumir"):
        assert gateway.rota(tarefa).provider == "ollama"


def test_a_forma_da_tarefa_nao_muda_com_o_destino(monkeypatch):
    """JSON e temperatura são da tarefa, não do servidor.

    Se `compreender` deixasse de pedir JSON ao sair da máquina, o
    `_validar_schema` pararia de valer e o fichamento voltaria a aceitar
    `{"erro": "não sei"}` como sucesso — o buraco que o gateway existe para
    tapar.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender")

    fora = gateway.rota("compreender")
    monkeypatch.setattr(settings, "gemini_tarefas", "")
    dentro = gateway.rota("compreender")

    assert fora.json_mode == dentro.json_mode is True
    assert fora.temperatura == dentro.temperatura


def test_rota_local_devolve_o_destino_da_queda(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender")

    queda = gateway.rota_local("compreender")
    assert queda.provider == "ollama"
    # A forma da tarefa sobrevive à queda: sem `json_mode`, o `_validar_schema`
    # pararia de valer e o fichamento aceitaria qualquer texto como sucesso.
    assert queda.json_mode is True


# ── a queda para o local ──────────────────────────────────────────


@pytest.fixture
def rota_para_fora(monkeypatch):
    """`compreender` sai da máquina, e cada destino tem o seu próprio duplo."""
    from app.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender")
    gateway.usar_provider(None)  # sem martelo: o roteamento por nome tem que valer

    def montar(fora, local):
        gateway._providers["gemini"] = fora
        gateway._providers["ollama"] = local

    return montar


@pytest.mark.asyncio
async def test_api_fora_do_ar_cai_para_o_local(rota_para_fora):
    """O 503 "high demand" apareceu no primeiro teste real da integração.

    Uma aula de 28 minutos não pode perder o fichamento porque um servidor de
    terceiro teve pico de demanda.
    """
    fora = ProviderFalso([LLMIndisponivel("Gemini 503 (sobrecarga/cota)")])
    local = ProviderFalso(['{"titulo": "veio do local"}'])
    rota_para_fora(fora, local)

    r = await gateway.gerar(
        "ficha isto",
        tarefa="compreender",
        agente="teste",
        json_schema={"type": "object", "required": ["titulo"]},
    )

    assert r.json == {"titulo": "veio do local"}
    assert local.prompts, "o modelo local tinha que ter sido chamado"


@pytest.mark.asyncio
async def test_json_fora_do_schema_nao_cai(rota_para_fora):
    """Queda é para servidor fora, não para resposta ruim.

    JSON sem a chave pedida é problema de prompt: o modelo local erraria igual,
    mais devagar, e ainda gastaria o dobro de tempo antes de falhar.
    """
    fora = ProviderFalso(['{"nada": 1}', '{"nada": 2}', '{"nada": 3}'])
    local = ProviderFalso(['{"titulo": "não deveria chegar aqui"}'])
    rota_para_fora(fora, local)

    with pytest.raises(JSONInvalido):
        await gateway.gerar(
            "ficha isto",
            tarefa="compreender",
            agente="teste",
            json_schema={"type": "object", "required": ["titulo"]},
        )

    assert not local.prompts, "o local não devia ter sido chamado"


@pytest.mark.asyncio
async def test_circuito_aberto_na_api_usa_o_local_direto(rota_para_fora):
    """Breaker aberto não é desistir — é ter para onde ir.

    Depois de três falhas seguidas o circuito da API fica aberto por minutos. No
    desenho antigo isso derrubava a chamada; agora manda para o outro destino
    sem nem tentar a rede.
    """
    from app.config import settings

    fora = ProviderFalso([LLMIndisponivel("cota")] * 9)
    local = ProviderFalso(['{"titulo": "local"}'] * 9)
    rota_para_fora(fora, local)

    for _ in range(settings.llm_breaker_falhas):
        await gateway.gerar(
            "x", tarefa="compreender", agente="teste",
            json_schema={"type": "object", "required": ["titulo"]},
        )

    chamadas_antes = len(fora.prompts)
    r = await gateway.gerar(
        "x", tarefa="compreender", agente="teste",
        json_schema={"type": "object", "required": ["titulo"]},
    )
    assert r.json == {"titulo": "local"}
    assert len(fora.prompts) == chamadas_antes, "com o circuito aberto, nem tenta a rede"


@pytest.mark.asyncio
async def test_modelo_explicito_nao_cai(rota_para_fora):
    """`modelo=` é o bake-off pedindo um modelo por nome. Cair mediria outra coisa."""
    fora = ProviderFalso([LLMIndisponivel("cota")])
    local = ProviderFalso(['{"titulo": "local"}'])
    rota_para_fora(fora, local)

    with pytest.raises(LLMIndisponivel):
        await gateway.gerar(
            "x", tarefa="compreender", agente="teste", modelo="gemini-2.5-flash",
            json_schema={"type": "object", "required": ["titulo"]},
        )
    assert not local.prompts


@pytest.mark.asyncio
async def test_chamada_de_api_nao_prende_o_semaforo(rota_para_fora):
    """O semáforo existe pelos 6 GB de VRAM. A API não disputa VRAM.

    Prendê-la na mesma fila faria o fichamento bloquear a reescrita do bloco
    seguinte — o oposto do que a Fase T conquistou ao mover o trabalho para
    dentro da aula.
    """
    fora = ProviderFalso(['{"titulo": "a"}', '{"titulo": "b"}'])
    fora.atraso = 0.05
    rota_para_fora(fora, ProviderFalso([]))

    schema = {"type": "object", "required": ["titulo"]}
    await asyncio.gather(
        gateway.gerar("1", tarefa="compreender", agente="t", json_schema=schema),
        gateway.gerar("2", tarefa="compreender", agente="t", json_schema=schema),
    )
    assert fora.pico_concorrencia == 2


# ── roteamento por agente ─────────────────────────────────────────


@pytest.fixture
def com_chave(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender")
    monkeypatch.setattr(settings, "gemini_agentes", "candidatura.curriculo")
    return settings


def test_redigir_separa_curriculo_de_bloco_de_aula(com_chave):
    """A mesma tarefa, dois destinos — e é por isso que o agente entra na rota.

    O bloco da transcrição roda 8× por aula na GPU que a Fase T liberou; mandá-lo
    para a API desfaria o P1 e cobraria por cada bloco. O currículo é o texto que
    vai para uma entrevista de verdade.
    """
    assert gateway.rota("redigir", "conhecimento.transcricao.bloco3").provider == "ollama"
    assert gateway.rota("redigir", "candidatura.curriculo.experiencias").provider == "gemini"


def test_agente_casa_por_prefixo(com_chave):
    """`candidatura.curriculo` pega todas as etapas sem listar uma a uma."""
    for etapa in ("resumo", "experiencias", "habilidades"):
        assert gateway.rota("redigir", f"candidatura.curriculo.{etapa}").provider == "gemini"
    # E não pega o vizinho de nome parecido.
    assert gateway.rota("classificar", "candidatura.match").provider == "ollama"


def test_sem_agente_a_rota_e_a_de_antes(com_chave):
    """`rota(tarefa)` de um argumento continua válida — é o que a suíte usa."""
    assert gateway.rota("redigir").provider == "ollama"
    assert gateway.rota("compreender").provider == "gemini"


def test_sem_chave_o_agente_tambem_e_ignorado(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_agentes", "candidatura.curriculo")
    assert gateway.rota("redigir", "candidatura.curriculo.resumo").provider == "ollama"


# ── o modelo pesado ───────────────────────────────────────────────


@pytest.fixture
def com_pesado(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_tarefas", "compreender,classificar,resumir,extrair")
    monkeypatch.setattr(settings, "gemini_agentes", "candidatura.curriculo")
    monkeypatch.setattr(settings, "gemini_pesado", "candidatura.curriculo")
    monkeypatch.setattr(settings, "gemini_model", "flash-de-teste")
    monkeypatch.setattr(settings, "gemini_model_pesado", "pro-de-teste")
    return settings


def test_so_o_curriculo_leva_o_pesado(com_pesado):
    """O currículo leva o Pro; todo o resto leva o Flash — inclusive o fichamento.

    O fichamento saiu do pesado por medida: 5 de 5 contra 4 de 4 na mesma aula,
    por 5× o tempo. Os 32 s a mais caem inteiros na espera depois do `parar`, que
    é justamente o que a Fase T tinha acabado de encurtar.
    """
    assert gateway.rota("redigir", "candidatura.curriculo.resumo").modelo == "pro-de-teste"
    for tarefa, agente in (
        ("compreender", "conhecimento.transcricao.fichamento"),
        ("extrair", "candidatura.extrator"),
        ("resumir", "copiloto.api"),
    ):
        assert gateway.rota(tarefa, agente).modelo == "flash-de-teste"


def test_pesado_nao_muda_quem_fica_local(com_pesado):
    """A escolha de modelo é depois da escolha de destino, nunca antes.

    Sem isto, listar um agente em `gemini_pesado` o mandaria para fora sem
    passar pela decisão de sair — e a reescrita ao vivo iria junto.
    """
    r = gateway.rota("redigir", "conhecimento.transcricao.bloco3")
    assert r.provider == "ollama"
    assert r.modelo == settings.ollama_model_redacao


def test_queda_do_pesado_e_o_local_e_nao_o_flash(com_pesado):
    """Cair para o Flash esconderia a falha da API atrás de um resultado pior
    e ainda pago. O destino da queda é a máquina."""
    queda = gateway.rota_local("compreender", "conhecimento.transcricao.fichamento")
    assert queda.provider == "ollama"


def test_a_queda_do_fichamento_usa_o_modelo_que_ja_esta_carregado(com_pesado):
    """O 8B não cabe mais na placa, e isso custou uma nota inteira.

    Em 17/08/2026, na primeira gravação depois de o Whisper ir para a GPU, o
    `llama3.1:8b` estourou os 180 s de timeout e o fichamento se perdeu: a placa
    tinha o Whisper (1,2 GB) e o `gemma4:e4b` da reescrita ao vivo (~4,3 GB), e
    os 4,9 GB do 8B não entram em cima disso.

    A queda tem que usar o que já está carregado. Vale menos na tarefa, e vale
    infinitamente mais que um timeout.
    """
    queda = gateway.rota_local("compreender", "conhecimento.transcricao.fichamento")
    assert queda.modelo == settings.ollama_model_redacao
    assert queda.modelo != settings.ollama_model_pesado
