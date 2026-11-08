"""Commutation functions and annuity-certain values."""
from __future__ import annotations

from .mortality import LifeTable


def table(lt: LifeTable, i: float, ages=None):
    """Rows of x, l_x, d_x, D_x, N_x, C_x, M_x, ä_x (annual, start-of-year annuity; deaths at year end)."""
    v = 1 / (1 + i)
    om = lt.omega
    l = [lt.l(x) for x in range(om + 2)]
    D = [v ** x * l[x] for x in range(om + 2)]
    C = [v ** (x + 1) * (l[x] - l[x + 1]) for x in range(om + 1)] + [0.0]
    N = [sum(D[x:]) for x in range(om + 2)]
    M = [sum(C[x:]) for x in range(om + 2)]
    rows = []
    for x in (ages if ages is not None else range(om + 1)):
        rows.append({"x": x, "l_x": l[x], "d_x": l[x] - l[x + 1], "D_x": D[x], "N_x": N[x], "C_x": C[x],
                     "M_x": M[x], "ä_x": N[x] / D[x] if D[x] else 0.0})
    return rows


def annuity_certain_due(n: int, i: float, m: int = 1) -> float:
    """ä^{(m)}_{n|}: n years of 1 a year paid in m instalments in advance."""
    if i == 0:
        return float(n)
    v = 1 / (1 + i)
    d_m = m * (1 - v ** (1 / m))
    return (1 - v ** n) / d_m


def guaranteed_life_annuity_due(lt: LifeTable, x: int, n: int, i: float) -> float:
    """n-year certain and life annuity-due: ä_{n|} + v^n · n p_x · ä_{x+n}."""
    from .annuities import annuity_due
    v = 1 / (1 + i)
    if x + n > lt.omega:
        return annuity_certain_due(n, i)
    return annuity_certain_due(n, i) + v ** n * lt.tpx(x, n) * annuity_due(lt, x + n, i)
