"""Mark a past-exam source as verified after its problem file was generated and checked.

  python tools/mark_verified.py YEAR "LAST-MODIFIED" "RETRIEVED_AT"
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
year, lm, got = int(sys.argv[1]), sys.argv[2], sys.argv[3]
path = os.path.join(ROOT, "sources", "ledger.json")
L = json.load(open(path, encoding="utf-8"))
items = json.load(open(os.path.join(ROOT, "problems", f"iaj-{year}.json"), encoding="utf-8"))
for e in L:
    if e["id"] == f"IAJ-PAST-{year}":
        e.update(verification="verified", retrieved_at=got, version=f"HTTP Last-Modified: {lm}")
        e["notes"] = (f"正答・配点表を tools/import_iaj.py で抽出し problems/iaj-{year}.json に登録"
                      f"（{len(items)}解答欄、配点合計100点を確認）。")
        break
else:
    raise SystemExit(f"IAJ-PAST-{year} not in ledger")
json.dump(L, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("verified", year)
