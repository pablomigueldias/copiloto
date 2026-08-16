"""Junta as fontes e chama o indexador — uma passada por tipo, não por pasta.

O detalhe que faz este módulo existir: `indexar()` apaga do índice o que sumiu
da fonte, e a unidade dessa limpeza é o `fonte_tipo`. Se duas pastas configuradas
compartilham o tipo `repo` e cada uma for indexada por conta própria, a segunda
apaga os chunks da primeira — o índice fica sempre com a última pasta varrida e
o bug só aparece na busca, semanas depois.

Então: **agrupa por tipo, encadeia os documentos das pastas daquele tipo, indexa
uma vez.** E quando a varredura é parcial (`--caminho`), a remoção do que sumiu é
desligada, porque "não vi este arquivo" ali significa "não olhei", não "sumiu".
"""
from __future__ import annotations

from collections.abc import Iterator
from itertools import chain
from pathlib import Path

from app.config import settings
from app.conhecimento.fontes import Documento, ler_markdown
from app.conhecimento.fontes_internas import ler_perfil_mestre, ler_vagas
from app.conhecimento.fontes_pdf import ler_pdf
from app.conhecimento.indexador import Resultado, indexar
from app.utils.logger import get_logger

logger = get_logger()

# Tipos que vêm de arquivo no disco (leitor por tipo) e tipos que vêm do banco.
LEITORES_DE_ARQUIVO = {
    "nota": ler_markdown,
    "repo": ler_markdown,
    "pdf": ler_pdf,
}
LEITORES_DE_BANCO = {
    "perfil": ler_perfil_mestre,
    "vaga": ler_vagas,
}
TIPOS = (*LEITORES_DE_ARQUIVO, *LEITORES_DE_BANCO)


def _documentos_de_arquivo(tipo: str, caminhos: list[str]) -> Iterator[Documento]:
    leitor = LEITORES_DE_ARQUIVO[tipo]
    return chain.from_iterable(
        leitor(Path(c), fonte_tipo=tipo) for c in caminhos  # type: ignore[operator]
    )


def caminhos_configurados(tipo: str) -> list[str]:
    return [c for t, c in settings.conhecimento_fontes_list if t == tipo]


async def ingerir(
    *,
    tipos: list[str] | None = None,
    caminho: str | Path | None = None,
    forcar: bool = False,
) -> dict[str, Resultado]:
    """Varre as fontes pedidas e devolve o resultado por tipo.

    `caminho` substitui o que está no `.env` para os tipos pedidos — é o modo
    "reindexa só esta pasta", e por isso não remove nada do índice.
    """
    pedidos = tipos or list(TIPOS)
    desconhecidos = [t for t in pedidos if t not in TIPOS]
    if desconhecidos:
        raise ValueError(f"Tipo de fonte desconhecido: {', '.join(desconhecidos)}")

    parcial = caminho is not None
    saida: dict[str, Resultado] = {}

    for tipo in pedidos:
        if tipo in LEITORES_DE_BANCO:
            if parcial:
                continue  # `--caminho` não faz sentido para o que vem do banco
            documentos: Iterator[Documento] | list[Documento] = await LEITORES_DE_BANCO[tipo](
                fonte_tipo=tipo
            )
        else:
            caminhos = [str(caminho)] if parcial else caminhos_configurados(tipo)
            if not caminhos:
                continue
            documentos = _documentos_de_arquivo(tipo, caminhos)

        logger.info(f"Indexando fonte '{tipo}'...")
        saida[tipo] = await indexar(
            documentos,
            fonte_tipo=tipo,
            forcar=forcar,
            remover_ausentes=not parcial,
        )
        logger.info(f"'{tipo}': {saida[tipo]}")

    return saida
