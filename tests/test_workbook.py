import pytest

from pensionlab.lab import workbook
from pensionlab.lab.topics import TOPICS


def test_every_topic_has_workbook_sections():
    assert set(workbook.TOPIC_SECTIONS) == set(TOPICS)
    for t in TOPICS:
        r = workbook.refs(t)
        assert r and all(k in workbook.SECTIONS for k, *_ in r)


def test_sections_start_on_workbook_pages_and_spans_tile():
    pages = [p for _, p in workbook.SECTIONS.values()]
    assert len(set(pages)) == len(pages)
    assert all(p % 2 == 1 for p in pages)               # odd = printed page, even = handwritten solution
    toc = workbook.toc()
    assert toc[0][2] == 1 and toc[-1][3] == workbook.LAST_PAGE
    for (_, _, _, end), (_, _, start, _) in zip(toc, toc[1:]):
        assert end + 1 == start


def test_span_and_alias():
    assert workbook.span("2") == (11, 74)
    assert workbook.span("28") == (1145, 1218)
    assert workbook.refs("life_annuity")[0][1] == "6 年金現価"


def test_missing_pdf(monkeypatch, tmp_path):
    monkeypatch.setenv("LAB_WORKBOOK", str(tmp_path / "none.pdf"))
    assert not workbook.available()


@pytest.mark.skipif(not workbook.available(), reason="workbook PDF is kept out of git")
def test_render_page():
    png = workbook.render(11, dpi=30)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(ValueError):
        workbook.render(0)
