"""SQLite storage: sources (ledger), problems, hints, attempts, review_queue."""
from __future__ import annotations

import json
import sqlite3
import time

from .verifiers import KEYED, is_correct, normalize

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
CREATE TABLE IF NOT EXISTS exam_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER NOT NULL, exam_body TEXT NOT NULL,
  started_at REAL NOT NULL, submitted_at REAL, limit_min INTEGER NOT NULL,
  score INTEGER, max_score INTEGER, answered INTEGER, over_time INTEGER);
CREATE TABLE IF NOT EXISTS notes(
  problem_id TEXT PRIMARY KEY REFERENCES problems(id), text TEXT NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS wb_marks(          -- learner's ◎/△ marks on workbook pages (data/wb_marks.json)
  wb_id TEXT NOT NULL, seq INTEGER NOT NULL, page INTEGER, month INTEGER, day INTEGER,
  mark TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ok', PRIMARY KEY(wb_id, seq));
CREATE TABLE IF NOT EXISTS wb_tags(           -- learner's labels on workbook problems (1X, 重要, ...)
  wb_id TEXT NOT NULL, tag TEXT NOT NULL, PRIMARY KEY(wb_id, tag));
CREATE TABLE IF NOT EXISTS sources(
  id TEXT PRIMARY KEY, title TEXT NOT NULL, publisher TEXT,
  kind TEXT NOT NULL,          -- past_exam/textbook/exam_info/workbook/reference/course/blog/anki/community
  exam_body TEXT,              -- IAJ (日本アクチュアリー会) / JSCPA (日本年金数理人会) / other
  year INTEGER, url TEXT, retrieved_at TEXT, version TEXT,
  verification TEXT NOT NULL DEFAULT 'unverified',  -- unverified/verified/needs_recheck/superseded
  license TEXT NOT NULL DEFAULT 'unknown',          -- link_only/private_use/permitted/unknown
  access TEXT,                 -- free/free_member/paid
  priority TEXT, notes TEXT);
"""

# columns added after v0.1; applied to existing DBs by connect()
PROBLEM_EXTRA_COLUMNS = {
    "exam_body": "TEXT DEFAULT 'original'",
    "question_no": "TEXT",      # e.g. "問題1(3)"
    "source_id": "TEXT REFERENCES sources(id)",
    "points": "INTEGER",
    "page": "INTEGER",          # page of the problem in the source PDF
    "answer_page": "INTEGER",   # page of the official worked answer
    "group_key": "TEXT",        # items scored together (完答)
    "note": "TEXT",
}
SOURCE_FIELDS = ["id", "title", "publisher", "kind", "exam_body", "year", "url", "retrieved_at",
                 "version", "verification", "license", "access", "priority", "notes"]
VERIFICATION = {"unverified", "verified", "needs_recheck", "superseded"}
LICENSE = {"link_only", "private_use", "permitted", "unknown"}

DAY = 86400.0


def connect(path: str = "data/lab.sqlite") -> sqlite3.Connection:
    if path != ":memory:":
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    have = {r["name"] for r in con.execute("PRAGMA table_info(problems)")}
    for col, decl in PROBLEM_EXTRA_COLUMNS.items():
        if col not in have:
            con.execute(f"ALTER TABLE problems ADD COLUMN {col} {decl}")
    con.commit()
    return con


def load_problems(con, path: str) -> int:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    for p in items:
        con.execute(
            "INSERT OR REPLACE INTO problems(id,year,section,topic,difficulty,statement,verifier_id,params,"
            "source,exam_body,question_no,source_id,points,page,answer_page,group_key,note)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (p["id"], p.get("year"), p.get("section"), p.get("topic"), p.get("difficulty"),
             p["statement"], p["verifier_id"], json.dumps(p["params"], ensure_ascii=False), p.get("source"),
             p.get("exam_body", "original"), p.get("question_no"), p.get("source_id"),
             p.get("points"), p.get("page"), p.get("answer_page"), p.get("group_key"), p.get("note")))
        con.execute("DELETE FROM hints WHERE problem_id=?", (p["id"],))
        for lvl, text in enumerate(p.get("hints", []), 1):
            con.execute("INSERT INTO hints VALUES(?,?,?)", (p["id"], lvl, text))
    con.commit()
    return len(items)


def search(con, year=None, topic=None, difficulty=None, exam_body=None):
    q, a = "SELECT * FROM problems WHERE 1=1", []
    for col, v in (("year", year), ("topic", topic), ("difficulty", difficulty), ("exam_body", exam_body)):
        if v is not None:
            q += f" AND {col}=?"
            a.append(v)
    return con.execute(q + " ORDER BY year, rowid", a).fetchall()


def get_hint(con, problem_id: str, level: int):
    r = con.execute("SELECT text FROM hints WHERE problem_id=? AND level=?", (problem_id, level)).fetchone()
    return r["text"] if r else None


def record_attempt(con, problem_id: str, answer, confidence: int,
                   seconds: float | None = None, error_type: str | None = None, now: float | None = None) -> bool:
    """Judge by recomputation, log the attempt, update the review queue. Returns correctness."""
    now = time.time() if now is None else now
    p = con.execute("SELECT * FROM problems WHERE id=?", (problem_id,)).fetchone()
    params = json.loads(p["params"])
    if p["verifier_id"] in KEYED:
        answer = normalize(p["verifier_id"], answer)
    ok = is_correct(p["verifier_id"], params, answer)
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


STATUSES = {"auto": "おまかせ（復習期限→未解答）", "recommend": "今日のおすすめ", "due": "復習期限", "unattempted": "未解答",
            "wrong": "前回誤答", "unsure": "前回自信なし", "all": "すべて"}


def candidates(con, years=None, topics=None, exam_body=None, status: str = "auto", now: float | None = None,
               exclude=()):
    """Problems matching the filters, in the order they should be offered."""
    from .topics import canonical
    now = time.time() if now is None else now
    q, a = "SELECT * FROM problems WHERE 1=1", []
    if years:
        q += f" AND year IN ({','.join('?' * len(years))})"
        a += list(years)
    if exam_body:
        q += " AND exam_body=?"
        a.append(exam_body)
    # official past exams first (newest year first), self-made samples last
    rows = [r for r in con.execute(q + " ORDER BY exam_body='original', year DESC, rowid", a)
            if (not topics or canonical(r["topic"] or "") in topics) and r["id"] not in exclude]
    last = {r["problem_id"]: r for r in con.execute(
        "SELECT a.* FROM attempts a JOIN (SELECT problem_id, MAX(id) mid FROM attempts GROUP BY problem_id) m"
        " ON a.id=m.mid")}
    due = {r["problem_id"]: r["due_at"] for r in con.execute("SELECT * FROM review_queue WHERE due_at<=?", (now,))}
    pick = {
        "due": lambda r: r["id"] in due,
        "unattempted": lambda r: r["id"] not in last,
        "wrong": lambda r: r["id"] in last and not last[r["id"]]["is_correct"],
        "unsure": lambda r: r["id"] in last and last[r["id"]]["confidence"] <= 1,
        "all": lambda r: True,
    }
    if status == "recommend":
        from .recommend import recommend
        allowed = {r["id"] for r in rows}
        return [r["problem"] for r in recommend(con, n=100, now=now, exam_body=None) if r["problem"]["id"] in allowed]
    if status == "auto":
        d = sorted((r for r in rows if r["id"] in due), key=lambda r: due[r["id"]])
        return d + [r for r in rows if r["id"] not in last]
    out = [r for r in rows if pick[status](r)]
    if status == "due":
        out.sort(key=lambda r: due[r["id"]])
    return out


def next_problem(con, now: float | None = None, exclude=(), **filters):
    """Due reviews first; otherwise an unattempted problem (both within the filters)."""
    c = candidates(con, now=now, exclude=exclude, **filters)
    return c[0] if c else None


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


# ---- source ledger
def load_sources(con, path: str) -> int:
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    for src in items:
        unknown = set(src) - set(SOURCE_FIELDS)
        if unknown:
            raise ValueError(f"{src.get('id')}: unknown fields {sorted(unknown)}")
        row = {k: src.get(k) for k in SOURCE_FIELDS}
        row["verification"] = row["verification"] or "unverified"
        row["license"] = row["license"] or "unknown"
        if row["verification"] not in VERIFICATION or row["license"] not in LICENSE:
            raise ValueError(f"{src['id']}: bad verification/license value")
        con.execute(f"INSERT OR REPLACE INTO sources({','.join(SOURCE_FIELDS)}) "
                    f"VALUES({','.join('?' * len(SOURCE_FIELDS))})", [row[k] for k in SOURCE_FIELDS])
    con.commit()
    return len(items)


def list_sources(con, priority=None, exam_body=None, verification=None):
    q, a = "SELECT * FROM sources WHERE 1=1", []
    for col, v in (("priority", priority), ("exam_body", exam_body), ("verification", verification)):
        if v is not None:
            q += f" AND {col}=?"
            a.append(v)
    return con.execute(q + " ORDER BY priority, exam_body, year DESC, id", a).fetchall()


def problems_needing_recheck(con):
    """Problems whose source was replaced or flagged; their official answers must be re-checked."""
    return con.execute(
        "SELECT p.id, p.year, p.question_no, s.id source_id, s.verification, s.version FROM problems p"
        " JOIN sources s ON s.id=p.source_id WHERE s.verification IN ('needs_recheck','superseded')"
        " ORDER BY p.year, p.id").fetchall()


def source_url(con, problem, page_col: str = "page"):
    """Link to the source PDF, at the problem's page when known."""
    if not problem["source_id"]:
        return None
    r = con.execute("SELECT url FROM sources WHERE id=?", (problem["source_id"],)).fetchone()
    if not r or not r["url"]:
        return None
    page = problem[page_col]
    return f"{r['url']}#page={page}" if page else r["url"]


def sync_data(con, problems_dir: str, ledger: str | None = None) -> int:
    """Reload the ledger and every problems/*.json when their contents changed since the last load.
    Returns the number of problems loaded (0 if already up to date)."""
    import hashlib
    import os
    files = sorted(f for f in os.listdir(problems_dir) if f.endswith(".json")) if os.path.isdir(problems_dir) else []
    h = hashlib.sha256()
    for path in ([ledger] if ledger and os.path.exists(ledger) else []) + [os.path.join(problems_dir, f) for f in files]:
        h.update(path.encode())
        with open(path, "rb") as fh:
            h.update(fh.read())
    digest = h.hexdigest()
    row = con.execute("SELECT value FROM meta WHERE key='data_hash'").fetchone()
    if row and row["value"] == digest:
        return 0
    if ledger and os.path.exists(ledger):
        load_sources(con, ledger)
    n = sum(load_problems(con, os.path.join(problems_dir, f)) for f in files)
    con.execute("INSERT OR REPLACE INTO meta VALUES('data_hash', ?)", (digest,))
    con.commit()
    return n
