"""Life annuity present values (annual payments, constant interest)."""
from __future__ import annotations

from .mortality import LifeTable


def annuity_due(table: LifeTable, x: int, i: float) -> float:
    """a-double-dot_x: 1 at start of each year while alive."""
    v = 1.0 / (1.0 + i)
    return sum(v**t * table.tpx(x, t) for t in range(0, table.omega - x + 1))


def annuity_immediate(table: LifeTable, x: int, i: float) -> float:
    """a_x = a-double-dot_x - 1."""
    return annuity_due(table, x, i) - 1.0


def deferred_annuity_due(table: LifeTable, x: int, n: int, i: float) -> float:
    """n| a-double-dot_x: payments start at age x+n."""
    v = 1.0 / (1.0 + i)
    return v**n * table.tpx(x, n) * annuity_due(table, x + n, i)


def pv_pension(table: LifeTable, age: int, retire_age: int, annual_benefit: float, i: float) -> float:
    """PV at `age` of a life pension paid annually in advance from `retire_age`."""
    return annual_benefit * deferred_annuity_due(table, age, retire_age - age, i)
