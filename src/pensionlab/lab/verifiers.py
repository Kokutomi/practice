"""verifier_id -> function(params) -> float. The ground truth is recomputed, never taken from AI."""
from __future__ import annotations

from .. import LifeTable, gompertz_makeham, annuity_due, annuity_immediate, deferred_annuity_due, pv_pension


def _table(p):
    return LifeTable(gompertz_makeham(**p.get("gm", {})))


VERIFIERS = {
    "annuity_due": lambda p: annuity_due(_table(p), p["x"], p["i"]),
    "annuity_immediate": lambda p: annuity_immediate(_table(p), p["x"], p["i"]),
    "deferred_annuity_due": lambda p: deferred_annuity_due(_table(p), p["x"], p["n"], p["i"]),
    "pv_pension": lambda p: pv_pension(_table(p), p["x"], p["retire_age"], p["benefit"], p["i"]),
}


def compute(verifier_id: str, params: dict) -> float:
    return VERIFIERS[verifier_id](params)


def is_correct(verifier_id: str, params: dict, answer: float, rel_tol: float = 0.005) -> bool:
    truth = compute(verifier_id, params)
    return abs(answer - truth) <= rel_tol * abs(truth)
