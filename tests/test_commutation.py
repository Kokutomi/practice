import pytest
from pensionlab import LifeTable, annuity_due, gompertz_makeham
from pensionlab.commutation import annuity_certain_due, guaranteed_life_annuity_due, table

LT = LifeTable(gompertz_makeham())


def test_commutation_identities():
    i = 0.03
    d = i / (1 + i)
    rows = {r["x"]: r for r in table(LT, i)}
    for x in (20, 40, 65, 90):
        r = rows[x]
        assert r["ä_x"] == pytest.approx(annuity_due(LT, x, i))
        assert r["M_x"] == pytest.approx(r["D_x"] - d * r["N_x"])        # M_x = D_x - d N_x
    assert table(LT, i, ages=[60])[0]["x"] == 60


def test_annuity_certain():
    assert annuity_certain_due(10, 0.0) == 10
    assert annuity_certain_due(1, 0.05) == pytest.approx(1.0)
    v = 1 / 1.02
    assert annuity_certain_due(10, 0.02) == pytest.approx(sum(v ** k for k in range(10)))
    # monthly in advance: 12 payments of 1/12 per year
    assert annuity_certain_due(5, 0.025, 12) == pytest.approx(sum(v ** 0 * (1 / 1.025) ** (k / 12) / 12 for k in range(60)))


def test_guaranteed_annuity_bounds():
    g = guaranteed_life_annuity_due(LT, 60, 10, 0.03)
    assert g > annuity_due(LT, 60, 0.03) and g > annuity_certain_due(10, 0.03)
    assert guaranteed_life_annuity_due(LT, 60, 0, 0.03) == pytest.approx(annuity_due(LT, 60, 0.03))


@pytest.mark.parametrize("n,i,m,scale,official", [
    (10, 0.020, 1, 1, 9.16), (10, 0.025, 1, 1, 8.97),                         # 2025年度 問題2(4) 諸数値
    (5, 0.025, 12, 12, 56.50204), (10, 0.025, 12, 12, 106.44161),               # 2025年度 問題3(1) 諸数値
    (5, 0.020, 12, 12, 57.17241), (10, 0.020, 12, 12, 108.95522),               # （年金月額1、年12回期初払い）
])
def test_matches_figures_printed_in_the_2025_exam(n, i, m, scale, official):
    digits = len(str(official).split(".")[1])
    assert round(scale * annuity_certain_due(n, i, m), digits) == official
