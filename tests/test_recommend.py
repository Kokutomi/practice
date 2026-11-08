from pathlib import Path

import pytest
from pensionlab.lab import db
from pensionlab.lab.recommend import recommend

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    for y in (2025, 2024):
        db.load_problems(c, str(ROOT / f"problems/iaj-{y}.json"))
    return c


def test_priorities(con):
    DAY = db.DAY
    db.record_attempt(con, "IAJ-2025-1-1", "A", 1, now=0)            # wrong, unsure -> due after 1 day
    db.record_attempt(con, "IAJ-2025-1-3", "A", 3, now=5 * DAY)       # wrong, sure -> misconception (not yet due)
    for pid in ("IAJ-2025-1-5-ア", "IAJ-2025-1-5-イ", "IAJ-2025-1-5-ウ"):   # Trowbridge 0/3 -> weak
        db.record_attempt(con, pid, "Z", 2, now=5 * DAY)
    recs = recommend(con, n=8, now=5 * DAY + 1)
    reasons = [r["reason"] for r in recs]
    ids = [r["problem"]["id"] for r in recs]
    assert ids[0] == "IAJ-2025-1-1" and reasons[0] == "復習期限"
    assert reasons[1].startswith("自信ありで誤答") and ids[1] == "IAJ-2025-1-3"
    assert reasons[2].startswith("弱点分野（財政方式（Trowbridgeモデル）") and ids[2] == "IAJ-2025-1-5-エ"
    assert any(r.startswith("未着手の分野") for r in reasons)
    assert len(set(ids)) == len(ids) == 8


def test_fresh_learner_gets_topic_coverage(con):
    recs = recommend(con, n=5, now=0)
    topics = [r["problem"]["topic"] for r in recs]
    assert len(set(topics)) == 5 and all(r["reason"].startswith("未着手の分野") for r in recs)
