import importlib.util
from pathlib import Path

from pensionlab.lab.verifiers import is_correct, truth_text

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("import_iaj", ROOT / "tools/import_iaj.py")
imp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imp)

PROBLEM = """年金数理（問題）
問題１．次の各問に答えなさい。
（１）……
 (Ａ) 1   (Ｂ) 2   (Ｃ) 3   (Ｄ) 4   (Ｅ) 5
（２）……
 (Ａ) x   (Ｂ) y   (Ｃ) z   (Ｄ) w   (Ｅ) v   (Ｆ) u
問題２．
（１）……
"""
ANSWER = """年金数理（解答例）
問題１．
（１）略
（２）略
問題２．
（１）略
"""
KEY = """        問題番号         正答            配点
問題１．    （１）          (Ｅ)   ５点
（４０点）   （２）          (Ａ) (Ｂ) (Ｄ)   完答で５点
問題２．    （１）    （ア）    (Ｆ)または(Ｇ)   ３点
（３０点）          （イ）①   (Ｇ)   完答で３点
              （イ）②   (Ｃ)
                                       2099 年度
                                   年金数理･･････16
        （２）    ①            𝑎𝑎𝑏𝑏𝑏𝑏       050       完答で３点
"""


def test_build_from_synthetic_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(imp, "pdf_pages", lambda pdf: [PROBLEM, ANSWER, KEY])
    items = imp.build(2099, "x.pdf", {"1-1": {"topic": "T", "summary": "S"}})
    by = {i["id"]: i for i in items}
    assert list(by) == ["IAJ-2099-1-1", "IAJ-2099-1-2", "IAJ-2099-2-1-ア", "IAJ-2099-2-1-イ①",
                        "IAJ-2099-2-1-イ②", "IAJ-2099-2-2-①"]
    one = by["IAJ-2099-1-1"]
    assert one["params"] == {"answer": ["E"], "n_choices": 5} and one["points"] == 5
    assert (one["page"], one["answer_page"], one["topic"], one["statement"]) == (1, 2, "T", "S")
    s = by["IAJ-2099-1-2"]
    assert s["verifier_id"] == "choice_set" and s["params"]["answer"] == ["ABD"] and s["group_key"] == "1-2"
    assert by["IAJ-2099-2-1-ア"]["params"]["answer"] == ["F", "G"]
    g1, g2 = by["IAJ-2099-2-1-イ①"], by["IAJ-2099-2-1-イ②"]
    assert g1["group_key"] == g2["group_key"] == "2-1-イ①" and (g1["points"], g2["points"]) == (3, 0)
    d = by["IAJ-2099-2-2-①"]
    assert d["verifier_id"] == "digits" and d["params"] == {"answer": ["050"]}
    assert d["question_no"] == "問題2(2)①"
    assert sum(i["points"] for i in items) == 5 + 5 + 3 + 3 + 3


def test_keyed_verifiers():
    assert is_correct("choice_set", {"answer": ["ABD"]}, "(D)(A)(B)")
    assert is_correct("choice_set", {"answer": ["ABD"]}, "ｂ，ａ，ｄ")
    assert not is_correct("choice_set", {"answer": ["ABD"]}, "AB")
    assert is_correct("digits", {"answer": ["050"]}, "０５０")
    assert not is_correct("digits", {"answer": ["050"]}, "50")
    assert truth_text("choice_set", {"answer": ["ABD"]}) == "(A)(B)(D)"
