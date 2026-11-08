import pytest
from pensionlab import LifeTable, gompertz_makeham, annuity_due, annuity_immediate, deferred_annuity_due


@pytest.fixture(scope="module")
def table():
    return LifeTable(gompertz_makeham())


def test_lx_monotone(table):
    assert all(a >= b for a, b in zip(table.lx, table.lx[1:]))
    assert table.l(table.omega + 1) == 0.0


def test_annuity_relation(table):
    assert annuity_due(table, 65, 0.03) == pytest.approx(annuity_immediate(table, 65, 0.03) + 1)


def test_zero_interest_annuity_is_expectancy(table):
    assert annuity_due(table, 65, 0.0) == pytest.approx(1 + table.ex(65))


def test_deferred_recursion(table):
    i = 0.03
    # a_x = a_{x:n} + n|a_x  -> check via defer 0
    assert deferred_annuity_due(table, 65, 0, i) == pytest.approx(annuity_due(table, 65, i))
    assert deferred_annuity_due(table, 40, 25, i) < annuity_due(table, 65, i)
