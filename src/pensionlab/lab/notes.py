"""Personal notes per problem, and export to an Obsidian vault (Markdown with wiki links)."""
from __future__ import annotations

import io
import json
import os
import re
import time
import zipfile
from datetime import datetime

from . import db
from .topics import canonical
from .verifiers import truth_text


def get(con, problem_id: str) -> str:
    r = con.execute("SELECT text FROM notes WHERE problem_id=?", (problem_id,)).fetchone()
    return r["text"] if r else ""


def save(con, problem_id: str, text: str, now: float | None = None) -> None:
    text = text.strip()
    if text:
        con.execute("INSERT OR REPLACE INTO notes VALUES(?,?,?)", (problem_id, text, time.time() if now is None else now))
    else:
        con.execute("DELETE FROM notes WHERE problem_id=?", (problem_id,))
    con.commit()


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "_", name)


def _title(p) -> str:
    return f"{p['year']} {p['question_no']}" if p["question_no"] else p["id"]


def vault_files(con, only_with_activity: bool = True) -> dict[str, str]:
    """{relative path: markdown}. One note per problem (with notes or attempts) + one index per topic."""
    rows = con.execute(
        "SELECT p.* FROM problems p WHERE ? = 0 OR p.id IN (SELECT problem_id FROM notes)"
        " OR p.id IN (SELECT problem_id FROM attempts) ORDER BY p.year DESC, p.rowid",
        (1 if only_with_activity else 0,)).fetchall()
    files, by_topic = {}, {}
    for p in rows:
        topic = canonical(p["topic"] or "未分類")
        title = _title(p)
        atts = con.execute("SELECT answered_at, answer, is_correct, confidence, error_type FROM attempts"
                           " WHERE problem_id=? ORDER BY id", (p["id"],)).fetchall()
        q_url, a_url = db.source_url(con, p), db.source_url(con, p, "answer_page")
        lines = ["---", f"id: {p['id']}", f"year: {p['year']}", f"exam_body: {p['exam_body']}",
                 f"topic: {topic}", "tags: [pensionlab, " + _safe(topic).replace(" ", "_") + "]", "---", "",
                 f"# {title}", "", f"分野: [[{_safe(topic)}]]", "", p["statement"], ""]
        if q_url:
            lines.append(f"- 問題文: [公式PDF p.{p['page']}]({q_url})")
        lines.append(f"- 正答: {truth_text(p['verifier_id'], json.loads(p['params']))}")
        if a_url and p["answer_page"]:
            lines.append(f"- 解答例: [公式PDF p.{p['answer_page']}]({a_url})")
        if p["note"]:
            lines.append(f"- 注: {p['note']}")
        note = get(con, p["id"])
        lines += ["", "## メモ", "", note or "（未記入）", ""]
        if atts:
            lines += ["## 解答履歴", "", "| 日時 | 解答 | 結果 | 確信度 | 誤りの種類 |", "|---|---|---|---|---|"]
            for a in atts:
                when = datetime.fromtimestamp(a["answered_at"]).strftime("%Y-%m-%d %H:%M")
                lines.append(f"| {when} | {a['answer']} | {'○' if a['is_correct'] else '×'} | {a['confidence']} | "
                             f"{a['error_type'] or ''} |")
        fname = f"年金数理/{p['year']}/{_safe(title)}.md"
        files[fname] = "\n".join(lines) + "\n"
        last_ok = atts[-1]["is_correct"] if atts else None
        by_topic.setdefault(topic, []).append((title, last_ok, bool(note)))
    for topic, items in by_topic.items():
        body = [f"# {topic}", "", "| 問題 | 最新 | メモ |", "|---|---|---|"]
        for title, ok, has_note in items:
            mark = "—" if ok is None else ("○" if ok else "×")
            body.append(f"| [[{_safe(title)}]] | {mark} | {'✎' if has_note else ''} |")
        files[f"年金数理/分野/{_safe(topic)}.md"] = "\n".join(body) + "\n"
    return files


def export_zip(con) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, text in vault_files(con).items():
            z.writestr(path, text)
    return buf.getvalue()


def export_dir(con, root: str) -> int:
    files = vault_files(con)
    for path, text in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
    return len(files)
