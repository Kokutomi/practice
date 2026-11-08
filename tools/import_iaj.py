"""Build problems/iaj-YYYY.json from the official IAJ 年金数理 PDF.

  python tools/import_iaj.py YEAR [--pdf PATH] [--fetch]

The PDF stays outside the repo (default data/sources/YYYYD.pdf). Only facts are written:
answer key, points, all-or-nothing groups, page numbers, choice counts, plus our own topic/summary
annotations from problems/annotations/iaj-YYYY.json. The problem text itself is never copied.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://www.actuaries.jp/lib/collection/books/{y}/{y}D.pdf"
KANA = "アイウエオカキクケコ"
CIRCLED = "".join(chr(c) for c in range(0x2460, 0x2474)) + "".join(chr(c) for c in range(0x3251, 0x325F))
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def ascii_fw(s: str) -> str:
    """Full-width ASCII -> ASCII; keep circled numbers and kana as they are."""
    return "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in s).replace("　", " ")


def math_label(s: str) -> str:
    """pdftotext doubles math-italic glyphs ('𝑎𝑎𝑏𝑏' -> 'ab')."""
    s = unicodedata.normalize("NFKC", s)
    return "".join(s[i] for i in range(0, len(s), 2)) if len(s) % 2 == 0 and all(
        s[i] == s[i + 1] for i in range(0, len(s), 2)) else s


def pdf_pages(pdf: str) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", pdf, "-"], check=True, capture_output=True, text=True).stdout
    return out.split("\f")


FOOTER = re.compile(r"^\s*(\d{4}\s*年度|年金数理[･・.]+\s*\d+)\s*$")


def parse_key(pages: list[str]) -> list[dict]:
    text = "\f".join(pages)
    start = text.rfind("問題番号")
    rows, big, sub, prefix = [], None, None, ""
    for raw in text[start:].splitlines()[1:]:
        line = ascii_fw(raw).replace("\f", "")
        if not line.strip() or FOOTER.match(line):
            continue
        line = re.sub(r"\(\d+点\)", " ", line)            # (40点) under 問題１．
        m = re.search(r"問題(\d+)\.", line)
        if m:
            big, sub, prefix = int(m.group(1)), None, ""
            line = line[m.end():]
        m = re.match(r"\s*\((\d+)\)", line)
        if m:
            sub, prefix = int(m.group(1)), ""
            line = line[m.end():]
        m = re.match(rf"\s*(?:\(([{KANA}])\))?\s*([{CIRCLED}])?", line)
        item = (m.group(1) or "") + (m.group(2) or "")
        if item:
            prefix = item
        line = line[m.end():]
        # blank-letter sub-slots: "① 𝑎𝑎 (A)" then "   𝑏𝑏 (A)" -> ①a, ①b
        lm = re.match(r"\s*([\U0001D400-\U0001D7FF\u210E]+|[a-z])\s+\(", line)
        if lm:
            item = prefix + math_label(lm.group(1))
        pts = re.search(r"(完答で)?\s*(\d+)\s*点", line)
        body = line[: pts.start()] if pts else line
        letters = re.findall(r"\(\s*([A-Z])\s*\)", body)
        digits = None
        if not letters:
            dm = re.search(r"(\S+)?\s+(\d+)\s*$", body.rstrip())
            if dm:
                digits = dm.group(2)
                # a plain-ASCII blank label ("ab 13") names the slot; math-glyph labels are often
                # garbled by pdftotext, so they are not used in ids
                if dm.group(1) and not item and re.fullmatch(r"[a-z]+", dm.group(1)):
                    item = dm.group(1)
        if not letters and digits is None and not pts:
            continue
        rows.append({"big": big, "sub": sub, "item": item, "letters": letters, "alt": "または" in body,
                     "digits": digits, "points": int(pts.group(2)) if pts else None,
                     "all_or_nothing": bool(pts and pts.group(1))})
    return rows


def locate(pages: list[str]):
    """Page (1-based) where each (big, sub) starts, in the problem part and the worked-answer part,
    and the highest choice letter seen inside each (big, sub) problem segment."""
    qpage, apage, maxletter = {}, {}, {}
    answers, big, last_sub = False, None, 0
    for n, pg in enumerate(pages, 1):
        for raw in pg.splitlines():
            line = ascii_fw(raw)
            if "年金数理(解答例)" in line.replace(" ", ""):
                answers, big = True, None
            m = re.search(r"問題(\d+)\.", line)
            if m:
                big, last_sub = int(m.group(1)), 0
                cur = (big, None)
                (apage if answers else qpage).setdefault(cur, n)
            m = re.match(r"\s*\((\d+)\)", line)
            # accept (1), (2), ... only in sequence: a header like "次の(1)、\n(2)は…" must not start (2) early
            if m and big and int(m.group(1)) == last_sub + 1:
                last_sub = int(m.group(1))
                cur = (big, last_sub)
                (apage if answers else qpage).setdefault(cur, n)
            if big and not answers:
                for L in re.findall(r"\(\s*([A-Z])\s*\)", line):
                    k = cur
                    if LETTERS.index(L) > LETTERS.index(maxletter.get(k, "A")):
                        maxletter[k] = L
    return qpage, apage, maxletter


def build(year: int, pdf: str, annotations: dict) -> list[dict]:
    pages = pdf_pages(pdf)
    rows = parse_key(pages)
    qpage, apage, maxletter = locate(pages)
    out, group = [], None
    for r in rows:
        if r["letters"] == [] and r["digits"] is None:
            raise SystemExit(f"{year}: no answer text for 問題{r['big']}({r['sub']}){r['item']} (image-only key?)")
        big, sub, item = r["big"], r["sub"], r["item"]
        key = "-".join(str(x) for x in (big, sub, item) if x not in (None, ""))
        if r["points"] is not None:
            group = key if r["all_or_nothing"] else None
            group_start = True
        else:
            group_start = False
        if r["digits"] is not None:
            vid, params = "digits", {"answer": [r["digits"]]}
        elif len(r["letters"]) > 1 and not r["alt"]:
            vid, params = "choice_set", {"answer": ["".join(sorted(r["letters"]))]}
        else:
            vid, params = "choice", {"answer": r["letters"]}
        if vid != "digits":
            top = maxletter.get((big, sub)) or maxletter.get((big, None)) or "J"
            params["n_choices"] = max(LETTERS.index(top), *(LETTERS.index(a) for a in "".join(params["answer"]))) + 1
        ann = {**annotations.get(f"{big}-{sub}", {}), **annotations.get(key, {})}
        if "n_choices" in ann and vid != "digits":
            params["n_choices"] = ann["n_choices"]
        if "answer" in ann:      # e.g. order-free pairs (順不同) documented in the key
            params["answer"] = ann["answer"]
        qno = f"問題{big}" + (f"({sub})" if sub else "")
        if item:
            qno += (f"({item[0]}){item[1:]}" if item[0] in KANA else item)
        e = {"id": f"IAJ-{year}-{key}", "year": year, "section": f"問題{big}", "topic": ann.get("topic", "未分類"),
             "difficulty": None, "statement": ann.get("summary", f"{qno}（要約未作成）"),
             "verifier_id": vid, "params": params, "source": f"日本アクチュアリー会 {year}年度 年金数理",
             "exam_body": "IAJ", "question_no": qno, "source_id": f"IAJ-PAST-{year}",
             "points": r["points"] if group_start else 0,
             "page": qpage.get((big, sub)) or qpage.get((big, None)),
             "answer_page": apage.get((big, sub)) or apage.get((big, None)),
             "group_key": group if (group and (group_start or r["points"] is None)) else None}
        if r["points"] is not None and not r["all_or_nothing"]:
            group = None
        if ann.get("hints"):
            e["hints"] = ann["hints"]
        notes = [ann["note"]] if ann.get("note") else []
        if e["group_key"]:
            notes.append("完答問題（同じ group_key の小問すべて正解で得点）")
        if notes:
            e["note"] = " ".join(notes)
        out.append(e)
    ids = [e["id"] for e in out]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SystemExit(f"{year}: duplicate slot ids {dup} (unrecognised item labels in the answer key)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("year", type=int)
    ap.add_argument("--pdf")
    ap.add_argument("--fetch", action="store_true", help="download the PDF into data/sources/")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    pdf = a.pdf or os.path.join(ROOT, "data", "sources", f"{a.year}D.pdf")
    if a.fetch:
        os.makedirs(os.path.dirname(pdf), exist_ok=True)
        urllib.request.urlretrieve(URL.format(y=a.year), pdf)
    ann_path = os.path.join(ROOT, "problems", "annotations", f"iaj-{a.year}.json")
    ann = json.load(open(ann_path, encoding="utf-8")) if os.path.exists(ann_path) else {}
    items = build(a.year, pdf, ann)
    out = a.out or os.path.join(ROOT, "problems", f"iaj-{a.year}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    by = {}
    for i in items:
        by[i["section"]] = by.get(i["section"], 0) + i["points"]
    missing = sum(i["topic"] == "未分類" for i in items)
    print(f"{a.year}: {len(items)} items, points {by}, unannotated {missing} -> {out}")


if __name__ == "__main__":
    sys.exit(main())
