import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "src/pensionlab/lab/app.py")


def radio(at, label):
    return next(r for r in at.radio if r.label == label)


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
    monkeypatch.setenv("LAB_WB_MARKS", str(tmp_path / "no_marks.json"))     # keep the learner's own marks out
    monkeypatch.setenv("LAB_WORKBOOK", str(tmp_path / "no.pdf"))            # behave like the cloud (no PDF)
    monkeypatch.setenv("LAB_ANKI_CARDS", str(tmp_path / "no_cards.json"))   # and no formula cards
    at = AppTest.from_file(APP, default_timeout=20).run()      # data is loaded automatically
    assert not at.exception
    return at


def test_numeric_flow(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["sample.json"])
    assert "S-001" in at.caption[0].value
    btn(at, "ヒント").click().run()
    assert any("ヒント1" in i.value for i in at.info)
    at.text_input[0].set_value("abc"); btn(at, "解答").click().run()
    assert at.error
    at.text_input[0].set_value("1.0"); radio(at, "確信度").set_value(3)
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
    btn(at, "ヒント").click().run()                             # 2025 has self-written approach hints
    assert any("ヒント1" in i.value and "昇給" in i.value for i in at.info)
    btn(at, "解答").click().run()
    assert any("解答を入力" in e.value for e in at.error)
    radio(at, "選択肢").set_value("C"); btn(at, "解答").click().run()
    assert any("正解" in s.value for s in at.success)
    assert any("2025D.pdf#page=23" in m.value for m in at.markdown)
    btn(at, "次の問題").click().run()
    assert "IAJ-2025-1-2" in at.caption[0].value


def test_dashboard_page(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    radio(at, "選択肢").set_value("C"); btn(at, "解答").click().run()
    at.radio(key="page").set_value("ダッシュボード").run()
    assert not at.exception
    assert any("2025年度" in m.label and "5 / 100" in m.value for m in at.metric)
    assert any("対象の欄はまだありません" in c.value for c in at.caption)   # 1 correct, sure-ish answer only


def test_choice_set_and_digits_inputs(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2021.json"])
    radio(at, "選択肢").set_value("C"); btn(at, "解答").click().run()          # 1(1)
    btn(at, "次の問題").click().run()
    assert "IAJ-2021-1-2" in at.caption[0].value                           # select-all question
    at.multiselect[0].select("D").select("A").select("B"); btn(at, "解答").click().run()
    assert any("正解" in s.value for s in at.success)
    for _ in range(4):                                                      # skip to 1(6)
        btn(at, "次の問題").click().run()
        if "IAJ-2021-1-6" in at.caption[0].value:
            break
        radio(at, "選択肢").set_value("A"); btn(at, "解答").click().run()
    assert "IAJ-2021-1-6" in at.caption[0].value
    at.text_input[0].set_value("９９５"); btn(at, "解答").click().run()
    assert any("正解" in s.value for s in at.success)


def test_exam_mode_page(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    at.radio(key="page").set_value("本番モード").run()
    btn(at, "開始").click().run()
    assert not at.exception and len(at.selectbox) == 36
    at.selectbox[0].select("C")                         # 問題1(1) correct (form commits on submit)
    btn(at, "提出").click().run()
    assert not at.exception
    assert any("5 / 100 点" in s.value for s in at.success)
    at.radio(key="page").set_value("ダッシュボード").run()
    assert not at.exception


def test_backup_download_present(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    assert not at.exception
    assert any("バックアップ" in e.label for e in at.sidebar.expander)


def test_practice_filters(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json", "iaj-2024.json", "sample.json"])
    assert "IAJ-2025-1-1" in at.caption[0].value                            # past exams first, newest year first
    at.sidebar.multiselect[0].select(2024).run()
    assert "IAJ-2024-1-1-ア" in at.caption[0].value
    at.sidebar.multiselect[1].select("生命表・平均余命").run()
    assert any("条件に合う問題がありません" in i.value for i in at.info)       # no 2024 life-table slot
    at.sidebar.multiselect[0].unselect(2024).run()
    assert "IAJ-2025-1-3" in at.caption[0].value                            # the 2025 life-table question
    at.sidebar.selectbox[0].select("wrong").run()
    assert any("条件に合う問題がありません" in i.value for i in at.info)


def test_memo_saved(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    radio(at, "選択肢").set_value("A"); btn(at, "解答").click().run()
    at.text_area[0].set_value("動態的昇給率の定義を確認")
    btn(at, "メモを保存").click().run()
    import sqlite3
    c = sqlite3.connect(tmp_path / "t.sqlite")
    assert c.execute("SELECT text FROM notes").fetchone()[0] == "動態的昇給率の定義を確認"


def test_recommend_status(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    at.sidebar.selectbox[0].select("recommend").run()
    assert any("おすすめの理由: 未着手の分野" in i.value for i in at.info)


def test_plan_page(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json", "iaj-2024.json"])
    at.radio(key="page").set_value("学習計画").run()
    assert not at.exception
    assert any("本番まで" in m.label for m in at.metric)


def test_tools_page(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    at.radio(key="page").set_value("計算ツール").run()
    assert not at.exception and len(at.tabs) == 3


def test_auto_sync_picks_up_changed_files(tmp_path, monkeypatch):
    import json, sqlite3
    at = make(tmp_path, monkeypatch, ["sample.json"])
    assert "S-001" in at.caption[0].value
    f = tmp_path / "problems" / "sample.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data[0]["statement"] = "更新後の問題文"
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    at.run()
    c = sqlite3.connect(tmp_path / "t.sqlite")
    assert c.execute("SELECT statement FROM problems WHERE id='S-001'").fetchone()[0] == "更新後の問題文"


def test_workbook_links_without_pdf(tmp_path, monkeypatch):
    marks = tmp_path / "marks.json"
    marks.write_text('{"marks": [{"wb_id": "1.2", "page": 3, "month": 11, "day": 3, "mark": "△"}],'
                     ' "tags": [{"wb_id": "1.2", "tag": "2X"}]}', encoding="utf-8")
    make(tmp_path, monkeypatch, ["iaj-2025.json"])
    monkeypatch.setenv("LAB_WB_MARKS", str(marks))           # make() points it at an empty file
    at = AppTest.from_file(APP, default_timeout=20).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "問題1.2" in text and "11/3△（誤答2回）" in text
    assert any("PDF はこの端末にない" in c.value for c in at.caption)


def test_dashboard_strengths(tmp_path, monkeypatch):
    at = make(tmp_path, monkeypatch, ["iaj-2025.json"])
    radio(at, "画面").set_value("ダッシュボード").run()
    assert not at.exception
    assert any("得意・不得意" in s.value for s in at.subheader)


def test_formula_cards_page_and_panel(tmp_path, monkeypatch):
    from test_cards import make_apkg
    from pensionlab.lab import cards
    data = cards.convert(str(make_apkg(tmp_path / "d.apkg")), {"g-basic": "昇給率・給与指数"})
    (tmp_path / "cards.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    make(tmp_path, monkeypatch, ["iaj-2025.json"])
    monkeypatch.setenv("LAB_ANKI_CARDS", str(tmp_path / "cards.json"))
    at = AppTest.from_file(APP, default_timeout=20).run()
    assert not at.exception
    n = 1 + sum(c["topic"] == "昇給率・給与指数" for c in json.loads(cards.EXTRA.read_text(encoding="utf-8"))["cards"])
    assert any(f"公式カード：昇給率・給与指数（{n}枚）" in e.label for e in at.expander)   # IAJ-2025-1-1 is 昇給率
    radio(at, "画面").set_value("公式カード").run()
    assert not at.exception
    sel = next(s for s in at.selectbox if s.label == "分野" and "今日の復習（0枚）" in s.options)
    assert any(o.startswith(f"昇給率・給与指数（{n}枚") for o in sel.options)
    sel.set_value("昇給率・給与指数").run()
    next(t for t in at.toggle if t.label == "答えを表示").set_value(True).run()
    btn(at, "△ 書けなかった").click().run()
    assert not at.exception
    assert any("△ を記録しました（次回は1日後）" in s.value for s in at.success)
