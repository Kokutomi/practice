import json
import sqlite3
from pathlib import Path

import pytest
from pensionlab.lab import db

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources/ledger.json"


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(LEDGER))
    return c


def test_ledger_loads_and_filters(con):
    assert len(db.list_sources(con)) == len(json.load(open(LEDGER, encoding="utf-8")))
    assert all(r["priority"] == "P0" for r in db.list_sources(con, priority="P0"))
    assert {r["exam_body"] for r in db.list_sources(con, exam_body="JSCPA")} == {"JSCPA"}


def test_ledger_ids_unique():
    ids = [s["id"] for s in json.load(open(LEDGER, encoding="utf-8"))]
    assert len(ids) == len(set(ids))


def test_bad_values_rejected(tmp_path, con):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"id": "X", "title": "t", "kind": "blog", "license": "free_for_all"}]))
    with pytest.raises(ValueError):
        db.load_sources(con, str(bad))
    bad.write_text(json.dumps([{"id": "X", "title": "t", "kind": "blog", "urll": "typo"}]))
    with pytest.raises(ValueError):
        db.load_sources(con, str(bad))


def test_recheck_links_problem_to_superseded_source(tmp_path, con):
    probs = tmp_path / "p.json"
    probs.write_text(json.dumps([{
        "id": "IAJ-2025-Q1", "year": 2025, "topic": "life_annuity", "difficulty": 1, "statement": "s",
        "verifier_id": "annuity_due", "params": {"x": 65, "i": 0.03},
        "exam_body": "IAJ", "question_no": "問題1(1)", "source_id": "IAJ-PAST-2025"}]))
    db.load_problems(con, str(probs))
    rows = db.problems_needing_recheck(con)
    assert [(r["id"], r["source_id"]) for r in rows] == [("IAJ-2025-Q1", "IAJ-PAST-2025")]
    assert db.search(con, exam_body="IAJ")[0]["question_no"] == "問題1(1)"


def test_existing_db_is_migrated(tmp_path):
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE problems(id TEXT PRIMARY KEY, year INTEGER, section TEXT, topic TEXT,"
                " difficulty INTEGER, statement TEXT NOT NULL, verifier_id TEXT NOT NULL, params TEXT NOT NULL, source TEXT)")
    old.execute("INSERT INTO problems VALUES('A',2026,'s','t',1,'x','annuity_due','{}','original')")
    old.commit(); old.close()
    c = db.connect(str(path))
    r = db.get_problem(c, "A")
    assert r["exam_body"] == "original" and r["source_id"] is None
