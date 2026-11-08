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


def test_workbook_marks_drive_recommendations(monkeypatch):
    from pensionlab.lab import db, recommend, wblink
    con = db.connect(":memory:")
    db.load_problems(con, "problems/iaj-2025.json")
    mapping = {"IAJ-2025-1-1": [{"wb_id": "1.2", "match": "strong", "reason": "r"}],
               "IAJ-2025-1-2": [{"wb_id": "1.2", "match": "related", "reason": "r"}],
               "IAJ-2025-1-3": [{"wb_id": "2.12", "match": "strong", "reason": "r"}]}
    index = {"1.2": {"wb_id": "1.2", "topic": "昇給率・給与指数", "page": 3, "solution_pages": [4]},
             "2.12": {"wb_id": "2.12", "topic": "生命表・平均余命", "page": 33, "solution_pages": [34]}}
    monkeypatch.setattr(wblink, "load_map", lambda *a: mapping)
    monkeypatch.setattr(wblink, "index_by_id", lambda *a: index)
    wblink.import_marks(con, {"marks": [{"wb_id": "1.2", "month": 11, "day": 3, "mark": "△"},
                                        {"wb_id": "2.12", "month": 11, "day": 3, "mark": "△"}]})
    recs = [r for r in recommend.recommend(con, n=10) if r["reason"].startswith("ワークブック")]
    assert [r["problem"]["id"] for r in recs] == ["IAJ-2025-1-1", "IAJ-2025-1-3"] or \
           [r["problem"]["id"] for r in recs] == ["IAJ-2025-1-3", "IAJ-2025-1-1"]     # one slot per workbook problem
    db.record_attempt(con, "IAJ-2025-1-1", "A", 3, now=1)        # wrong answer -> redo the workbook problem
    redo = recommend.workbook_review(con)
    assert [r["entry"]["wb_id"] for r in redo] == ["1.2"]
