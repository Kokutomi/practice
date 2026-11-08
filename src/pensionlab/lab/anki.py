"""Export review cards to an Anki-importable TSV (File > Import; header lines set the options).

Selected: slots whose latest attempt was wrong, or correct with confidence 1 (not yet secure).
Front: question number, our summary and a link to the official PDF page (the problem text is not copied).
Back: official answer, link to the worked answer, last error type and notes.
"""
from __future__ import annotations

import html
import json

from . import db
from .topics import canonical
from .verifiers import truth_text


def select(con, include_unsure: bool = True):
    q = ("SELECT p.*, a.is_correct, a.confidence, a.error_type FROM attempts a "
         "JOIN (SELECT problem_id, MAX(id) mid FROM attempts GROUP BY problem_id) m ON a.id=m.mid "
         "JOIN problems p ON p.id=a.problem_id WHERE a.is_correct=0"
         + (" OR (a.is_correct=1 AND a.confidence<=1)" if include_unsure else "") + " ORDER BY p.year DESC, p.rowid")
    return con.execute(q).fetchall()


def _tag(s: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in s).strip("_")


def card(con, p) -> tuple[str, str, str]:
    params = json.loads(p["params"])
    q_url, a_url = db.source_url(con, p), db.source_url(con, p, "answer_page")
    head = f"{p['year']}年度 {p['question_no'] or p['id']}" if p["exam_body"] != "original" else p["id"]
    front = f"<b>{html.escape(head)}</b><br>{html.escape(p['statement'])}"
    if q_url:
        front += f'<br><a href="{html.escape(q_url)}">問題文（公式PDF p.{p["page"]}）</a>'
    back = f"正答: <b>{html.escape(truth_text(p['verifier_id'], params))}</b>"
    if a_url and p["answer_page"]:
        back += f'<br><a href="{html.escape(a_url)}">解答例（公式PDF p.{p["answer_page"]}）</a>'
    status = "誤答" if not p["is_correct"] else "正解だが自信なし"
    back += f"<br>前回: {status}" + (f"（{html.escape(p['error_type'])}）" if p["error_type"] else "")
    if p["note"]:
        back += f"<br><small>{html.escape(p['note'])}</small>"
    tags = ["pensionlab", f"{p['exam_body']}{p['year']}", _tag(canonical(p["topic"] or ""))]
    if p["error_type"]:
        tags.append("err_" + _tag(p["error_type"]))
    return front, back, " ".join(t for t in tags if t)


def export(con, path: str, include_unsure: bool = True) -> int:
    rows = select(con, include_unsure)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("#separator:tab\n#html:true\n#tags column:3\n#deck:年金数理::Learning Lab\n")
        for p in rows:
            f.write("\t".join(x.replace("\t", " ").replace("\n", "<br>") for x in card(con, p)) + "\n")
    return len(rows)
