"""本番モード: one full year under a time limit, scored by 配点 with all-or-nothing groups."""
from __future__ import annotations

import time

from . import db, scoring

DEFAULT_LIMIT_MIN = 180   # 2026年度試験日程の試験時間（年金数理 12/9 10:00〜）


def start(con, year: int, exam_body: str = "IAJ", limit_min: int = DEFAULT_LIMIT_MIN, now: float | None = None) -> int:
    now = time.time() if now is None else now
    cur = con.execute("INSERT INTO exam_sessions(year, exam_body, started_at, limit_min) VALUES(?,?,?,?)",
                      (year, exam_body, now, limit_min))
    con.commit()
    return cur.lastrowid


def problems(con, year: int, exam_body: str = "IAJ"):
    return con.execute("SELECT * FROM problems WHERE year=? AND exam_body=? ORDER BY rowid", (year, exam_body)).fetchall()


def remaining_seconds(con, session_id: int, now: float | None = None) -> float:
    now = time.time() if now is None else now
    s = con.execute("SELECT started_at, limit_min FROM exam_sessions WHERE id=?", (session_id,)).fetchone()
    return s["started_at"] + 60 * s["limit_min"] - now


def submit(con, session_id: int, responses: dict, confidence: dict | None = None, now: float | None = None):
    """responses: problem_id -> answer (blank/None = unanswered). Records an attempt per answered slot
    (feeding the review queue), then scores this session's answers only."""
    now = time.time() if now is None else now
    s = con.execute("SELECT * FROM exam_sessions WHERE id=?", (session_id,)).fetchone()
    if s["submitted_at"] is not None:
        raise ValueError("already submitted")
    probs = problems(con, s["year"], s["exam_body"])
    correct, answered = {}, 0
    for p in probs:
        ans = responses.get(p["id"])
        if ans in (None, ""):
            continue
        answered += 1
        conf = (confidence or {}).get(p["id"], 2)
        correct[p["id"]] = db.record_attempt(con, p["id"], ans, conf, None, now=now)
    result = scoring.score(probs, correct)
    over = now - s["started_at"] > 60 * s["limit_min"]
    con.execute("UPDATE exam_sessions SET submitted_at=?, score=?, max_score=?, answered=?, over_time=? WHERE id=?",
                (now, result["total"], result["max"], answered, int(over), session_id))
    con.commit()
    return {**result, "answered": answered, "slots": len(probs), "over_time": over,
            "minutes": round((now - s["started_at"]) / 60, 1), "correct": correct}


def history(con, exam_body: str = "IAJ"):
    return con.execute("SELECT * FROM exam_sessions WHERE exam_body=? AND submitted_at IS NOT NULL"
                       " ORDER BY submitted_at DESC", (exam_body,)).fetchall()
