"""今日のおすすめ: what to solve next, with the reason, from the learner's own history.

Order of priority
  1. 復習期限        review-queue items that are due
  2. 自信ありで誤答  latest attempt wrong at confidence 3 (likely a misconception)
  3. ワークブック△  unattempted slots linked to workbook problems still marked △/× last year,
                     topics that are asked more often in recent exams first
  4. 弱点分野        unattempted problems in topics with accuracy below WEAK_PCT (>= MIN_ATTEMPTS tries)
  5. 未着手分野      one unattempted problem from each topic never tried
  6. 最新年度        remaining unattempted official problems, newest year first

workbook_review() is the other direction: workbook problems to redo for slots answered wrong.
"""
from __future__ import annotations

import time

from .topics import canonical

WEAK_PCT = 70.0
MIN_ATTEMPTS = 3


def recommend(con, n: int = 10, now: float | None = None, exam_body: str | None = "IAJ"):
    now = time.time() if now is None else now
    probs = [r for r in con.execute("SELECT * FROM problems ORDER BY year DESC, rowid")
             if exam_body is None or r["exam_body"] == exam_body]
    by_id = {p["id"]: p for p in probs}
    last = {r["problem_id"]: r for r in con.execute(
        "SELECT a.* FROM attempts a JOIN (SELECT problem_id, MAX(id) mid FROM attempts GROUP BY problem_id) m"
        " ON a.id=m.mid")}
    stats: dict[str, list[int]] = {}
    for r in con.execute("SELECT p.topic, a.is_correct FROM attempts a JOIN problems p ON p.id=a.problem_id"):
        s = stats.setdefault(canonical(r["topic"] or ""), [0, 0])
        s[0] += r["is_correct"]
        s[1] += 1
    out, seen = [], set()

    def add(pid, reason):
        if pid in by_id and pid not in seen and len(out) < n:
            seen.add(pid)
            out.append({"problem": by_id[pid], "reason": reason})

    for r in con.execute("SELECT problem_id, due_at FROM review_queue WHERE due_at<=? ORDER BY due_at", (now,)):
        add(r["problem_id"], "復習期限")
    for pid, a in last.items():
        if not a["is_correct"] and a["confidence"] >= 3:
            add(pid, "自信ありで誤答（誤解の可能性）")
    from . import wblink
    mapping, index = wblink.load_map(), wblink.index_by_id()
    if mapping:
        freq = wblink.frequency(con)
        cands = []
        for sid, rs in mapping.items():
            if sid not in by_id or sid in last:
                continue
            for r in rs:
                if r.get("match") == "none" or r["wb_id"] not in index:
                    continue
                h = wblink.history(con, r["wb_id"])
                if h["mastery"] is not None and h["mastery"] < 1.0:
                    t = canonical(by_id[sid]["topic"] or "")
                    cands.append((-freq.get(t, 0.0), h["mastery"], -by_id[sid]["year"], sid, r["wb_id"], h))
                    break
        # one slot per workbook problem; alternate topics (most frequent topic first)
        by_topic: dict[str, list] = {}
        used_wb: set[str] = set()
        for c in sorted(cands):
            if c[4] in used_wb:
                continue
            used_wb.add(c[4])
            by_topic.setdefault(canonical(by_id[c[3]]["topic"] or ""), []).append(c)
        queues = sorted(by_topic.values(), key=lambda q: q[0][0])
        while any(queues):
            for q in queues:
                if q:
                    _, _, _, sid, wb_id, h = q.pop(0)
                    add(sid, f"ワークブック問題{wb_id}が昨年△（{wblink.history_text(h)}）")
    weak = sorted((t for t, (c, k) in stats.items() if k >= MIN_ATTEMPTS and 100 * c / k < WEAK_PCT),
                  key=lambda t: stats[t][0] / stats[t][1])
    for t in weak:
        pct = round(100 * stats[t][0] / stats[t][1])
        for p in probs:
            if canonical(p["topic"] or "") == t and p["id"] not in last:
                add(p["id"], f"弱点分野（{t} 正答率{pct}%）")
                break
    tried = set(stats)
    for p in probs:
        t = canonical(p["topic"] or "")
        if t not in tried and p["id"] not in last:
            tried.add(t)
            add(p["id"], f"未着手の分野（{t}）")
    for p in probs:
        if p["id"] not in last:
            add(p["id"], f"{p['year']}年度の未解答")
    return out


def workbook_review(con, n: int = 10):
    """Workbook problems to redo: linked to past-exam slots whose latest attempt was wrong."""
    from . import wblink
    mapping, index = wblink.load_map(), wblink.index_by_id()
    last = {r["problem_id"]: r for r in con.execute(
        "SELECT a.* FROM attempts a JOIN (SELECT problem_id, MAX(id) mid FROM attempts GROUP BY problem_id) m"
        " ON a.id=m.mid")}
    out, seen = [], set()
    for sid, a in sorted(last.items(), key=lambda kv: -kv[1]["answered_at"]):
        if a["is_correct"]:
            continue
        for r in wblink.related(sid, mapping, index):
            if r["wb_id"] not in seen and len(out) < n:
                seen.add(r["wb_id"])
                out.append({"entry": r["entry"], "slot": sid, "match": r["match"],
                            "reason": f"{sid} を誤答 → {r['reason']}", "history": wblink.history(con, r["wb_id"])})
    return out
