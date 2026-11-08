from pathlib import Path

import pytest
from pensionlab.lab import dashboard, db

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(ROOT / "problems/iaj-2025.json"))
    db.load_problems(c, str(ROOT / "problems/sample.json"))
    return c


def test_dashboard_aggregates(con):
    db.record_attempt(con, "IAJ-2025-1-1", "C", 1, now=0)            # correct, unsure
    db.record_attempt(con, "IAJ-2025-1-3", "A", 3, now=0)            # wrong, sure
    db.set_last_error_type(con, "IAJ-2025-1-3", "arithmetic")
    db.record_attempt(con, "S-001", 1.0, 3, now=0)                   # legacy topic -> canonical
    acc = {r["topic"]: r for r in dashboard.topic_accuracy(con)}
    assert acc["昇給率・給与指数"]["accuracy"] == 100.0
    assert acc["生命表・平均余命"]["accuracy"] == 0.0
    assert acc["年金現価・計算基数"]["available"] >= 3 + 3           # 2025 items + samples
    assert dashboard.topic_accuracy(con)[0]["accuracy"] == 0.0       # weakest first
    m = dashboard.confidence_matrix(con)
    assert m[1] == {"correct": 1, "wrong": 0} and m[3] == {"correct": 0, "wrong": 2}
    assert dashboard.error_types(con) == [{"error_type": "arithmetic", "n": 1}]
    ys = dashboard.year_scores(con)
    assert ys == [{"year": 2025, "score": 5, "max": 100, "answered": 2, "slots": 36}]


def test_pace_and_median(con):
    db.record_attempt(con, "IAJ-2025-1-1", "C", 3, seconds=600, now=0)      # 5 points, 10 min -> 2.0 min/pt
    db.record_attempt(con, "IAJ-2025-1-2", "I", 3, seconds=300, now=0)      # 5 points, 5 min -> 1.0
    db.record_attempt(con, "IAJ-2025-1-5-ア", "B", 3, seconds=120, now=0)   # 1 point, 2 min -> 2.0
    p = dashboard.pace(con)
    assert p == {"median_min_per_point": 2.0, "budget_min_per_point": 1.8, "samples": 3}
    acc = {r["topic"]: r for r in dashboard.topic_accuracy(con)}
    assert acc["昇給率・給与指数"]["median_min"] == 10.0
