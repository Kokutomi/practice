import json
from pathlib import Path

import pytest
from pensionlab.lab import db, exam

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(ROOT / "problems/iaj-2025.json"))
    return c


def test_exam_session_scores_only_its_answers(con):
    db.record_attempt(con, "IAJ-2025-1-2", "I", 3, now=0)          # earlier practice, not part of the exam
    sid = exam.start(con, 2025, now=1000)
    probs = exam.problems(con, 2025)
    resp = {p["id"]: json.loads(p["params"])["answer"][0] for p in probs if p["section"] == "問題1"}
    resp["IAJ-2025-1-6-③"] = "A"                                      # breaks the 完答 group 1(6)
    del resp["IAJ-2025-1-2"]                                          # unanswered in the exam
    r = exam.submit(con, sid, resp, now=1000 + 60 * 100)
    assert r["total"] == 40 - 5 - 5 and r["max"] == 100
    assert r["by_section"]["問題1"] == [30, 40]
    assert (r["answered"], r["slots"], r["over_time"], r["minutes"]) == (13, 36, False, 100.0)
    h = exam.history(con)[0]
    assert (h["score"], h["answered"], h["over_time"]) == (30, 13, 0)
    with pytest.raises(ValueError):
        exam.submit(con, sid, resp)


def test_over_time_flag_and_remaining(con):
    sid = exam.start(con, 2025, limit_min=180, now=0)
    assert exam.remaining_seconds(con, sid, now=60) == 180 * 60 - 60
    r = exam.submit(con, sid, {}, now=181 * 60)
    assert r["over_time"] and r["total"] == 0
