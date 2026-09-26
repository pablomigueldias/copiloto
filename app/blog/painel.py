"""Como vai o blog, e o que eu faço agora.

A tela `/posts` respondia "o que estou escrevendo?". Esta camada responde as
duas perguntas que eu fazia ao Claude no terminal:

1. **O que eu faço agora?** — `proximos_passos()`: uma lista curta, em ordem,
   cada item com o post e o botão que resolve. A ordem é a do dinheiro na mesa:
   primeiro o que já está quase no ar (PR verde), por último o que ainda é ideia.
2. **Como vai o blog?** — cadência, meta do M4, cobertura por pilar, calendário
   das próximas terças, o que está parado.

Tudo sai do banco da redação. Nada aqui chama o GitHub ou a API do Gemini: a
tela abre em milissegundos, e o que depende de rede (checks do PR) continua no
editor de cada post.

As regras da Etapa 11 do blog moram aqui como constantes: um post por semana,
na terça; divulgação ativa só com 5 posts no ar; LinkedIn na quarta seguinte.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.blog import camadas as camadas_mod
from app.blog import geracao, servico, taxonomia, vault
from app.db.models.blog import ESTADOS, BlogPost
from app.db.session import get_session

DIA_DE_PUBLICAR = 1  # terça (segunda = 0)
M4_MINIMO = 5
M4_COMPLETO = 10
PARADO_DIAS = 7
SEMANAS_NO_CALENDARIO = 8


@dataclass(slots=True)
class Passo:
    tipo: str  # publicar | pr | linkedin | escrever | gerar | origem | pauta | calendario
    titulo: str
    detalhe: str
    post_id: str | None = None
    acao: str | None = None  # o rótulo do botão


def proxima_terca(hoje: date) -> date:
    return hoje + timedelta(days=(DIA_DE_PUBLICAR - hoje.weekday()) % 7)


def _semana(d: date) -> date:
    """A terça que "é dona" do dia: o post de sexta vale pela terça seguinte."""
    return proxima_terca(d)


def _diag(p: BlogPost) -> tuple[list[str], list[str]]:
    cs = camadas_mod.analisar(
        corpo=p.corpo or "",
        descricao=p.descricao,
        tags=list(p.tags or []),
        origem=list(p.origem or []),
        pilar=p.pilar,
    )
    return camadas_mod.o_que_falta(cs), camadas_mod.faltas(p.corpo or "")


def _por_data(p: BlogPost) -> tuple[int, date]:
    """Com data primeiro (a mais próxima), sem data depois."""
    return (0, p.data_publicacao) if p.data_publicacao else (1, date.max)


def proximos_passos(
    posts: list[BlogPost], *, hoje: date, gerar_ok: bool, candidatas: int
) -> list[Passo]:
    passos: list[Passo] = []
    publicados = [p for p in posts if p.estado == "publicado"]

    # 1. Quase no ar: PR aberto esperando o merge (post novo ou atualização).
    for p in posts:
        if p.estado == "publicado" and p.branch:
            passos.append(
                Passo(
                    "publicar",
                    f"Publicar a atualização de “{p.titulo}”",
                    f"PR #{p.pr_numero} aberto com a correção. Com os checks verdes, "
                    "o merge é um clique.",
                    str(p.id),
                    "abrir e publicar",
                )
            )
        if p.estado == "pronto" and p.pr_numero:
            passos.append(
                Passo(
                    "publicar",
                    f"Publicar “{p.titulo}”",
                    f"PR #{p.pr_numero} aberto. Com os checks verdes, o merge é um clique.",
                    str(p.id),
                    "abrir e publicar",
                )
            )

    # 2. Pronto sem PR.
    for p in posts:
        if p.estado == "pronto" and not p.pr_numero:
            passos.append(
                Passo(
                    "pr",
                    f"Abrir o PR de “{p.titulo}”",
                    "As cinco camadas fecharam. Falta o PR — o CI leva uns 2 minutos.",
                    str(p.id),
                    "abrir o PR",
                )
            )

    # 2b. Post no ar editado aqui e ainda não republicado.
    for p in posts:
        if not p.branch and servico.alteracoes_nao_publicadas(p):
            passos.append(
                Passo(
                    "pr",
                    f"Atualização de “{p.titulo}” guardada, mas não publicada",
                    "O site ainda mostra a versão anterior. Publicar a atualização abre um "
                    "PR com a data de correção.",
                    str(p.id),
                    "abrir o post",
                )
            )

    # 3. LinkedIn: marcado para hoje ou antes, e ainda não postado.
    for p in publicados:
        if (
            p.linkedin_texto
            and not p.linkedin_postado_em
            and p.linkedin_em
            and p.linkedin_em <= hoje
        ):
            passos.append(
                Passo(
                    "linkedin",
                    f"Postar no LinkedIn: “{p.titulo}”",
                    f"Marcado para {p.linkedin_em.strftime('%d/%m')}. O texto está pronto — "
                    "copie, cole e marque como postado.",
                    str(p.id),
                    "copiar o texto",
                )
            )
    if len(publicados) >= M4_MINIMO:
        for p in publicados:
            if not p.linkedin_texto:
                passos.append(
                    Passo(
                        "linkedin",
                        f"Gerar o LinkedIn de “{p.titulo}”",
                        "Post no ar sem divulgação. O texto sai do próprio post, na régua de voz.",
                        str(p.id),
                        "gerar",
                    )
                )

    # 4. Rascunho: o mais perto da data, com o que falta dito por extenso.
    rascunhos = sorted((p for p in posts if p.estado == "rascunho"), key=_por_data)
    for p in rascunhos[:2]:
        falta, marcadores = _diag(p)
        if marcadores:
            detalhe = f"{len(marcadores)} {{{{FALTA}}}} para preencher. O primeiro: {marcadores[0]}"
        elif falta:
            detalhe = f"{len(falta)} sinal(is) vermelho(s). " + "; ".join(falta[:2])
        else:
            detalhe = "As camadas fecharam. Confira o frontmatter e marque pronto."
        quando = f" · sai {p.data_publicacao.strftime('%d/%m')}" if p.data_publicacao else ""
        passos.append(
            Passo("escrever", f"Terminar “{p.titulo}”{quando}", detalhe, str(p.id), "continuar")
        )

    # 5. A próxima pauta da fila.
    pautas = sorted((p for p in posts if p.estado == "pauta"), key=_por_data)
    if pautas and len(rascunhos) < 2:
        p = pautas[0]
        if not p.origem:
            passos.append(
                Passo(
                    "origem",
                    f"Ligar “{p.titulo}” a uma fonte",
                    "Sem origem não há matéria-prima nem prova. Aponte a nota do vault "
                    "ou o doc do Copiloto.",
                    str(p.id),
                    "abrir",
                )
            )
        elif gerar_ok:
            passos.append(
                Passo(
                    "gerar",
                    f"Gerar o rascunho de “{p.titulo}”",
                    "A matéria-prima está ligada. O Gemini escreve, a régua mede, e o que "
                    "faltar vira {{FALTA}}.",
                    str(p.id),
                    "gerar rascunho",
                )
            )
        else:
            passos.append(
                Passo(
                    "escrever",
                    f"Começar “{p.titulo}”",
                    "A pauta tem fonte. Falta a primeira linha.",
                    str(p.id),
                    "abrir",
                )
            )

    # 6. Fila vazia.
    if not pautas and not rascunhos:
        if candidatas:
            passos.append(
                Passo(
                    "pauta",
                    f"Importar uma pauta do vault ({candidatas} nota(s) marcada(s))",
                    "As notas com `blog: ideia` estão na aba do vault, logo abaixo.",
                    None,
                    None,
                )
            )
        else:
            passos.append(
                Passo(
                    "pauta",
                    "A fila está vazia",
                    "Marque uma nota do vault com `blog: ideia` nas propriedades, ou anote "
                    "uma pauta aqui.",
                )
            )

    # 7. A próxima terça sem post.
    terca = proxima_terca(hoje)
    marcados = [
        p
        for p in posts
        if p.estado != "arquivado" and p.data_publicacao and _semana(p.data_publicacao) == terca
    ]
    if not marcados:
        passos.append(
            Passo(
                "calendario",
                f"Nada marcado para terça, {terca.strftime('%d/%m')}",
                "Dê uma data de publicação à pauta que vem a seguir. Semana perdida não acumula.",
            )
        )
    return passos


def _dias(de: datetime | None, hoje: date) -> int | None:
    return None if de is None else (hoje - de.astimezone(UTC).date()).days


async def resumo(*, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    async with get_session() as session:
        posts = list((await session.scalars(select(BlogPost))).all())

    gerar = await geracao.situacao()
    try:
        n_candidatas = sum(1 for c in await vault.candidatas() if not c.post_id)
    except OSError:
        n_candidatas = 0

    publicados = sorted(
        (p for p in posts if p.estado == "publicado" and p.publicado_em),
        key=lambda p: p.publicado_em,
        reverse=True,
    )
    ultimo = publicados[0] if publicados else None
    limite_30 = datetime.now(UTC) - timedelta(days=30)

    pilares = []
    for pilar in taxonomia.PILARES:
        do_pilar = [p for p in publicados if p.pilar == pilar]
        pilares.append(
            {
                "pilar": pilar,
                "publicados": len(do_pilar),
                "na_fila": sum(
                    1
                    for p in posts
                    if p.pilar == pilar and p.estado in ("pauta", "rascunho", "pronto")
                ),
                "dias_sem_post": _dias(do_pilar[0].publicado_em, hoje) if do_pilar else None,
            }
        )

    primeira = proxima_terca(hoje)
    calendario = []
    for i in range(SEMANAS_NO_CALENDARIO):
        terca = primeira + timedelta(weeks=i)
        da_semana = [
            p
            for p in posts
            if p.estado != "arquivado" and p.data_publicacao and _semana(p.data_publicacao) == terca
        ]
        calendario.append(
            {
                "terca": terca,
                "posts": [
                    {
                        "id": str(p.id),
                        "titulo": p.titulo,
                        "estado": p.estado,
                        "data": p.data_publicacao,
                    }
                    for p in da_semana
                ],
            }
        )

    parados = [
        {
            "id": str(p.id),
            "titulo": p.titulo,
            "dias": _dias(p.updated_at, hoje),
        }
        for p in posts
        if p.estado == "rascunho" and (_dias(p.updated_at, hoje) or 0) >= PARADO_DIAS
    ]

    return {
        "hoje": hoje,
        "funil": {e: sum(1 for p in posts if p.estado == e) for e in ESTADOS},
        "m4": {"publicados": len(publicados), "minimo": M4_MINIMO, "completo": M4_COMPLETO},
        "cadencia": {
            "ultimos_30_dias": sum(1 for p in publicados if p.publicado_em >= limite_30),
            "dias_desde_ultimo": _dias(ultimo.publicado_em, hoje) if ultimo else None,
            "ultimo": ultimo.titulo if ultimo else None,
        },
        "pilares": pilares,
        "calendario": calendario,
        "parados": parados,
        "divulgacao_ativa": len(publicados) >= M4_MINIMO,
        "gerar": gerar,
        "candidatas_vault": n_candidatas,
        "proximos": [
            asdict(p)
            for p in proximos_passos(
                posts, hoje=hoje, gerar_ok=gerar["disponivel"], candidatas=n_candidatas
            )
        ],
    }


# Medido no índice do Copiloto (`busca.py`): pergunta com resposta fica entre
# 0,27 e 0,48 de distância; sem resposta, de 0,48 a 0,75. Abaixo do corte, o
# post publicado fala mesmo do assunto da pauta.
CORTE_PARECIDO = 0.48


async def parecidos(post: BlogPost, *, limite: int = 3) -> list[dict]:
    """Posts já publicados perto desta pauta — para não repetir sem saber."""
    from app.conhecimento import busca

    consulta = " ".join(x for x in (post.titulo, post.descricao or "") if x).strip()
    if not consulta:
        return []
    proprio = f"/blog/{post.slug}" if post.slug else None
    vistos: dict[str, dict] = {}
    for t in await busca.buscar(consulta, limite=10, fonte_tipo="blog"):
        if t.distancia is None or t.distancia > CORTE_PARECIDO:
            continue
        if proprio and t.fonte_ref.endswith(proprio):
            continue
        vistos.setdefault(
            t.fonte_ref,
            {
                "titulo": t.titulo or t.fonte_ref,
                "url": t.fonte_ref,
                "trecho": " ".join(t.conteudo.split())[:220],
            },
        )
    return list(vistos.values())[:limite]
