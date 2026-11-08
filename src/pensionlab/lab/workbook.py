"""Page index of 『2015年度 年金数理ワークブック』(アクチュアリー受験研究会), handwritten-solution edition.

The PDF itself is NOT in the repository: its cover says it may not be distributed, copied or posted
without the author's permission. Put your own copy at ``data/sources/WBnamachu_.pdf`` (git-ignored)
or point ``LAB_WORKBOOK`` at it. Only this page index — chapter titles and page numbers — is committed.

Layout of the scanned PDF (1218 pages): odd PDF pages are the workbook pages, and the even page right
after each one holds the handwritten solution. All page numbers below are 1-based PDF page indexes
(what a viewer's ``#page=`` uses), checked by eye against every chapter and section heading.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PATH = ROOT / "data" / "sources" / "WBnamachu_.pdf"
TITLE = "2015年度 年金数理ワークブック（手書き解答付き）"
LAST_PAGE = 1218

# key -> (title, first PDF page). Chapters are "N"; sections "N.M".
SECTIONS = {
    "1":    ("第I部 1 動態的昇給率", 1),
    "2":    ("2 定常人口・生命表", 11),
    "3":    ("3 多重脱退", 75),
    "4":    ("4 年金資産・金利計算", 97),
    "5":    ("5 計算基数", 123),
    "6":    ("6 年金現価", 129),
    "6.2":  ("6.2 年金現価 計算問題（確定年金）", 153),
    "6.2.2": ("6.2.2 生命年金", 181),
    "6.2.3": ("6.2.3 死亡した日の属する月までの給付", 235),
    "6.2.4": ("6.2.4 年金額の変更", 247),
    "7":    ("7 連生", 301),
    "8":    ("第II部 8 定常状態と極限方程式", 341),
    "9":    ("9 各種財政方式（正誤・選択）", 389),
    "9.2":  ("9.2 賦課方式", 449),
    "9.3":  ("9.3 退職時年金現価積立方式", 461),
    "9.4":  ("9.4 単位積立方式", 469),
    "9.5":  ("9.5 平準積立方式", 493),
    "9.6":  ("9.6 加入時積立方式", 499),
    "9.7":  ("9.7 財政方式 総合問題", 501),
    "10":   ("第III部 10 責任準備金と未償却債務", 521),
    "11":   ("11 財政方式2（穴埋め・選択・正誤）", 559),
    "11.2": ("11.2 加入年齢方式", 579),
    "11.3": ("11.3 個人平準保険料方式", 629),
    "11.4": ("11.4 総合保険料方式", 635),
    "11.5": ("11.5 到達年齢方式", 653),
    "11.6": ("11.6 開放型総合保険料方式", 661),
    "11.7": ("11.7 開放基金方式", 685),
    "11.8": ("11.8 財政方式2 総合問題", 691),
    "12":   ("第IV部 12 制度変更と過去勤務債務への影響", 723),
    "13":   ("13 年金制度の合併・分割", 813),
    "14":   ("14 被保険者の年齢別責任準備金に関する考察", 837),
    "15":   ("15 ファクラー公式とティーレの公式", 851),
    "16":   ("第V部 16 企業年金制度 正誤問題", 889),
    "17":   ("17 定額制・定年のみの給付の制度", 899),
    "18":   ("18 最終給与比例制・定年のみの給付の制度", 907),
    "19":   ("19 中途脱退給付のある制度（定額制）", 917),
    "20":   ("20 給与累計に基づく給付の制度", 933),
    "21":   ("21 新規加入年齢の保険料率への影響", 935),
    "22":   ("22 予定新規加入員の見込み方", 937),
    "23":   ("23 開放基金方式と過去勤務債務", 965),
    "24":   ("24 特別保険料と償却年数", 967),
    "25":   ("25 企業年金制度 総合問題", 1009),
    "26":   ("第VI部 26 財政決算の考え方", 1049),
    "27":   ("27 財政決算の損益", 1057),
    "28":   ("28 財政再計算", 1145),
}

TOPIC_SECTIONS = {
    "年金現価・計算基数": ["6", "5", "7"],
    "生命表・平均余命": ["2"],
    "定常人口・脱退残存表": ["2", "3"],
    "昇給率・給与指数": ["1", "18"],
    "財政方式（Trowbridgeモデル）": ["9", "8"],
    "加入年齢方式・標準保険料": ["11.2", "11.3", "21"],
    "総合保険料方式": ["11.4", "11.6"],
    "開放基金方式・未積立債務": ["11.7", "23", "10"],
    "特別保険料・未積立債務の償却": ["24", "23"],
    "財政決算・損益（利差等）": ["27", "26"],
    "財政運営・積立金の推移": ["8", "10"],
    "制度変更（統合・分割・給付減額）": ["13", "12", "28"],
}


def path() -> Path:
    return Path(os.environ.get("LAB_WORKBOOK", str(DEFAULT_PATH)))


def available() -> bool:
    return path().is_file()


def span(key: str) -> tuple[int, int]:
    """(first, last) PDF page of a section: up to the page before the next heading in page order."""
    start = SECTIONS[key][1]
    later = sorted(p for _, p in SECTIONS.values() if p > start)
    return start, (later[0] - 1 if later else LAST_PAGE)


def refs(topic: str):
    """[(key, title, first page, last page)] for a canonical topic."""
    from .topics import canonical
    return [(k, SECTIONS[k][0], *span(k)) for k in TOPIC_SECTIONS.get(canonical(topic), [])]


def toc():
    """All sections in page order: [(key, title, first page, last page)]."""
    return [(k, t, *span(k)) for k, (t, _) in sorted(SECTIONS.items(), key=lambda kv: kv[1][1])]


def render(page: int, dpi: int = 110) -> bytes:
    """PNG bytes of one PDF page (pypdfium2 if installed, else poppler's pdftoppm)."""
    if not 1 <= page <= LAST_PAGE:
        raise ValueError(f"page {page} out of range 1..{LAST_PAGE}")
    src = str(path())
    try:
        import io

        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(src)
        try:
            img = doc[page - 1].render(scale=dpi / 72).to_pil()
        finally:
            doc.close()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except ImportError:
        pass
    if not shutil.which("pdftoppm"):
        raise RuntimeError("pypdfium2 か poppler (pdftoppm) が必要です")
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "p"
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(page), "-l", str(page),
                        "-singlefile", src, str(out)], check=True, capture_output=True)
        return (out.with_suffix(".png")).read_bytes()
