"""Data for the learning dashboard (kept free of Streamlit so it can be tested)."""
from __future__ import annotations

from . import scoring
from .topics import canonical


def topic_accuracy(con):
    """Per canonical topic: attempts, accuracy %, distinct problems tried / available. Weakest first."""
    rows = con.execute(
        "SELECT p.topic, a.problem_id, a.is_correct FROM attempts a JOIN problems p ON p.id=a.problem_id").fetchall()
    avail = {}
    for r in con.execute("SELECT topic, COUNT(*) n FROM problems GROUP BY topic"):
        t = canonical(r["topic"])
        avail[t] = avail.get(t, 0) + r["n"]
    agg: dict[str, dict] = {}
    for r in rows:
        t = canonical(r["topic"])
        a = agg.setdefault(t, {"topic": t, "attempts": 0, "correct": 0, "tried": set()})
        a["attempts"] += 1
        a["correct"] += r["is_correct"]
        a["tried"].add(r["problem_id"])
    out = [{"topic": t, "attempts": a["attempts"], "accuracy": round(100 * a["correct"] / a["attempts"], 1),
            "tried": len(a["tried"]), "available": avail.get(t, 0)} for t, a in agg.items()]
    return sorted(out, key=lambda r: (r["accuracy"], -r["attempts"]))


def confidence_matrix(con):
    """{confidence: {"correct": n, "wrong": n}} for confidence 1..3."""
    m = {c: {"correct": 0, "wrong": 0} for c in (1, 2, 3)}
    for r in con.execute("SELECT confidence, is_correct, COUNT(*) n FROM attempts GROUP BY confidence, is_correct"):
        if r["confidence"] in m:
            m[r["confidence"]]["correct" if r["is_correct"] else "wrong"] += r["n"]
    return m


def error_types(con):
    return [dict(r) for r in con.execute(
        "SELECT error_type, COUNT(*) n FROM attempts WHERE error_type IS NOT NULL AND is_correct=0"
        " GROUP BY error_type ORDER BY n DESC")]


def year_scores(con, exam_body: str = "IAJ"):
    """Latest-attempt score for every year that has at least one attempt."""
    years = [r["year"] for r in con.execute(
        "SELECT DISTINCT p.year FROM attempts a JOIN problems p ON p.id=a.problem_id"
        " WHERE p.exam_body=? ORDER BY p.year DESC", (exam_body,))]
    res = []
    for y in years:
        s = scoring.year_score(con, y, exam_body)
        answered = con.execute("SELECT COUNT(DISTINCT a.problem_id) FROM attempts a JOIN problems p ON p.id=a.problem_id"
                               " WHERE p.year=? AND p.exam_body=?", (y, exam_body)).fetchone()[0]
        total = con.execute("SELECT COUNT(*) FROM problems WHERE year=? AND exam_body=?", (y, exam_body)).fetchone()[0]
        res.append({"year": y, "score": s["total"], "max": s["max"], "answered": answered, "slots": total})
    return res
