from pathlib import Path

import pytest
from pensionlab.lab import anki, db

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(ROOT / "problems/iaj-2025.json"))
    return c


def test_export_selects_wrong_and_unsure(con, tmp_path):
    db.record_attempt(con, "IAJ-2025-1-1", "C", 3, now=0)      # correct & sure -> excluded
    db.record_attempt(con, "IAJ-2025-1-2", "I", 1, now=0)      # correct but unsure -> included
    db.record_attempt(con, "IAJ-2025-2-4-ア", "A", 2, now=0)   # wrong -> included
    db.set_last_error_type(con, "IAJ-2025-2-4-ア", "arithmetic")
    db.record_attempt(con, "IAJ-2025-1-3", "A", 2, now=0)
    db.record_attempt(con, "IAJ-2025-1-3", "H", 3, now=1)      # fixed later -> excluded
    out = tmp_path / "cards.txt"
    assert anki.export(con, str(out)) == 2
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[:3] == ["#separator:tab", "#html:true", "#tags column:3"]
    cards = [l.split("\t") for l in lines if not l.startswith("#")]
    assert all(len(c) == 3 for c in cards)
    front, back, tags = cards[1]
    assert "問題2(4)(ア)" in front and "2025D.pdf#page=12" in front
    assert "(F) または (G)" in back and "#page=32" in back and "arithmetic" in back
    assert set(tags.split()) >= {"pensionlab", "IAJ2025", "err_arithmetic"}
    assert anki.export(con, str(out), include_unsure=False) == 1
