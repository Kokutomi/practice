"""Interactive practice: python -m pensionlab.lab.cli [load FILE | list | practice | stats]"""
from __future__ import annotations

import json
import sys
import time

from . import db
from .verifiers import compute

ERROR_TYPES = ["", "timing(due/immediate)", "interest/discount", "mortality/survival", "arithmetic", "other"]


def practice(con):
    p = db.next_problem(con)
    if not p:
        print("出題できる問題がありません（`load` で問題を読み込んでください）")
        return
    print(f"\n[{p['id']}] {p['topic']} (難易度 {p['difficulty']})\n{p['statement']}\n")
    t0, level = time.time(), 0
    while True:
        s = input("答え（数値）／ h=ヒント: ").strip()
        if s == "h":
            level += 1
            print("ヒント:", db.get_hint(con, p["id"], level) or "（これ以上ヒントはありません）")
            continue
        try:
            ans = float(s)
            break
        except ValueError:
            print("数値を入力してください")
    conf = int(input("確信度 1(低)-3(高): ") or 2)
    ok = db.record_attempt(con, p["id"], ans, conf, time.time() - t0)
    truth = compute(p["verifier_id"], json.loads(p["params"]))
    print("正解!" if ok else f"不正解。再計算値 = {truth:.4f}")
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
    elif cmd == "stats":
        for r in db.stats_by_topic(con):
            print(f"{r['topic']}: {r['n']}回 正答率{r['pct']}% 正解だが低確信{r['correct_unsure']}")
        print("復習期限:", len(db.due_reviews(con)), "問")
    else:
        practice(con)


if __name__ == "__main__":
    main(sys.argv[1:])
