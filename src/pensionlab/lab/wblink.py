"""Workbook problems ↔ past-exam slots ↔ the learner's own ◎/△ marks.

Committed (facts only, no problem text):
  problems/workbook/index.json  one entry per workbook problem: number, PDF pages, section, topic, citation
  problems/workbook/map.json    past-exam slot id -> related workbook problems (strong / related / none)
Private (git-ignored, moved between PC and phone through the learning-record backup):
  data/wb_marks.json            the learner's review marks typed on the workbook pages

The marks were written in 2024 and 2025 and carry no year, so they are read as "how well it went last
year": only the counts of each mark are used, never their order or a "latest" mark.

弱点度 (weakness, 0..1, higher = weaker) of a topic
  workbook mastery m_wb = (◎ + 0.5·○) / (◎ + ○ + △ + ×) over the topic's workbook problems
  app accuracy     m_app = correct / attempts on past-exam slots of the topic
  mastery = (W_APP·k·m_app + W_WB·m_wb) / (W_APP·k + W_WB), k = min(attempts, APP_FULL) / APP_FULL
            (current practice outweighs last year's marks once there are enough attempts;
             a side with no data drops out; no data at all -> None)
  weakness = 1 - mastery
優先度 (priority) = weakness × frequency, where frequency is the topic's share of points in the recent
past exams (problems/iaj-*.json), newer years weighted more (RECENCY per year back).
Self-assigned labels such as 重要 are shown as tags only and do not change any number.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .topics import canonical

ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = ROOT / "problems" / "workbook" / "index.json"
MAP_PATH = ROOT / "problems" / "workbook" / "map.json"
MARKS_PATH = ROOT / "data" / "wb_marks.json"

MARK_VALUE = {"◎": 1.0, "○": 0.5, "△": 0.0, "×": 0.0}
MATCH = ("strong", "related", "none")
W_APP, W_WB, APP_FULL = 2.0, 1.0, 10
RECENCY = 0.85

def ensure_schema(con) -> None:
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='wb_marks'").fetchone():
        from .db import SCHEMA
        con.executescript(SCHEMA)


def _read(path) -> object | None:
    path = Path(path)
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_index(path=INDEX_PATH) -> list[dict]:
    return _read(path) or []


def load_map(path=MAP_PATH) -> dict[str, list[dict]]:
    return _read(path) or {}


def index_by_id(path=INDEX_PATH) -> dict[str, dict]:
    return {e["wb_id"]: e for e in load_index(path)}


# ---- private marks
def sync_marks(con, path=MARKS_PATH) -> int:
    """Load data/wb_marks.json into wb_marks / wb_tags when its contents changed. Returns rows loaded."""
    ensure_schema(con)
    path = Path(path)
    if not path.is_file():
        return 0
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    row = con.execute("SELECT value FROM meta WHERE key='wb_marks_hash'").fetchone()
    if row and row[0] == digest:
        return 0
    data = json.loads(raw.decode("utf-8"))
    n = import_marks(con, data)
    con.execute("INSERT OR REPLACE INTO meta VALUES('wb_marks_hash', ?)", (digest,))
    con.commit()
    return n


def import_marks(con, data: dict) -> int:
    """Replace the marks/tags with the contents of a wb_marks.json document."""
    ensure_schema(con)
    con.execute("DELETE FROM wb_marks")
    con.execute("DELETE FROM wb_tags")
    seqs: dict[str, int] = {}
    for m in data.get("marks", []):
        if m.get("mark") not in MARK_VALUE:
            raise ValueError(f"unknown mark {m.get('mark')!r} on {m.get('wb_id')}")
        s = seqs[m["wb_id"]] = seqs.get(m["wb_id"], 0) + 1
        con.execute("INSERT INTO wb_marks VALUES(?,?,?,?,?,?,?)",
                    (m["wb_id"], s, m.get("page"), m.get("month"), m.get("day"), m["mark"], m.get("status", "ok")))
    for t in data.get("tags", []):
        con.execute("INSERT OR IGNORE INTO wb_tags VALUES(?,?)", (t["wb_id"], t["tag"]))
    con.commit()
    return len(data.get("marks", [])) + len(data.get("tags", []))


def history(con, wb_id: str) -> dict:
    """{"marks": [...], "counts": {mark: n}, "mastery": float|None, "misses": int|None, "tags": [...]}"""
    ensure_schema(con)
    marks = [dict(r) for r in con.execute("SELECT * FROM wb_marks WHERE wb_id=? ORDER BY seq", (wb_id,))]
    tags = [r[0] for r in con.execute("SELECT tag FROM wb_tags WHERE wb_id=? ORDER BY tag", (wb_id,))]
    counts = {k: sum(m["mark"] == k and m["status"] == "ok" for m in marks) for k in MARK_VALUE}
    misses = [int(t[:-1]) for t in tags if t[:-1].isdigit() and t.endswith("X")]
    return {"marks": marks, "counts": counts, "mastery": mastery(counts), "misses": max(misses) if misses else None,
            "tags": [t for t in tags if not (t[:-1].isdigit() and t.endswith("X"))]}


def mastery(counts: dict) -> float | None:
    n = sum(counts.get(k, 0) for k in MARK_VALUE)
    return None if n == 0 else sum(MARK_VALUE[k] * counts.get(k, 0) for k in MARK_VALUE) / n


def history_text(h: dict) -> str:
    if not h["marks"]:
        return "記録なし"
    s = " ".join((f"{m['month']}/{m['day']}" if m["month"] else "日付なし") + m["mark"]
                 + ("(要確認)" if m["status"] != "ok" else "") for m in h["marks"])
    if h["misses"]:
        s += f"（誤答{h['misses']}回）"
    return s


# ---- past exam slot -> workbook problems
def related(slot_id: str, mapping: dict | None = None, index: dict | None = None) -> list[dict]:
    """Workbook problems linked to a past-exam slot, strongest first, with their index entry."""
    mapping = load_map() if mapping is None else mapping
    index = index_by_id() if index is None else index
    out = [dict(r, entry=index[r["wb_id"]]) for r in mapping.get(slot_id, [])
           if r.get("match") != "none" and r.get("wb_id") in index]
    return sorted(out, key=lambda r: MATCH.index(r["match"]))


def slots_for(wb_id: str, mapping: dict | None = None) -> list[tuple[str, str]]:
    mapping = load_map() if mapping is None else mapping
    return [(sid, r["match"]) for sid, rs in mapping.items() for r in rs
            if r.get("wb_id") == wb_id and r.get("match") != "none"]


# ---- topic-level indicators
def frequency(con, latest: int | None = None) -> dict[str, float]:
    """Topic -> share (0..1) of past-exam points, newer years weighted by RECENCY**(years back)."""
    rows = con.execute("SELECT year, topic, points FROM problems WHERE exam_body='IAJ' AND points IS NOT NULL").fetchall()
    if not rows:
        return {}
    latest = latest or max(r["year"] for r in rows)
    w: dict[str, float] = {}
    for r in rows:
        t = canonical(r["topic"] or "")
        w[t] = w.get(t, 0.0) + r["points"] * RECENCY ** (latest - r["year"])
    total = sum(w.values())
    return {t: v / total for t, v in w.items()}


def workbook_mastery_by_topic(con, index: list[dict] | None = None) -> dict[str, dict]:
    ensure_schema(con)
    index = load_index() if index is None else index
    topic_of = {e["wb_id"]: canonical(e["topic"]) for e in index if e.get("topic")}
    agg: dict[str, dict] = {}
    for r in con.execute("SELECT wb_id, mark FROM wb_marks WHERE status='ok'"):
        t = topic_of.get(r["wb_id"])
        if not t:
            continue
        a = agg.setdefault(t, {k: 0 for k in MARK_VALUE})
        a[r["mark"]] += 1
    return {t: {"counts": c, "mastery": mastery(c)} for t, c in agg.items()}


def combine(app_acc: float | None, attempts: int, wb_mastery: float | None) -> float | None:
    """Weakness 0..1 (see module docstring)."""
    k = min(attempts, APP_FULL) / APP_FULL if app_acc is not None else 0.0
    wa, ww = W_APP * k, (W_WB if wb_mastery is not None else 0.0)
    if wa + ww == 0:
        return None
    return 1 - ((wa * (app_acc or 0.0)) + ww * (wb_mastery or 0.0)) / (wa + ww)


def topic_table(con, index: list[dict] | None = None) -> list[dict]:
    """Per topic: app accuracy, workbook marks, weakness, recent-exam frequency, priority. Highest priority first."""
    from .topics import TOPICS
    wb = workbook_mastery_by_topic(con, index)
    freq = frequency(con)
    app: dict[str, list[int]] = {}
    for r in con.execute("SELECT p.topic, a.is_correct FROM attempts a JOIN problems p ON p.id=a.problem_id"):
        s = app.setdefault(canonical(r["topic"] or ""), [0, 0])
        s[0] += r["is_correct"]
        s[1] += 1
    out = []
    for t in TOPICS:
        c, n = app.get(t, [0, 0])
        acc = c / n if n else None
        m = wb.get(t, {}).get("mastery")
        weak = combine(acc, n, m)
        f = freq.get(t, 0.0)
        out.append({"topic": t, "attempts": n, "app_accuracy": acc, "wb_counts": wb.get(t, {}).get("counts"),
                    "wb_mastery": m, "weakness": weak, "frequency": f,
                    "priority": None if weak is None else weak * f})
    return sorted(out, key=lambda r: (r["priority"] is None, -(r["priority"] or 0), -r["frequency"]))


def weak_workbook_problems(con, index: list[dict] | None = None, mapping: dict | None = None, n: int = 20):
    """Workbook problems with △/× left (mastery < 1), ranked by the recent-exam frequency of their topic and
    how many past-exam slots point to them."""
    index = load_index() if index is None else index
    mapping = load_map() if mapping is None else mapping
    freq = frequency(con)
    out = []
    for e in index:
        h = history(con, e["wb_id"])
        if h["mastery"] is None or h["mastery"] >= 1.0:
            continue
        links = slots_for(e["wb_id"], mapping)
        score = (1 - h["mastery"]) * (freq.get(canonical(e.get("topic") or ""), 0.0) + 0.01 * len(links))
        out.append({"entry": e, "history": h, "slots": links, "score": score})
    return sorted(out, key=lambda r: -r["score"])[:n]
