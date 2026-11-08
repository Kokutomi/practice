"""SQLite storage: problems, hints, attempts, review_queue."""
from __future__ import annotations

import json
import sqlite3
import time

from .verifiers import is_correct

SCHEMA = """
CREATE TABLE IF NOT EXISTS problems(
  id TEXT PRIMARY KEY, year INTEGER, section TEXT, topic TEXT, difficulty INTEGER,
  statement TEXT NOT NULL, verifier_id TEXT NOT NULL, params TEXT NOT NULL, source TEXT);
CREATE TABLE IF NOT EXISTS hints(
  problem_id TEXT NOT NULL REFERENCES problems(id), level INTEGER NOT NULL, text TEXT NOT NULL,
  PRIMARY KEY(problem_id, level));
CREATE TABLE IF NOT EXISTS attempts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, problem_id TEXT NOT NULL REFERENCES problems(id),
  answered_at REAL NOT NULL, answer REAL, is_correct INTEGER NOT NULL,
  confidence INTEGER NOT NULL, seconds REAL, error_type TEXT);
CREATE TABLE IF NOT EXISTS review_queue(
  problem_id TEXT PRIMARY KEY REFERENCES problems(id), topic TEXT, error_type TEXT,
  due_at REAL NOT NULL, interval_days REAL NOT NULL);
"""

DAY = 86400.0


def connect(path: str = "data/lab.sqlite") -> sqlite3.Connection:
    if path != ":memory:":
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def load_problems(con, path: str) -> int:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    for p in items:
        con.execute(
            "INSERT OR REPLACE INTO problems VALUES(?,?,?,?,?,?,?,?,?)",
            (p["id"], p.get("year"), p.get("section"), p.get("topic"), p.get("difficulty"),
             p["statement"], p["verifier_id"], json.dumps(p["params"]), p.get("source")))
        con.execute("DELETE FROM hints WHERE problem_id=?", (p["id"],))
        for lvl, text in enumerate(p.get("hints", []), 1):
            con.execute("INSERT INTO hints VALUES(?,?,?)", (p["id"], lvl, text))
    con.commit()
    return len(items)


def search(con, year=None, topic=None, difficulty=None):
    q, a = "SELECT * FROM problems WHERE 1=1", []
    for col, v in (("year", year), ("topic", topic), ("difficulty", difficulty)):
        if v is not None:
            q += f" AND {col}=?"
            a.append(v)
    return con.execute(q + " ORDER BY year, id", a).fetchall()


def get_hint(con, problem_id: str, level: int):
    r = con.execute("SELECT text FROM hints WHERE problem_id=? AND level=?", (problem_id, level)).fetchone()
    return r["text"] if r else None


def record_attempt(con, problem_id: str, answer: float, confidence: int,
                   seconds: float | None = None, error_type: str | None = None, now: float | None = None) -> bool:
    """Judge by recomputation, log the attempt, update the review queue. Returns correctness."""
    now = time.time() if now is None else now
    p = con.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
    ok = is_correct(p["verifier_id"], json.loads(p["params"]), answer)
    con.execute("INSERT INTO attempts(problem_id,answered_at,answer,is_correct,confidence,seconds,error_type)"
                " VALUES(?,?,?,?,?,?,?)", (problem_id, now, answer, int(ok), confidence, seconds, error_type))
    prev = con.execute("SELECT interval_days FROM review_queue WHERE problem_id=?", (problem_id,)).fetchone()
    if ok and confidence >= 3:
        interval = (prev["interval_days"] * 2) if prev else 3.0
    elif ok:
        interval = 2.0  # correct but unsure
    else:
        interval = 1.0
    con.execute("INSERT OR REPLACE INTO review_queue VALUES(?,?,?,?,?)",
                (problem_id, p["topic"], error_type, now + interval * DAY, interval))
    con.commit()
    return ok


def due_reviews(con, now: float | None = None):
    now = time.time() if now is None else now
    return con.execute("SELECT * FROM review_queue WHERE due_at<=? ORDER BY due_at", (now,)).fetchall()


def next_problem(con, now: float | None = None):
    """Due reviews first; otherwise an unattempted problem."""
    due = due_reviews(con, now)
    if due:
        return con.execute("SELECT * FROM problems WHERE id=?", (due[0]["problem_id"],)).fetchone()
    return con.execute("SELECT * FROM problems WHERE id NOT IN (SELECT problem_id FROM attempts)"
                       " ORDER BY year, id LIMIT 1").fetchone()


def stats_by_topic(con):
    return con.execute(
        "SELECT p.topic, COUNT(*) n, ROUND(100.0*SUM(a.is_correct)/COUNT(*),1) pct,"
        " SUM(a.is_correct=1 AND a.confidence<=2) correct_unsure"
        " FROM attempts a JOIN problems p ON p.id=a.problem_id GROUP BY p.topic").fetchall()


def set_last_error_type(con, problem_id: str, error_type: str) -> None:
    con.execute("UPDATE attempts SET error_type=? WHERE id=(SELECT MAX(id) FROM attempts WHERE problem_id=?)",
                (error_type, problem_id))
    con.execute("UPDATE review_queue SET error_type=? WHERE problem_id=?", (error_type, problem_id))
    con.commit()


def get_problem(con, problem_id: str):
    return con.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
