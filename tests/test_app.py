import pytest

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def make(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DB", str(tmp_path / "t.sqlite"))
    monkeypatch.setenv("LAB_SAMPLE", str(ROOT / "problems/sample.json"))
    return AppTest.from_file(str(ROOT / "src/pensionlab/lab/app.py"), default_timeout=20)


def btn(at, label):
    return next(b for b in at.button if label in b.label)


def test_flow(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend("src")
    at = make(tmp_path, monkeypatch).run()
    assert not at.exception and at.info  # empty state message
    at.sidebar.button[0].click().run()
    at = at.run()
    assert "S-001" in at.caption[0].value
    btn(at, "ヒント").click().run()
    assert any("ヒント1" in i.value for i in at.info)
    at.text_input[0].set_value("abc"); btn(at, "解答").click().run()
    assert at.error                                 # invalid input
    at.text_input[0].set_value("1.0"); at.radio[0].set_value(3)
    btn(at, "解答").click().run()
    assert any("不正解" in e.value for e in at.error)
    at.selectbox[0].select("arithmetic"); btn(at, "記録").click().run()
    assert any("記録しました" in c.value for c in at.caption)
    btn(at, "次の問題").click().run()
    assert not at.exception
