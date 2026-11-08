import json
import pytest
from pensionlab.lab import db
from pensionlab.lab.verifiers import compute

SAMPLE = "problems/sample.json"


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_problems(c, SAMPLE)
    return c


def truth(pid, con):
    p = con.execute("SELECT * FROM problems WHERE id=?", (pid,)).fetchone()
    return compute(p["verifier_id"], json.loads(p["params"]))


def test_load_and_search(con):
    assert len(db.search(con)) == 3
    assert [r["id"] for r in db.search(con, topic="deferred_annuity")] == ["S-003"]
    assert db.get_hint(con, "S-001", 2) and db.get_hint(con, "S-001", 3) is None


def test_correct_high_confidence_extends_interval(con):
    assert db.record_attempt(con, "S-001", truth("S-001", con), 3, now=0)
    assert db.record_attempt(con, "S-001", truth("S-001", con), 3, now=0)
    assert con.execute("SELECT interval_days FROM review_queue").fetchone()[0] == 6.0


def test_wrong_answer_due_next_day_and_prioritised(con):
    assert not db.record_attempt(con, "S-002", 1.0, 3, now=0)
    assert db.due_reviews(con, now=0) == []
    assert db.next_problem(con, now=2 * db.DAY)["id"] == "S-002"


def test_unsure_correct_is_flagged(con):
    db.record_attempt(con, "S-001", truth("S-001", con), 1, now=0)
    assert db.stats_by_topic(con)[0]["correct_unsure"] == 1
