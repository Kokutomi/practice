import glob
import json

import pytest

from pensionlab.lab import db, wblink, workbook
from pensionlab.lab.topics import TOPICS

INDEX = wblink.load_index()
MAP = wblink.load_map()


def slot_ids():
    ids = set()
    for f in glob.glob(str(wblink.ROOT / "problems" / "iaj-*.json")):
        ids |= {p["id"] for p in json.load(open(f, encoding="utf-8"))}
    return ids


# ---- committed data integrity
def test_index_ids_unique_and_ordered():
    ids = [e["wb_id"] for e in INDEX]
    assert len(ids) == len(set(ids))
    pages = [e["page"] for e in INDEX]
    assert pages == sorted(pages)


def test_index_pages_follow_layout():
    # odd page = printed problem, next even page = handwritten solution; a few long problems continue on
    # the even page (then the solution moves to the following odd page) -- all checked by eye
    for i, e in enumerate(INDEX):
        assert e["page"] % 2 == 1 and e["page"] == e["pages"][0], e["wb_id"]
        nxt = INDEX[i + 1]["page"] if i + 1 < len(INDEX) else workbook.LAST_PAGE + 1
        assert sorted(e["pages"] + e["solution_pages"]) == list(range(e["page"], nxt)), e["wb_id"]
        assert e["solution_pages"], e["wb_id"]
    even_continuations = [p for e in INDEX for p in e["pages"] if p % 2 == 0]
    assert len(even_continuations) <= 10


def test_index_section_topic_and_status():
    for e in INDEX:
        assert e["section"] in workbook.SECTIONS, e
        assert e["wb_id"].split(".")[0] == e["section"].split(".")[0], e
        assert e["topic"] in TOPICS, e
        assert e["status"] in ("ok", "needs_review"), e
        if e["status"] == "needs_review":
            assert e.get("note"), e
        assert len(e.get("summary", "")) <= 40, e


PRINTED_GAPS = {"22.6": "22.8"}      # the book itself has no 問題22.7


def test_index_numbers_follow_the_printed_numbering():
    prev = {}
    for e in INDEX:
        ch, n = e["wb_id"].split(".")
        want = PRINTED_GAPS.get(f"{ch}.{prev.get(ch, 0)}", f"{ch}.{prev.get(ch, 0) + 1}")
        assert e["wb_id"] == want, e["wb_id"]
        prev[ch] = int(n)


def test_map_keys_and_targets_exist():
    if not MAP:
        pytest.skip("map not built yet")
    ids, wb_ids = slot_ids(), {e["wb_id"] for e in INDEX}
    assert set(MAP) <= ids
    for sid, rs in MAP.items():
        assert rs, sid
        for r in rs:
            assert r["match"] in wblink.MATCH, (sid, r)
            if r["match"] == "none":
                assert len(rs) == 1, sid
            else:
                assert r["wb_id"] in wb_ids, (sid, r)
                assert r.get("reason"), (sid, r)
        assert len([r for r in rs if r["match"] != "none"]) <= 3, sid


def test_map_covers_every_slot():
    if not MAP:
        pytest.skip("map not built yet")
    assert set(MAP) == slot_ids()


# ---- marks and indicators (synthetic data, no PDF needed)
def fresh():
    con = db.connect(":memory:")
    db.load_problems(con, str(wblink.ROOT / "problems" / "iaj-2025.json"))
    return con


IDX = [{"wb_id": "1.1", "topic": "昇給率・給与指数"}, {"wb_id": "11.12", "topic": "加入年齢方式・標準保険料"}]
MARKS = {"marks": [{"wb_id": "1.1", "month": 10, "day": 22, "mark": "◎"},
                   {"wb_id": "1.1", "month": 11, "day": 3, "mark": "△"},
                   {"wb_id": "11.12", "month": 11, "day": 11, "mark": "○"},
                   {"wb_id": "11.12", "month": 11, "day": 23, "mark": "△"}],
         "tags": [{"wb_id": "11.12", "tag": "3X"}, {"wb_id": "11.12", "tag": "重要"}]}


def test_history_and_mastery():
    con = fresh()
    wblink.import_marks(con, MARKS)
    h = wblink.history(con, "11.12")
    assert h["counts"] == {"◎": 0, "○": 1, "△": 1, "×": 0}
    assert h["mastery"] == 0.25 and h["misses"] == 3 and h["tags"] == ["重要"]
    assert wblink.history_text(h) == "11/11○ 11/23△（誤答3回）"
    assert wblink.history(con, "9.9")["mastery"] is None


def test_unknown_mark_rejected():
    with pytest.raises(ValueError):
        wblink.import_marks(fresh(), {"marks": [{"wb_id": "1.1", "mark": "?"}]})


def test_combine_weakness_definition():
    assert wblink.combine(None, 0, None) is None
    assert wblink.combine(None, 0, 0.25) == 0.75                 # workbook only
    assert wblink.combine(0.5, 10, None) == 0.5                  # app only
    # 10+ attempts: app weight 2, workbook weight 1
    assert wblink.combine(1.0, 10, 0.0) == pytest.approx(1 - 2 / 3)
    # 5 attempts: app weight 1, workbook weight 1
    assert wblink.combine(1.0, 5, 0.0) == pytest.approx(0.5)


def test_frequency_prefers_recent_years():
    con = fresh()
    f = wblink.frequency(con)
    assert sum(f.values()) == pytest.approx(1.0)
    con2 = db.connect(":memory:")
    for y in (2019, 2025):
        db.load_problems(con2, str(wblink.ROOT / "problems" / f"iaj-{y}.json"))
    f2 = wblink.frequency(con2)
    assert f2 and sum(f2.values()) == pytest.approx(1.0)


def test_topic_table_and_weak_problems():
    con = fresh()
    wblink.import_marks(con, MARKS)
    rows = wblink.topic_table(con, IDX)
    by = {r["topic"]: r for r in rows}
    assert by["加入年齢方式・標準保険料"]["weakness"] == pytest.approx(0.75)
    assert by["昇給率・給与指数"]["weakness"] == pytest.approx(0.5)
    assert rows[0]["priority"] is not None
    weak = wblink.weak_workbook_problems(con, IDX, {"IAJ-2025-1-1": [{"wb_id": "1.1", "match": "strong",
                                                                      "reason": "x"}]})
    scores = [w["score"] for w in weak]
    assert scores == sorted(scores, reverse=True)
    assert {w["entry"]["wb_id"] for w in weak} == {"1.1", "11.12"}


def test_sync_marks_detects_changes(tmp_path):
    con = fresh()
    p = tmp_path / "wb_marks.json"
    assert wblink.sync_marks(con, p) == 0
    p.write_text(json.dumps(MARKS, ensure_ascii=False), encoding="utf-8")
    assert wblink.sync_marks(con, p) == 6
    assert wblink.sync_marks(con, p) == 0
    MARKS2 = {"marks": MARKS["marks"][:1], "tags": []}
    p.write_text(json.dumps(MARKS2, ensure_ascii=False), encoding="utf-8")
    assert wblink.sync_marks(con, p) == 1
    assert con.execute("SELECT COUNT(*) FROM wb_marks").fetchone()[0] == 1


def test_related_orders_by_strength():
    idx = {"1.1": {"wb_id": "1.1"}, "1.2": {"wb_id": "1.2"}}
    m = {"S": [{"wb_id": "1.2", "match": "related", "reason": "r"}, {"wb_id": "1.1", "match": "strong", "reason": "s"}]}
    assert [r["wb_id"] for r in wblink.related("S", m, idx)] == ["1.1", "1.2"]
    assert wblink.related("missing", m, idx) == []
    assert wblink.slots_for("1.2", m) == [("S", "related")]
