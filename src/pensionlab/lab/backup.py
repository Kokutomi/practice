"""Back up / restore the learner's own records (problems and sources are reloaded from the repo)."""
from __future__ import annotations

import json
import time

USER_TABLES = ["attempts", "review_queue", "exam_sessions", "notes", "wb_marks", "wb_tags"]
FORMAT = "pensionlab-backup/1"


def dump(con) -> dict:
    out = {"format": FORMAT, "exported_at": time.time(), "tables": {}}
    for t in USER_TABLES:
        out["tables"][t] = [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
    return out


def save(con, path: str) -> dict:
    data = dump(con)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return {t: len(v) for t, v in data["tables"].items()}


def restore(con, data: dict, mode: str = "merge") -> dict:
    """mode='merge': add records not already present (attempts matched by problem/time/answer);
    mode='replace': wipe the learner tables first."""
    if data.get("format") != FORMAT:
        raise ValueError("not a pensionlab backup")
    known = {r["id"] for r in con.execute("SELECT id FROM problems")}
    counts = {}
    if mode == "replace":
        for t in USER_TABLES:
            con.execute(f"DELETE FROM {t}")
    elif mode != "merge":
        raise ValueError(mode)
    for t in USER_TABLES:
        rows = data["tables"].get(t, [])
        cols = [r["name"] for r in con.execute(f"PRAGMA table_info({t})")]
        added = 0
        for r in rows:
            if "problem_id" in r and r["problem_id"] not in known:
                continue          # problem file not loaded here; skip rather than dangle
            if t == "attempts":
                dup = con.execute("SELECT 1 FROM attempts WHERE problem_id=? AND answered_at=? AND answer IS ?",
                                  (r["problem_id"], r["answered_at"], r["answer"])).fetchone()
                if dup:
                    continue
                r = {k: v for k, v in r.items() if k != "id"}      # let ids renumber
            elif t == "exam_sessions":
                dup = con.execute("SELECT 1 FROM exam_sessions WHERE year=? AND started_at=?",
                                  (r["year"], r["started_at"])).fetchone()
                if dup:
                    continue
                r = {k: v for k, v in r.items() if k != "id"}
            keys = [k for k in r if k in cols]
            verb = "INSERT OR REPLACE" if t in ("review_queue", "notes", "wb_marks", "wb_tags") else "INSERT"
            con.execute(f"{verb} INTO {t}({','.join(keys)}) VALUES({','.join('?' * len(keys))})", [r[k] for k in keys])
            added += 1
        counts[t] = added
    con.commit()
    return counts


def load(con, path: str, mode: str = "merge") -> dict:
    with open(path, encoding="utf-8") as f:
        return restore(con, json.load(f), mode)
