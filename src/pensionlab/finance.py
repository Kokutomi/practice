"""Trowbridge model: stationary population, pension of 1 a year from age x_r for life.

Conventions (stated, since exam questions hinge on them):
  * one table l_x for both actives and pensioners (all decrements before x_r are deaths/withdrawals
    without benefit), entry only at age x_e, retirement exactly at x_r;
  * contributions C and benefits B are paid at the start of the year (期初);
  * F is the fund at the start of the year *before* that year's contributions and benefits, so the
    equilibrium equation is (F + C - B)(1 + i) = F, i.e.  C + d F = B  with d = i / (1 + i).
"""
from __future__ import annotations

from dataclasses import dataclass

from .mortality import LifeTable


@dataclass
class Trowbridge:
    table: LifeTable
    x_e: int
    x_r: int
    i: float

    def __post_init__(self):
        if not (0 <= self.x_e < self.x_r <= self.table.omega):
            raise ValueError("need 0 <= x_e < x_r <= omega")
        self.v = 1 / (1 + self.i)
        self.d = self.i / (1 + self.i)
        om = self.table.omega
        self.D = [self.v ** x * self.table.l(x) for x in range(om + 2)]
        self.N = [sum(self.D[x:]) for x in range(om + 2)]

    # --- commutation helpers
    def l(self, x):
        return self.table.l(x)

    def a_due(self, x):
        return self.N[x] / self.D[x]

    @property
    def actives(self):
        return range(self.x_e, self.x_r)

    @property
    def pensioners(self):
        return range(self.x_r, self.table.omega + 1)

    def value_at_retirement(self):
        """ä_{x_r}: PV at x_r of the pension of 1."""
        return self.a_due(self.x_r)

    def benefit_pv_active(self, x):
        """PV at age x of the pension of an active member aged x."""
        return self.D[self.x_r] / self.D[x] * self.value_at_retirement()

    # --- aggregate quantities
    @property
    def B(self):
        return sum(self.l(x) for x in self.pensioners)

    @property
    def L(self):
        return sum(self.l(x) for x in self.actives)

    @property
    def S_p(self):
        return sum(self.l(x) * self.a_due(x) for x in self.pensioners)

    @property
    def S_a(self):
        return sum(self.l(x) * self.benefit_pv_active(x) for x in self.actives)

    def level_premium(self):
        """Entry-age normal (平準積立方式) premium per active, paid x_e .. x_r-1."""
        return self.D[self.x_r] * self.value_at_retirement() / (self.N[self.x_e] - self.N[self.x_r])

    # --- financing methods: annual contribution C
    def contribution(self, method: str) -> float:
        ar, xe, xr = self.value_at_retirement(), self.x_e, self.x_r
        if method == "paygo":          # 賦課方式
            return self.B
        if method == "terminal":       # 退職時年金現価積立方式
            return self.l(xr) * ar
        if method == "initial":        # 加入時積立方式
            return self.l(xe) * self.benefit_pv_active(xe)
        if method == "unit":           # 単位積立方式 (benefit accrues evenly over x_r - x_e years)
            n = xr - xe
            return sum(self.l(x) * self.benefit_pv_active(x) / n for x in self.actives)
        if method == "entry_age":      # 平準積立方式（加入年齢方式・定常）
            return self.level_premium() * self.L
        raise ValueError(method)

    def fund(self, method: str) -> float:
        """Stationary fund from the equilibrium equation C + dF = B."""
        return (self.B - self.contribution(method)) / self.d

    # --- prospective definitions, used to check fund() (and to study the exam statements)
    def liability(self, method: str) -> float:
        ar = self.value_at_retirement()
        if method == "paygo":
            return 0.0
        if method == "terminal":       # pensioners other than those just retiring
            return sum(self.l(x) * self.a_due(x) for x in self.pensioners if x > self.x_r)
        if method == "initial":        # every member already funded, except this year's entrants
            return self.S_p + sum(self.l(x) * self.benefit_pv_active(x) for x in self.actives if x > self.x_e)
        if method == "unit":           # accrued (past-service) benefits
            n = self.x_r - self.x_e
            return self.S_p + sum(self.l(x) * (x - self.x_e) / n * self.benefit_pv_active(x) for x in self.actives)
        if method == "entry_age":      # benefit PV minus PV of future level premiums
            P = self.level_premium()
            return self.S_p + sum(self.l(x) * (self.benefit_pv_active(x) - P * (self.N[x] - self.N[self.x_r]) / self.D[x])
                                  for x in self.actives)
        raise ValueError(method)

    def entry_age_retrospective(self) -> float:
        """Past level premiums accumulated with interest and survivorship, plus pensioners' PV."""
        P = self.level_premium()
        return self.S_p + sum(self.l(x) * P * (self.N[self.x_e] - self.N[x]) / self.D[x] for x in self.actives)


METHODS = {"paygo": "賦課方式", "terminal": "退職時年金現価積立方式", "unit": "単位積立方式",
           "entry_age": "平準積立方式", "initial": "加入時積立方式"}
