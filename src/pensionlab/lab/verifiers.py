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


CHOICE = "choice"          # one letter; params = {"answer": ["F", "G"] (alternatives), "n_choices": 10}
CHOICE_SET = "choice_set"  # select all; params = {"answer": ["ABD"], "n_choices": 6}
DIGITS = "digits"          # digit fill-in; params = {"answer": ["050"]}
KEYED = {CHOICE, CHOICE_SET, DIGITS}
LETTERS = "ABCDEFGHIJKLMN"


def normalize_choice(answer) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", str(answer)).strip().strip("()（）").upper()


def normalize_set(answer) -> str:
    import re
    import unicodedata
    return "".join(sorted(set(re.findall(r"[A-Z]", unicodedata.normalize("NFKC", str(answer)).upper()))))


def normalize_digits(answer) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKC", str(answer)) if c.isdigit())


def normalize(verifier_id: str, answer):
    return {CHOICE: normalize_choice, CHOICE_SET: normalize_set, DIGITS: normalize_digits}.get(
        verifier_id, lambda a: a)(answer)


def choices(params: dict) -> list[str]:
    return list(LETTERS[: params.get("n_choices", 10)])


def compute(verifier_id: str, params: dict) -> float:
    return VERIFIERS[verifier_id](params)


def truth_text(verifier_id: str, params: dict) -> str:
    if verifier_id == CHOICE:
        return " または ".join(f"({a})" for a in params["answer"])
    if verifier_id == CHOICE_SET:
        return "".join(f"({a})" for a in params["answer"][0])
    if verifier_id == DIGITS:
        return " または ".join(params["answer"])
    return f"{compute(verifier_id, params):.4f}"


def is_correct(verifier_id: str, params: dict, answer, rel_tol: float = 0.005) -> bool:
    if verifier_id in KEYED:
        return normalize(verifier_id, answer) in params["answer"]
    truth = compute(verifier_id, params)
    return abs(answer - truth) <= rel_tol * abs(truth)
