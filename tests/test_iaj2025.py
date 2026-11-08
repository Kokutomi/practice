import json
from pathlib import Path

import pytest
from pensionlab.lab import db

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "problems/iaj-2025.json"


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(DATA))
    return c


def test_structure_and_points():
    items = json.load(open(DATA, encoding="utf-8"))
    assert len(items) == 36 and len({i["id"] for i in items}) == 36
    for sec, total in (("問題1", 40), ("問題2", 30), ("問題3", 30)):
        assert sum(i["points"] for i in items if i["section"] == sec) == total
    for i in items:
        p = i["params"]
        assert all(a in "ABCDEFGHIJKL"[: p["n_choices"]] for a in p["answer"]), i["id"]
        assert i["source_id"] == "IAJ-PAST-2025" and i["exam_body"] == "IAJ"


def test_correction_2025_q2_4a_accepts_f_and_g(con):
    assert db.record_attempt(con, "IAJ-2025-2-4-ア", "F", 3, now=0)
    assert db.record_attempt(con, "IAJ-2025-2-4-ア", "Ｇ", 3, now=0)   # full-width accepted
    assert not db.record_attempt(con, "IAJ-2025-2-4-ア", "(E)", 3, now=0)


def test_links_and_no_recheck_needed(con):
    p = db.get_problem(con, "IAJ-2025-3-3-⑤")
    assert db.source_url(con, p).endswith("2025D.pdf#page=21")
    assert db.source_url(con, p, "answer_page").endswith("#page=38")
    assert db.problems_needing_recheck(con) == []
    assert db.search(con, exam_body="IAJ", topic="開放基金方式・未積立債務")[0]["group_key"] == "1-6-①"
