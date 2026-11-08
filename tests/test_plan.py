from datetime import date
from pathlib import Path

import pytest
from pensionlab.lab import db, exam, plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.load_sources(c, str(ROOT / "sources/ledger.json"))
    for f in sorted((ROOT / "problems").glob("iaj-*.json")):
        db.load_problems(c, str(f))
    return c


def test_plan_until_exam(con):
    sid = exam.start(con, 2025, now=0)
    exam.submit(con, sid, {}, now=1)                       # 2025 already taken -> not scheduled again
    p = plan.build(con, date(2026, 11, 8))
    assert p[-1]["kind"] == "exam" and p[-1]["date"] == date(2026, 12, 9) and p[-1]["start"] == "10:00"
    assert [e["kind"] for e in p[-3:-1]] == ["review", "review"]
    mocks = [e for e in p if e["kind"] == "mock"]
    # 9 weekend days up to 12/6 (Saturdays first, then Sundays) for the 10 years not yet taken: newest first
    assert [e["title"][5:9] for e in mocks] == ["2024", "2023", "2022", "2021", "2020", "2019", "2018", "2017", "2016"]
    assert all(e["date"].weekday() in (5, 6) and e["date"] <= date(2026, 12, 6) for e in mocks)
    assert all(e["start"] == "10:00" and e["minutes"] == 180 for e in mocks)
    assert len({e["date"] for e in p}) == len(p) == (date(2026, 12, 9) - date(2026, 11, 8)).days + 1
    practice = [e for e in p if e["kind"] == "practice"]
    assert practice and all("欄" in e["title"] or "復習" in e["title"] for e in practice)


def test_ics_is_wellformed(con):
    text = plan.to_ics(plan.build(con, date(2026, 12, 1)))
    lines = text.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR" and text.endswith("END:VCALENDAR\r\n")
    assert text.count("BEGIN:VEVENT") == text.count("END:VEVENT") == 9
    assert "DTSTART;TZID=Asia/Tokyo:20261209T100000" in text and "DTEND;TZID=Asia/Tokyo:20261209T130000" in text
    assert all(len(l.encode()) <= 75 for l in lines)


def test_after_exam_date(con):
    assert [e["kind"] for e in plan.build(con, date(2026, 12, 10))] == ["exam"]


def test_plan_names_formula_cards(con):
    from pensionlab.lab import cards
    cards.store(con, {"format": "pensionlab-anki/1", "cards": [
        {"guid": f"g{i}", "ord": i, "num": f"4.{i}", "topic": "加入年齢方式・標準保険料", "front": "q", "back": "a"}
        for i in range(40)]})
    p = plan.build(con, date(2026, 11, 8))
    notes = [e["detail"] for e in p if e["kind"] == "practice" and "公式カード" in e["detail"]]
    assert notes and "加入年齢方式・標準保険料の新規15枚" in notes[0]
