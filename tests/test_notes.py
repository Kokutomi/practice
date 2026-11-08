import io
import zipfile
from pathlib import Path

import pytest
from pensionlab.lab import db, notes

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    db.load_problems(c, str(ROOT / "problems/iaj-2025.json"))
    return c


def test_save_get_delete(con):
    notes.save(con, "IAJ-2025-1-1", "  b_x の形に注意  ", now=1)
    assert notes.get(con, "IAJ-2025-1-1") == "b_x の形に注意"
    notes.save(con, "IAJ-2025-1-1", "   ")
    assert notes.get(con, "IAJ-2025-1-1") == ""


def test_obsidian_vault(con, tmp_path):
    db.record_attempt(con, "IAJ-2025-1-3", "A", 3, now=0)
    db.set_last_error_type(con, "IAJ-2025-1-3", "arithmetic")
    notes.save(con, "IAJ-2025-2-4-ア", "基数を使う解法と直接計算で端数が変わる", now=1)
    files = notes.vault_files(con)
    assert set(files) == {"年金数理/2025/2025 問題1(3).md", "年金数理/2025/2025 問題2(4)(ア).md",
                          "年金数理/分野/生命表・平均余命.md", "年金数理/分野/年金現価・計算基数.md"}
    md = files["年金数理/2025/2025 問題1(3).md"]
    assert "[[生命表・平均余命]]" in md and "2025D.pdf#page=3" in md and "| × | 3 | arithmetic |" in md
    assert "[[2025 問題2(4)(ア)]] | — | ✎" in files["年金数理/分野/年金現価・計算基数.md"]
    z = zipfile.ZipFile(io.BytesIO(notes.export_zip(con)))
    assert len(z.namelist()) == 4
    assert notes.export_dir(con, str(tmp_path)) == 4
