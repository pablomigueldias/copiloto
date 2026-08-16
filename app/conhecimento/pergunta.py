"""Perguntar ao próprio conhecimento e receber resposta ancorada.

A F2 deu memória; aqui está a boca. A regra que define a fase inteira:

    a resposta não pode existir sem os trechos.

Se o índice não tem o assunto, a resposta certa é *"não tenho isso indexado"* —
nunca o que o modelo lembra do pré-treino. Um copiloto que inventa perde a única
coisa que o torna melhor que um modelo de fronteira: saber do mundo do Pablo, e
só dele.

Três defesas, da mais barata para a mais cara:

1. **piso de distância** — antes de gastar GPU. Busca vetorial nunca devolve
   vazio: ela sempre tem um vizinho mais próximo, e "figuras de linguagem"
   traz lógica difusa com a mesma cara de resposta. Medido neste índice,
   pergunta com resposta fica em 0,27–0,48 e sem resposta em 0,48–0,75.
2. **o prompt** — recebe os trechos e a ordem explícita de admitir quando eles
   não respondem. Pega a zona cinzenta que o piso deixa passar de propósito.
3. **validação de citação** — toda afirmação cita `[n]`, e todo `[n]` tem que
   existir. Resposta sem citação nenhuma é tratada como não-resposta.

Um corte agressivo é pior que um frouxo: recusar pergunta que tinha resposta
ensina a não usar o sistema.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.conhecimento.busca import LIMITE, Trecho, buscar
from app.db.observability import registrar_evento
from app.llm import gateway
from app.llm.tipos import LLMErro
from app.utils.logger import get_logger

logger = get_logger()

# Acima disto, nenhum trecho está perto o bastante para embasar resposta. Ver
# a medição no §2 de `docs/fase03.md`: 0,55 recusa 4 das 5 perguntas sem
# resposta e nenhuma das 6 que tinham.
DISTANCIA_MAXIMA = 0.55

# Quanto de cada trecho vai no prompt. O chunker já corta em ~1.200; o teto aqui
# é rede de segurança para fonte de página inteira de PDF.
CHARS_POR_TRECHO = 1500

_CITACAO = re.compile(r"\[(\d{1,2})\]")

INSTRUCOES = """\
Você é o copiloto do Pablo. Responde usando APENAS os trechos abaixo, que vêm \
das anotações, dos documentos e do código dele.

Regras, todas obrigatórias:
- Responda só o que estiver nos trechos. Não complete com conhecimento geral.
- Cite a fonte de cada afirmação com o número entre colchetes: [1], [2].
- Se os trechos não responderem à pergunta, escreva exatamente:
  NAO_INDEXADO
  e nada além disso.
- Frases curtas, direto ao ponto. Sem preâmbulo, sem "com base nos trechos".
- Escreva em português do Brasil.
- No máximo 200 palavras.\
"""


@dataclass(slots=True)
class Resposta:
    pergunta: str
    texto: str
    fontes: list[Trecho] = field(default_factory=list)
    trechos: list[Trecho] = field(default_factory=list)
    respondeu: bool = True
    motivo: str | None = None  # 'sem_indice' | 'sem_citacao' | 'recusou' | 'erro_llm'
    distancia: float | None = None
    modelo: str | None = None
    latencia_ms: int | None = None
    tokens: int | None = None

    def __str__(self) -> str:
        if not self.respondeu:
            return f"[{self.motivo}] {self.texto}"
        citadas = ", ".join(t.fonte_ref for t in self.fontes)
        return f"{self.texto}\n\nFontes: {citadas}"


def _rotulo(t: Trecho) -> str:
    """Como o trecho se identifica dentro do prompt.

    Caminho e trilha de título juntos: sem isso o modelo cita "[2]" e nem ele
    nem eu sabemos de onde saiu.
    """
    pagina = (t.metadados or {}).get("pagina")
    sufixo = f", p. {pagina}" if pagina else ""
    return f"{t.titulo or t.fonte_ref}{sufixo} — {t.fonte_ref}"


def montar_prompt(pergunta: str, trechos: Sequence[Trecho]) -> str:
    """Instruções + trechos numerados + pergunta, nesta ordem.

    A pergunta fica **por último** de propósito: modelo pequeno com 8k de
    contexto presta mais atenção no fim do prompt, e o que ele precisa ter
    fresco na cabeça é o que foi perguntado.
    """
    blocos = [
        f"[{i}] {_rotulo(t)}\n{t.conteudo[:CHARS_POR_TRECHO]}"
        for i, t in enumerate(trechos, start=1)
    ]
    return (
        f"{INSTRUCOES}\n\n"
        f"--- TRECHOS ---\n\n" + "\n\n".join(blocos) + "\n\n"
        f"--- PERGUNTA ---\n{pergunta}\n\nResposta:"
    )


def _fora_do_indice(trechos: Sequence[Trecho]) -> bool:
    """Nenhum trecho perto o bastante, e nenhum acerto de palavra exata.

    O acerto lexical vale como salvo-conduto: se a pergunta contém um termo que
    aparece literalmente numa nota (`pgvector`, `RRF`, nome próprio), o índice
    tem o assunto mesmo que o embedding não concorde.
    """
    if not trechos:
        return True
    if any(t.posicao_lexical is not None for t in trechos):
        return False
    distancias = [t.distancia for t in trechos if t.distancia is not None]
    return not distancias or min(distancias) > DISTANCIA_MAXIMA


def _citados(texto: str, trechos: Sequence[Trecho]) -> tuple[list[Trecho], list[int]]:
    """Separa o que a resposta citou do que ela inventou de citar."""
    usados: list[Trecho] = []
    invalidos: list[int] = []
    for bruto in dict.fromkeys(_CITACAO.findall(texto)):  # sem repetir, na ordem
        n = int(bruto)
        if 1 <= n <= len(trechos):
            usados.append(trechos[n - 1])
        else:
            invalidos.append(n)
    return usados, invalidos


async def perguntar(
    pergunta: str,
    *,
    limite: int = LIMITE,
    fonte_tipo: str | Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    agente: str = "copiloto",
) -> Resposta:
    """Busca, monta o prompt ancorado, gera e valida as citações."""
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return Resposta(pergunta=pergunta, texto="", respondeu=False, motivo="sem_indice")

    trechos = await buscar(pergunta, limite=limite, fonte_tipo=fonte_tipo, tags=tags)
    distancias = [t.distancia for t in trechos if t.distancia is not None]
    melhor = min(distancias) if distancias else None

    if _fora_do_indice(trechos):
        # Nem chama o LLM: pergunta fora do índice não melhora com token gasto.
        await registrar_evento(
            "conhecimento.pergunta",
            status="vazio",
            detalhe=f"{pergunta[:120]!r} — melhor distância {melhor}",
        )
        return Resposta(
            pergunta=pergunta,
            texto="Não tenho isso indexado.",
            trechos=list(trechos),
            respondeu=False,
            motivo="sem_indice",
            distancia=melhor,
        )

    try:
        r = await gateway.gerar(
            montar_prompt(pergunta, trechos),
            tarefa="resumir",
            agente=agente,
            # Ancorado: a temperatura serve para escrever bem, não para
            # completar o que não está nos trechos.
            temperatura=0.2,
        )
    except LLMErro as e:
        logger.warning(f"Pergunta falhou no LLM: {type(e).__name__}: {e}")
        await registrar_evento("conhecimento.pergunta", status="erro", detalhe=str(e)[:300])
        return Resposta(
            pergunta=pergunta,
            texto="O modelo local não respondeu agora.",
            trechos=list(trechos),
            respondeu=False,
            motivo="erro_llm",
            distancia=melhor,
        )

    texto = r.texto.strip()
    medidas = {
        "distancia": melhor,
        "modelo": r.modelo,
        "latencia_ms": r.latencia_ms,
        "tokens": (r.tokens_input or 0) + (r.tokens_output or 0) or None,
    }

    if "NAO_INDEXADO" in texto.upper().replace("Ã", "A"):
        await registrar_evento("conhecimento.pergunta", status="vazio", detalhe="modelo recusou")
        return Resposta(
            pergunta=pergunta,
            texto="Não tenho isso indexado.",
            trechos=list(trechos),
            respondeu=False,
            motivo="recusou",
            **medidas,
        )

    fontes, invalidas = _citados(texto, trechos)
    if invalidas:
        # Citar [7] com 5 trechos é o modelo inventando referência — o sintoma
        # mais barato de detectar de que ele saiu do material.
        logger.warning(f"Resposta citou trecho inexistente {invalidas}: {pergunta[:80]!r}")

    if not fontes:
        await registrar_evento(
            "conhecimento.pergunta", status="erro", detalhe="resposta sem citação"
        )
        return Resposta(
            pergunta=pergunta,
            texto=texto,
            trechos=list(trechos),
            respondeu=False,
            motivo="sem_citacao",
            **medidas,
        )

    await registrar_evento(
        "conhecimento.pergunta",
        status="ok",
        detalhe=f"{len(fontes)} fonte(s), distância {melhor:.3f}" if melhor else None,
        duracao_ms=r.latencia_ms,
    )
    return Resposta(
        pergunta=pergunta,
        texto=texto,
        fontes=fontes,
        trechos=list(trechos),
        **medidas,
    )
