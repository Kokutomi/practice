"""Exam-style scoring: points are earned per scoring unit; an all-or-nothing group (完答)
scores only when every slot in it is correct."""
from __future__ import annotations

from collections import OrderedDict


def units(problems):
    """Group problem rows into scoring units, preserving order. Returns {unit_key: [rows]}."""
    out: OrderedDict[str, list] = OrderedDict()
    for p in problems:
        key = f"{p['year']}:{p['group_key']}" if p["group_key"] else p["id"]
        out.setdefault(key, []).append(p)
    return out


def score(problems, correct: dict[str, bool]):
    """correct: problem_id -> bool (missing = unanswered = wrong).
    Returns dict(total, max, by_section, units=[(key, earned, max, ids)])."""
    total = mx = 0
    by_section: dict[str, list[int]] = {}
    detail = []
    for key, rows in units(problems).items():
        pts = sum(r["points"] or 0 for r in rows)
        ok = all(correct.get(r["id"], False) for r in rows)
        earned = pts if ok else 0
        total += earned
        mx += pts
        sec = by_section.setdefault(rows[0]["section"] or "", [0, 0])
        sec[0] += earned
        sec[1] += pts
        detail.append((key, earned, pts, [r["id"] for r in rows]))
    return {"total": total, "max": mx, "by_section": by_section, "units": detail}


def latest_correctness(con, problem_ids=None, since: float | None = None) -> dict[str, bool]:
    """Most recent attempt per problem (optionally only attempts at/after `since`)."""
    q = ("SELECT a.problem_id, a.is_correct FROM attempts a JOIN (SELECT problem_id, MAX(id) mid FROM attempts"
         + (" WHERE answered_at>=?" if since is not None else "") + " GROUP BY problem_id) m ON a.id=m.mid")
    rows = con.execute(q, (since,) if since is not None else ()).fetchall()
    res = {r["problem_id"]: bool(r["is_correct"]) for r in rows}
    if problem_ids is not None:
        res = {k: v for k, v in res.items() if k in set(problem_ids)}
    return res


def year_score(con, year: int, exam_body: str = "IAJ", since: float | None = None):
    probs = con.execute("SELECT * FROM problems WHERE year=? AND exam_body=? ORDER BY rowid", (year, exam_body)).fetchall()
    return score(probs, latest_correctness(con, [p["id"] for p in probs], since))
