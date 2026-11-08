"""Split a large PDF into parts under a size limit (e.g. the 10MB limit for handing files to Claude via Google Drive).

  python tools/split_pdf.py data/sources/WBnamachu_.pdf --max-mb 9

Parts are written next to the input as  <name>_part01_p0001-0240.pdf ... ; page ranges keep an even number
of pages so a workbook page and its handwritten solution stay in the same part. Uses pypdfium2
(installed with `pip install -e ".[app]"`). Join them back with --join.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import tempfile


def _save(doc, path):
    with open(path, "wb") as f:
        doc.save(f)
    return os.path.getsize(path)


def split(src: str, max_mb: float = 9.0, step: int = 2) -> list[str]:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(src)
    n, limit = len(pdf), max_mb * 1024 * 1024
    base = os.path.splitext(src)[0]
    out, start, k = [], 0, 1
    while start < n:
        # grow the part `step` pages at a time; estimate from bytes per page, then verify the real size
        end = min(n, start + step)
        best = None
        while True:
            part = pdfium.PdfDocument.new()
            part.import_pages(pdf, list(range(start, end)))
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as t:
                tmp = t.name
            size = _save(part, tmp)
            part.close()
            if size > limit and best:
                os.remove(tmp)
                break
            if best:
                os.remove(best[1])
            best = (end, tmp, size)
            if size > limit or end == n:
                break
            per_page = size / (end - start)
            end = min(n, max(end + step, start + int(limit * 0.97 / per_page) // step * step))
        end, tmp, size = best
        name = f"{base}_part{k:02d}_p{start + 1:04d}-{end:04d}.pdf"
        os.replace(tmp, name)
        out.append(name)
        print(f"{os.path.basename(name)}  {size / 1024 / 1024:.1f}MB  ({end - start} pages)")
        start, k = end, k + 1
    pdf.close()
    return out


def join(parts: list[str], dst: str) -> int:
    import pypdfium2 as pdfium
    key = lambda p: int(re.search(r"_part(\d+)_", p).group(1))
    out = pdfium.PdfDocument.new()
    for p in sorted(parts, key=key):
        d = pdfium.PdfDocument(p)
        out.import_pages(d)
        d.close()
    n = len(out)
    _save(out, dst)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="PDF to split, or (with --join) the output path")
    ap.add_argument("--max-mb", type=float, default=9.0)
    ap.add_argument("--join", nargs="+", metavar="PART", help="join parts (glob ok) into PDF")
    a = ap.parse_args(argv)
    if a.join:
        parts = [p for g in a.join for p in sorted(glob.glob(g))]
        print(join(parts, a.pdf), "pages ->", a.pdf)
    else:
        split(a.pdf, a.max_mb)


if __name__ == "__main__":
    sys.exit(main())
