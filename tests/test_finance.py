import pytest
from pensionlab import LifeTable, gompertz_makeham
from pensionlab.finance import METHODS, Trowbridge


@pytest.fixture(params=[(20, 60, 0.03), (25, 65, 0.015), (30, 60, 0.05)])
def m(request):
    xe, xr, i = request.param
    return Trowbridge(LifeTable(gompertz_makeham()), xe, xr, i)


def test_equilibrium_equation_and_prospective_value(m):
    for k in METHODS:
        C, F = m.contribution(k), m.fund(k)
        assert C + m.d * F == pytest.approx(m.B)
        assert F == pytest.approx(m.liability(k), rel=1e-9), k


def test_entry_age_retrospective_equals_prospective(m):
    assert m.entry_age_retrospective() == pytest.approx(m.liability("entry_age"), rel=1e-9)


def test_textbook_ordering_of_funds_and_contributions(m):
    order = ["paygo", "terminal", "unit", "entry_age", "initial"]
    F = [m.fund(k) for k in order]
    C = [m.contribution(k) for k in order]
    assert F == sorted(F) and len(set(F)) == len(F)
    assert C == sorted(C, reverse=True)


def test_zero_interest_limit_is_rejected_cleanly():
    with pytest.raises(ZeroDivisionError):
        Trowbridge(LifeTable(gompertz_makeham()), 20, 60, 0.0).fund("terminal")
    with pytest.raises(ValueError):
        Trowbridge(LifeTable(gompertz_makeham()), 60, 60, 0.03)
