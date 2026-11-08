"""Life table and a simple parametric mortality law."""
from __future__ import annotations

import math
from dataclasses import dataclass


def gompertz_makeham(A: float = 0.0007, B: float = 0.00005, c: float = 1.10, max_age: int = 110):
    """Return q_x list (x=0..max_age) from mu_x = A + B*c**x. q_max_age = 1."""
    ln_c = math.log(c)
    qs = []
    for x in range(max_age + 1):
        # integral of mu over [x, x+1]
        h = A + B * c**x * (c - 1) / ln_c
        qs.append(1.0 - math.exp(-h))
    qs[-1] = 1.0
    return qs


@dataclass
class LifeTable:
    qx: list[float]
    radix: float = 100_000.0

    def __post_init__(self):
        lx = [self.radix]
        for q in self.qx[:-1]:
            lx.append(lx[-1] * (1.0 - q))
        self.lx = lx

    @property
    def omega(self) -> int:
        return len(self.qx) - 1

    def l(self, x: int) -> float:
        return self.lx[x] if 0 <= x <= self.omega else 0.0

    def tpx(self, x: int, t: int) -> float:
        """Probability a life aged x survives t years."""
        return self.l(x + t) / self.l(x)

    def ex(self, x: int) -> float:
        """Curtate life expectancy."""
        return sum(self.tpx(x, t) for t in range(1, self.omega - x + 1))
