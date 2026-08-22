"""Quando a questão volta. Uma função pura, e é de propósito.

Todo o agendamento cabe em `proximo_estado`: recebe a agenda de hoje e o que
aconteceu, devolve a agenda de amanhã. Sem banco, sem sessão, sem relógio
implícito — a data de hoje entra por parâmetro. É o que torna o comportamento
testável sem esperar sete dias, e é a única parte do módulo que eu não quero
descobrir quebrada em cima da prova.

As três regras:

1. **Acertou** → intervalo cresce. Sete dias na primeira vez, ×2,2 depois,
   teto de 180. Três acertos seguidos e a questão fica `dominada` — sai da
   pressa, não da fila.
2. **Errou** → volta em dois dias e a sequência **zera**. Não recua um degrau:
   quem errou depois de 35 dias não sabia há 35 dias, sabia há 7.
3. **Adiei** → 30 dias, estado `adiada`, e nenhuma tentativa é registrada.
   Adiar é dizer "está fácil", não "acertei" — contar como acerto inflaria a
   estatística com o que eu não respondi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.db.models.estudo.agenda import (
    ACERTOS_PARA_DOMINAR,
    FATOR,
    INTERVALO_ACERTO,
    INTERVALO_ADIAR,
    INTERVALO_ERRO,
    INTERVALO_MAX,
)


@dataclass(frozen=True, slots=True)
class Estado:
    """O que a agenda guarda, sem o ORM em volta."""

    proxima_em: date
    intervalo_dias: int
    acertos_seguidos: int
    total_acertos: int
    total_erros: int
    estado: str


def inicial(hoje: date) -> Estado:
    """Questão recém-cadastrada entra vencendo hoje — não daqui a uma semana."""
    return Estado(
        proxima_em=hoje,
        intervalo_dias=0,
        acertos_seguidos=0,
        total_acertos=0,
        total_erros=0,
        estado="nova",
    )


def _crescer(intervalo: int) -> int:
    if intervalo <= 0:
        return INTERVALO_ACERTO
    return min(INTERVALO_MAX, round(intervalo * FATOR))


def proximo_estado(atual: Estado, *, acertou: bool, hoje: date) -> Estado:
    intervalo = _crescer(atual.intervalo_dias) if acertou else INTERVALO_ERRO
    seguidos = atual.acertos_seguidos + 1 if acertou else 0

    if not acertou:
        estado = "aprendendo"
    elif seguidos >= ACERTOS_PARA_DOMINAR:
        estado = "dominada"
    else:
        estado = "aprendendo"

    return Estado(
        proxima_em=hoje + timedelta(days=intervalo),
        intervalo_dias=intervalo,
        acertos_seguidos=seguidos,
        total_acertos=atual.total_acertos + (1 if acertou else 0),
        total_erros=atual.total_erros + (0 if acertou else 1),
        estado=estado,
    )


def adiada(atual: Estado, *, hoje: date, dias: int = INTERVALO_ADIAR) -> Estado:
    """Sai da fila por `dias`. Não conta acerto nem erro: eu não respondi."""
    return Estado(
        proxima_em=hoje + timedelta(days=dias),
        intervalo_dias=dias,
        acertos_seguidos=atual.acertos_seguidos,
        total_acertos=atual.total_acertos,
        total_erros=atual.total_erros,
        estado="adiada",
    )
