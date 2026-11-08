import shutil
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "src/pensionlab/lab/app.py")


def btn(at, label):
    return next(b for b in at.button if label in b.label)


def make(tmp_path, monkeypatch, files):
    pdir = tmp_path / "problems"
    pdir.mkdir()
    for f in files:
        shutil.copy(ROOT / "problems" / f, pdir / f)
    monkeypatch.syspath_prepend(str(ROOT / "src"))
    monkeypatch.setenv("LAB_DB", str(tmp_path / "t.sqlite"))
    monkeypatch.setenv("LAB_PROBLEMS", str(pdir))
    monkeypatch.setenv("LAB_LEDGER", str(ROOT / "sources/ledger.json"))
    at = AppTest.from_file(APP, default_timeout=20).run()
    assert not at.exception and at.info  # empty state
    btn(at, "読み込む").click().run()
    return at.run()


def test_numeric_flow(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["sample.json"])
    assert "S-001" in at.caption[0].value
    btn(at, "ヒント").click().run()
    assert any("ヒント1" in i.value for i in at.info)
    at.text_input[0].set_value("abc"); btn(at, "解答").click().run()
    assert at.error
    at.text_input[0].set_value("1.0"); at.main.radio[0].set_value(3)
    btn(at, "解答").click().run()
    assert any("不正解" in e.value for e in at.error)
    at.selectbox[0].select("arithmetic"); btn(at, "記録").click().run()
    assert any("記録しました" in c.value for c in at.caption)
    btn(at, "次の問題").click().run()
    assert not at.exception


def test_choice_flow_with_official_links(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    assert "IAJ-2025-1-1" in at.caption[0].value and "配点 5点" in at.caption[0].value
    assert any("2025D.pdf#page=1" in m.value for m in at.markdown)
    assert not [b for b in at.button if "ヒント" in b.label]   # no hints for official items
    btn(at, "解答").click().run()
    assert any("解答を入力" in e.value for e in at.error)
    at.main.radio[0].set_value("C"); btn(at, "解答").click().run()
    assert any("正解" in s.value for s in at.success)
    assert any("2025D.pdf#page=23" in m.value for m in at.markdown)
    btn(at, "次の問題").click().run()
    assert "IAJ-2025-1-2" in at.caption[0].value


def test_dashboard_page(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    at.main.radio[0].set_value("C"); btn(at, "解答").click().run()
    at.sidebar.radio[0].set_value("ダッシュボード").run()
    assert not at.exception
    assert any("2025年度" in m.label and "5 / 100" in m.value for m in at.metric)
    assert any("対象の欄はまだありません" in c.value for c in at.caption)   # 1 correct, sure-ish answer only


def test_choice_set_and_digits_inputs(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2021.json"])
    at.main.radio[0].set_value("C"); btn(at, "解答").click().run()          # 1(1)
    btn(at, "次の問題").click().run()
    assert "IAJ-2021-1-2" in at.caption[0].value                           # select-all question
    at.multiselect[0].select("D").select("A").select("B"); btn(at, "解答").click().run()
    assert any("正解" in s.value for s in at.success)
    for _ in range(4):                                                      # skip to 1(6)
        btn(at, "次の問題").click().run()
        if "IAJ-2021-1-6" in at.caption[0].value:
            break
        at.main.radio[0].set_value("A"); btn(at, "解答").click().run()
    assert "IAJ-2021-1-6" in at.caption[0].value
    at.text_input[0].set_value("９９５"); btn(at, "解答").click().run()
    assert any("正解" in s.value for s in at.success)


def test_exam_mode_page(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    at.sidebar.radio[0].set_value("本番モード").run()
    btn(at, "開始").click().run()
    assert not at.exception and len(at.selectbox) == 36
    at.selectbox[0].select("C")                         # 問題1(1) correct (form commits on submit)
    btn(at, "提出").click().run()
    assert not at.exception
    assert any("5 / 100 点" in s.value for s in at.success)
    at.sidebar.radio[0].set_value("ダッシュボード").run()
    assert not at.exception


def test_backup_download_present(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    assert not at.exception
    assert any("バックアップ" in e.label for e in at.sidebar.expander)
