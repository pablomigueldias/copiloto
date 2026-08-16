"""Few-shot dinâmico: três textos meus, escolhidos pela situação.

O degrau 3 da escada da §4 do plano — o de maior retorno por esforço, e o único
que fica melhor sozinho com o uso: cada ação que eu aprovo vira exemplo, e o
próximo texto nasce mais parecido comigo.

Duas decisões que valem explicação:

**O embedding não vai numa mensagem de fila.** Aprovar precisa ser instantâneo,
então o vetor fica para depois — mas "depois" é uma coluna `NULL` no banco, não
um job enfileirado. Mensagem se perde quando o Redis reinicia; coluna `NULL`
continua lá esperando. O worker varre e preenche; se ele nunca rodar, a busca
cai no fallback por data e o sistema segue funcionando pior, não quebrado.

**Compara contexto com contexto.** O embedding é da *situação* que produziu o
texto ("e-mail frio para agência pequena que pediu orçamento"), não do texto. Na
hora de gerar, o que existe é uma situação nova — comparar situação com situação
é o que acha o exemplo certo.
"""
from __future__ import annotations

import re

from sqlalchemy import select

from app.db.models.acao_pendente import AcaoPendente
from app.db.models.exemplo_estilo import ExemploEstilo
from app.db.session import get_session
from app.llm import gateway
from app.utils.logger import get_logger

logger = get_logger()

# Três é o número do plano: o bastante para o modelo pegar o padrão, pouco o
# bastante para caber no contexto junto com o RAG.
N_EXEMPLOS = 3


# O `tipo` da ação e a `tarefa` que o gerador procura no few-shot **não são a
# mesma palavra**, e essa diferença de nome custou seis currículos corrigidos que
# nunca voltaram para o modelo:
#
#     ação de currículo  →  tipo = "curriculo"
#     app/candidatura/curriculo.py  →  exemplos_para("bullet_curriculo", ...)
#
# Cada correção era gravada e nunca lida. A tradução mora aqui, num lugar só,
# porque quem sabe o nome que o gerador usa é este módulo — e uma constante é
# mais fácil de conferir que dois literais em arquivos diferentes.
TAREFA_DO_TIPO = {"curriculo": "bullet_curriculo"}

# Bullet do `como_texto()` do currículo: duas casas de indentação e um hífen.
_BULLET = re.compile(r"^\s{2}-\s+(.+)$", re.MULTILINE)
# Um bullet de currículo tem substância; "  - x" é lixo de formatação.
MINIMO_BULLET = 25


def _texto_do_exemplo(acao: AcaoPendente) -> str:
    """O que vale guardar da ação aprovada.

    Para currículo, **só os bullets**. O texto aprovado é o documento inteiro
    (contato, seções, formação), e o few-shot dele entra no `PROMPT_BULLETS`,
    que pede bullets. Colar 2.000 caracteres de currículo ali gasta metade do
    contexto de 8k e ensina o modelo a repetir a estrutura do documento, em vez
    de a escrever como eu escrevo.
    """
    texto = (acao.texto_final or acao.texto_gerado or "").strip()
    if acao.tipo != "curriculo":
        return texto

    bullets = [b.strip() for b in _BULLET.findall(texto)]
    bullets = [b for b in bullets if len(b) >= MINIMO_BULLET]
    return "\n".join(f"- {b}" for b in bullets)


async def registrar(acao: AcaoPendente) -> ExemploEstilo | None:
    """Ação decidida vira exemplo — se foi aprovada e tem texto.

    Rejeitada nunca entra: ensinar o few-shot com o que eu recusei é o jeito
    mais eficiente de o sistema aprender a escrever mal.
    """
    if acao.status not in ("aprovada", "editada"):
        return None
    texto = _texto_do_exemplo(acao)
    if not texto:
        return None

    async with get_session() as session:
        exemplo = ExemploEstilo(
            tarefa=TAREFA_DO_TIPO.get(acao.tipo, acao.tipo),
            # Sem contexto explícito, o título é a melhor descrição da situação
            # que existe — e é melhor que string vazia no embedding.
            contexto=(acao.contexto or acao.titulo).strip(),
            texto=texto,
            acao_id=acao.id,
        )
        session.add(exemplo)
        await session.commit()
        await session.refresh(exemplo)

    logger.info(f"Exemplo de estilo registrado: {exemplo.tarefa} ({len(texto)} chars)")
    return exemplo


async def embedar_pendentes(*, limite: int = 32) -> int:
    """Preenche os embeddings que faltam. Job do worker, idempotente."""
    async with get_session() as session:
        pendentes = list(
            (
                await session.scalars(
                    select(ExemploEstilo)
                    .where(ExemploEstilo.embedding.is_(None))
                    .order_by(ExemploEstilo.aprovado_em)
                    .limit(limite)
                )
            ).all()
        )
        if not pendentes:
            return 0

        vetores = await gateway.embedar([e.contexto for e in pendentes])
        for exemplo, vetor in zip(pendentes, vetores, strict=True):
            exemplo.embedding = vetor
        await session.commit()

    logger.info(f"{len(pendentes)} exemplo(s) de estilo embedados")
    return len(pendentes)


async def exemplos_para(
    tarefa: str, contexto: str, *, n: int = N_EXEMPLOS
) -> list[ExemploEstilo]:
    """Os `n` exemplos meus mais parecidos com esta situação.

    Cai para "os mais recentes" quando não há embedding — nos primeiros dias
    isso é a regra, não a exceção, e três exemplos quaisquer meus já ensinam
    mais sobre a minha voz do que nenhum.
    """
    contexto = (contexto or "").strip()
    async with get_session() as session:
        vetor = None
        if contexto:
            try:
                (vetor,) = await gateway.embedar([contexto])
            except Exception as e:  # noqa: BLE001 — sem embedder, ainda há fallback
                logger.warning(f"Sem embedding para escolher exemplo ({type(e).__name__}); por data")

        stmt = select(ExemploEstilo).where(ExemploEstilo.tarefa == tarefa)
        if vetor is not None:
            stmt = stmt.where(ExemploEstilo.embedding.is_not(None)).order_by(
                ExemploEstilo.embedding.cosine_distance(vetor)
            )
        else:
            stmt = stmt.order_by(ExemploEstilo.aprovado_em.desc())

        achados = list((await session.scalars(stmt.limit(n))).all())

        # Ainda sem nenhum embedado: completa com os mais recentes, para não
        # devolver lista vazia enquanto o worker não passou.
        if vetor is not None and len(achados) < n:
            faltam = n - len(achados)
            vistos = {e.id for e in achados}
            recentes = (
                await session.scalars(
                    select(ExemploEstilo)
                    .where(ExemploEstilo.tarefa == tarefa)
                    .order_by(ExemploEstilo.aprovado_em.desc())
                    .limit(n)
                )
            ).all()
            achados += [e for e in recentes if e.id not in vistos][:faltam]

    return achados


def bloco_few_shot(exemplos: list[ExemploEstilo]) -> str:
    """Os exemplos formatados para entrar num prompt. Vazio se não houver."""
    if not exemplos:
        return ""
    partes = [
        f"Situação: {e.contexto}\nTexto que eu escrevi:\n{e.texto}" for e in exemplos
    ]
    return (
        "Estes são textos meus, aprovados por mim. Escreva com esta voz — "
        "mesmo ritmo, mesmo tamanho de frase, mesmas escolhas de palavra:\n\n"
        + "\n\n---\n\n".join(partes)
    )
