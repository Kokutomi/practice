from pathlib import Path

import pytest
from pensionlab.lab import backup, db, exam

ROOT = Path(__file__).resolve().parents[1]


def fresh():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(ROOT / "problems/iaj-2025.json"))
    return c


def test_roundtrip_merge_is_idempotent(tmp_path):
    a = fresh()
    db.record_attempt(a, "IAJ-2025-1-1", "C", 3, now=10)
    db.record_attempt(a, "IAJ-2025-1-2", "A", 1, now=20)
    sid = exam.start(a, 2025, now=30)
    exam.submit(a, sid, {"IAJ-2025-1-3": "H"}, now=40)
    a.execute("INSERT INTO notes VALUES('IAJ-2025-1-2','期初・期末を取り違え',50)"); a.commit()
    path = tmp_path / "b.json"
    counts = backup.save(a, str(path))
    assert counts == {"attempts": 3, "review_queue": 3, "exam_sessions": 1, "notes": 1, "wb_marks": 0, "wb_tags": 0,
                      "card_reviews": 0, "card_state": 0}
    b = fresh()
    assert backup.load(b, str(path)) == counts
    assert backup.load(b, str(path))["attempts"] == 0                  # merging twice adds nothing
    assert b.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 3
    assert b.execute("SELECT text FROM notes").fetchone()[0] == "期初・期末を取り違え"


def test_replace_and_bad_file(tmp_path):
    a = fresh()
    db.record_attempt(a, "IAJ-2025-1-1", "C", 3, now=10)
    data = backup.dump(a)
    b = fresh()
    db.record_attempt(b, "IAJ-2025-1-4", "A", 3, now=10)
    backup.restore(b, data, mode="replace")
    assert [r[0] for r in b.execute("SELECT problem_id FROM attempts")] == ["IAJ-2025-1-1"]
    with pytest.raises(ValueError):
        backup.restore(b, {"format": "x"})


def test_unknown_problems_are_skipped():
    a = fresh()
    db.record_attempt(a, "IAJ-2025-1-1", "C", 3, now=10)
    data = backup.dump(a)
    empty = db.connect(":memory:")
    assert backup.restore(empty, data)["attempts"] == 0


def test_workbook_marks_travel_in_backup():
    from pensionlab.lab import wblink
    a = fresh()
    wblink.import_marks(a, {"marks": [{"wb_id": "1.1", "page": 1, "month": 10, "day": 22, "mark": "◎"},
                                      {"wb_id": "1.1", "page": 1, "month": 11, "day": 3, "mark": "△"}],
                            "tags": [{"wb_id": "1.1", "tag": "2X"}, {"wb_id": "1.1", "tag": "重要"}]})
    data = backup.dump(a)
    b = fresh()
    counts = backup.restore(b, data)
    assert counts["wb_marks"] == 2 and counts["wb_tags"] == 2
    assert backup.restore(b, data)["wb_marks"] == 2                    # same keys: replaced, not duplicated
    assert b.execute("SELECT COUNT(*) FROM wb_marks").fetchone()[0] == 2
    h = wblink.history(b, "1.1")
    assert h["misses"] == 2 and h["tags"] == ["重要"] and h["mastery"] == 0.5
