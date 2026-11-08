import hashlib
import json
import sqlite3
import zipfile

import pytest

from pensionlab.lab import cards, db
from pensionlab.lab.topics import TOPICS

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
PNG = b"\x89PNG\r\n\x1a\nfake"


def make_apkg(path):
    """A minimal legacy-format deck: one formula card with [$]..[/$], one cloze, one picture."""
    db_path = path.parent / "c.anki2"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE col(models TEXT)")
    con.execute("INSERT INTO col VALUES(?)", (json.dumps({"1": {"name": "Basic+actsymb"}, "2": {"name": "穴埋め"}}),))
    con.execute("CREATE TABLE notes(id INTEGER, guid TEXT, mid INTEGER, flds TEXT)")
    notes = [(1, "g-basic", 1, "割引率 [$]d[/$] を v で\x1f[$$]d=1-v[/$$]\x1f3.4"),
             (2, "g-cloze", 2, "標準保険料:{{c1::将来勤務}}期間\x1f"),
             (3, "g-pic", 1, 'ケース図 <img src="case.png">\x1fA\x1f')]
    con.executemany("INSERT INTO notes VALUES(?,?,?,?)", notes)
    con.commit()
    con.close()
    inline = "latex-" + hashlib.sha1(b"$d$").hexdigest() + ".svg"
    display = "latex-" + hashlib.sha1(b"\\begin{displaymath}d=1-v\\end{displaymath}").hexdigest() + ".svg"
    with zipfile.ZipFile(path, "w") as z:
        z.write(db_path, "collection.anki2")
        z.writestr("media", json.dumps({"0": inline, "1": display, "2": "case.png"}))
        z.writestr("0", SVG)
        z.writestr("1", SVG)
        z.writestr("2", PNG)
    return path


def test_convert_embeds_formula_images_and_clozes(tmp_path):
    data = cards.convert(str(make_apkg(tmp_path / "d.apkg")), {"g-basic": "年金現価・計算基数"})
    assert data["missing_media"] == []
    basic, cloze, pic = data["cards"]
    assert basic["num"] == "3.4" and basic["topic"] == "年金現価・計算基数"
    assert basic["front"].count("data:image/svg+xml;base64,") == 1 and "[$]" not in basic["front"]
    assert "data:image/svg+xml;base64," in basic["back"]
    assert cloze["kind"] == "cloze" and "将来勤務" not in cloze["front"] and "将来勤務" in cloze["back"]
    assert "data:image/png;base64," in pic["front"]


def test_mathjax_becomes_dollar_math():
    out = cards.render(r"\(p_x\) と \[q_x=1-p_x\]", {}, [])
    assert "$p_x$" in out and "$$q_x=1-p_x$$" in out


def test_missing_latex_image_falls_back_to_source():
    missing = []
    out = cards.render("[$]x^2[/$]", {}, missing)
    assert "<code>x^2</code>" in out and missing


def test_store_sync_and_lookup(tmp_path):
    con = db.connect(":memory:")
    data = cards.convert(str(make_apkg(tmp_path / "d.apkg")), {})
    p = tmp_path / "cards.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert cards.sync(con, p) == 3
    assert cards.sync(con, p) == 0                                 # unchanged file: nothing reloaded
    assert sum(cards.counts(con).values()) == 3
    assert cards.sync(con, tmp_path / "none.json") == 0
    with pytest.raises(ValueError):
        cards.store(con, {"format": "other"})


def test_upload_apkg(tmp_path):
    con = db.connect(":memory:")
    raw = make_apkg(tmp_path / "d.apkg").read_bytes()
    assert cards.load_upload(con, "年金数理.apkg", raw) == 3


def test_committed_topics_are_canonical():
    t = json.loads(cards.TOPICS.read_text(encoding="utf-8"))
    assert t and set(t.values()) <= set(TOPICS)
