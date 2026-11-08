import importlib.util
from pathlib import Path

import pytest

pdfium = pytest.importorskip("pypdfium2")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("split_pdf", ROOT / "tools/split_pdf.py")
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)


def make_pdf(path, pages):
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(595, 842)
    with open(path, "wb") as f:
        doc.save(f)


def test_split_respects_limit_keeps_pairs_and_joins_back(tmp_path):
    src = tmp_path / "wb.pdf"
    make_pdf(src, 40)
    size_mb = src.stat().st_size / 1024 / 1024
    parts = sp.split(str(src), max_mb=size_mb / 3)
    assert len(parts) >= 3
    counts = [len(pdfium.PdfDocument(p)) for p in parts]
    assert sum(counts) == 40 and all(c % 2 == 0 for c in counts)
    assert all(Path(p).stat().st_size <= size_mb / 3 * 1024 * 1024 for p in parts)
    assert "_part01_p0001-" in parts[0]
    out = tmp_path / "joined.pdf"
    assert sp.join(parts[::-1], str(out)) == 40
