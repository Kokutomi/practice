"""Interactive practice: python -m pensionlab.lab.cli
  load FILE | list | practice | stats | score YEAR | sources load FILE | sources list [P0|P1|P2] | sources recheck"""
from __future__ import annotations

import json
import sys
import time

from . import db, scoring
from .verifiers import CHOICE, DIGITS, KEYED, choices, truth_text

ERROR_TYPES = ["", "timing(due/immediate)", "interest/discount", "mortality/survival", "arithmetic", "other"]


def practice(con):
    p = db.next_problem(con)
    if not p:
        print("出題できる問題がありません（`load` で問題を読み込んでください）")
        return
    params = json.loads(p["params"])
    is_choice = p["verifier_id"] in KEYED
    print(f"\n[{p['id']}] {p['question_no'] or ''} {p['topic']}\n{p['statement']}")
    url = db.source_url(con, p)
    if url:
        print("問題文:", url)
    print()
    t0, level = time.time(), 0
    if p["verifier_id"] == DIGITS:
        prompt = "答え（数字）"
    elif is_choice:
        multi = "" if p["verifier_id"] == CHOICE else "・複数可"
        prompt = f"答え（{'/'.join(choices(params))}{multi}）"
    else:
        prompt = "答え（数値）"
    while True:
        s = input(f"{prompt}／ h=ヒント: ").strip()
        if s == "h":
            level += 1
            print("ヒント:", db.get_hint(con, p["id"], level) or "（これ以上ヒントはありません）")
            continue
        if is_choice:
            ans = s
            break
        try:
            ans = float(s)
            break
        except ValueError:
            print("数値を入力してください")
    conf = int(input("確信度 1(低)-3(高): ") or 2)
    ok = db.record_attempt(con, p["id"], ans, conf, time.time() - t0)
    print("正解!" if ok else f"不正解。正答 = {truth_text(p['verifier_id'], params)}")
    a_url = db.source_url(con, p, "answer_page")
    if a_url and p["answer_page"]:
        print("解答例:", a_url)
    if not ok:
        for i, e in enumerate(ERROR_TYPES[1:], 1):
            print(f"  {i}. {e}")
        k = input("誤りタイプ番号（Enterでスキップ）: ").strip()
        if k.isdigit() and 1 <= int(k) <= len(ERROR_TYPES) - 1:
            con.execute("UPDATE attempts SET error_type=? WHERE id=(SELECT MAX(id) FROM attempts)", (ERROR_TYPES[int(k)],))
            con.execute("UPDATE review_queue SET error_type=? WHERE problem_id=?", (ERROR_TYPES[int(k)], p["id"]))
            con.commit()


def main(argv):
    con = db.connect()
    cmd = argv[0] if argv else "practice"
    if cmd == "load":
        print(db.load_problems(con, argv[1]), "問を読み込みました")
    elif cmd == "list":
        for r in db.search(con):
            print(r["id"], r["year"], r["topic"], r["difficulty"])
    elif cmd == "sources":
        sub = argv[1] if len(argv) > 1 else "list"
        if sub == "load":
            print(db.load_sources(con, argv[2]), "件の情報源を台帳に登録しました")
        elif sub == "recheck":
            rows = db.problems_needing_recheck(con)
            for r in rows:
                print(f"{r['id']} {r['year']} {r['question_no'] or ''} <- {r['source_id']} ({r['verification']}, {r['version']})")
            print(f"{len(rows)}問の正答を最新版と照合してください" if rows else "照合が必要な問題はありません")
        else:
            for r in db.list_sources(con, priority=argv[2] if len(argv) > 2 else None):
                url = r["url"] or "URL未記入"
                print(f"[{r['priority']}] {r['id']:<22} {r['verification']:<13} {r['license']:<11} {r['title']}  <{url}>")
    elif cmd == "score":
        r = scoring.year_score(con, int(argv[1]))
        print(f"{argv[1]}年度: {r['total']} / {r['max']} 点（最新の解答で採点、完答は全問正解で得点）")
        for sec, (e, m) in r["by_section"].items():
            print(f"  {sec}: {e} / {m}")
    elif cmd == "stats":
        for r in db.stats_by_topic(con):
            print(f"{r['topic']}: {r['n']}回 正答率{r['pct']}% 正解だが低確信{r['correct_unsure']}")
        print("復習期限:", len(db.due_reviews(con)), "問")
    else:
        practice(con)


if __name__ == "__main__":
    main(sys.argv[1:])
