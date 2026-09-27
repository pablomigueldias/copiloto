"""Dia útil, para a cadência: o lembrete sai 5 dias úteis depois do e-mail 1.

Dia útil é segunda a sexta, fora os feriados nacionais e os de São Paulo
(estado e capital), que é onde estão as clínicas da base. Carnaval entra: não é
feriado nacional, mas é ponto facultativo e ninguém lê e-mail comercial nele.
Os móveis saem da Páscoa; o resto é data fixa.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import cache

_FIXOS = (
    (1, 1),    # Confraternização Universal
    (1, 25),   # aniversário de São Paulo (capital)
    (4, 21),   # Tiradentes
    (5, 1),    # Dia do Trabalho
    (7, 9),    # Revolução Constitucionalista (estado)
    (9, 7),    # Independência
    (10, 12),  # Nossa Senhora Aparecida
    (11, 2),   # Finados
    (11, 15),  # Proclamação da República
    (11, 20),  # Consciência Negra (nacional desde 2024)
    (12, 25),  # Natal
)


def pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    mes, dia = divmod(h + ll - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


@cache
def feriados(ano: int) -> frozenset[date]:
    p = pascoa(ano)
    moveis = (
        p - timedelta(days=48),  # segunda de Carnaval
        p - timedelta(days=47),  # terça de Carnaval
        p - timedelta(days=2),   # Sexta-feira Santa
        p + timedelta(days=60),  # Corpus Christi
    )
    return frozenset({date(ano, m, d) for m, d in _FIXOS} | set(moveis))


def dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in feriados(d.year)


def somar_dias_uteis(d: date, n: int) -> date:
    """O n-ésimo dia útil depois de `d` (sem contar `d`)."""
    while n > 0:
        d += timedelta(days=1)
        if dia_util(d):
            n -= 1
    return d
