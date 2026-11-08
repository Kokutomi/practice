from pathlib import Path

import pytest
from pensionlab.lab import db, scoring

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(ROOT / "problems/iaj-2025.json"))
    return c


def answer_all(con, wrong=()):
    for p in db.search(con, year=2025):
        ans = "Z" if p["id"] in wrong else __import__("json").loads(p["params"])["answer"][0]
        db.record_attempt(con, p["id"], ans, 2, now=0)


def test_full_marks(con):
    answer_all(con)
    s = scoring.year_score(con, 2025)
    assert (s["total"], s["max"]) == (100, 100)
    assert s["by_section"] == {"問題1": [40, 40], "問題2": [30, 30], "問題3": [30, 30]}


def test_all_or_nothing_group_loses_whole_unit(con):
    answer_all(con, wrong={"IAJ-2025-1-6-③"})       # 1(6) ①②③ 完答で5点
    s = scoring.year_score(con, 2025)
    assert s["total"] == 95
    unit = next(u for u in s["units"] if u[0] == "2025:1-6-①")
    assert unit[1:3] == (0, 5) and len(unit[3]) == 3


def test_unanswered_scores_zero_and_latest_attempt_counts(con):
    assert scoring.year_score(con, 2025)["total"] == 0
    db.record_attempt(con, "IAJ-2025-1-1", "A", 2, now=0)
    db.record_attempt(con, "IAJ-2025-1-1", "C", 2, now=10)
    assert scoring.year_score(con, 2025)["total"] == 5
    assert scoring.year_score(con, 2025, since=20)["total"] == 0
