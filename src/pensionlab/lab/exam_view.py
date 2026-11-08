"""Streamlit page for 本番モード."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from . import db, exam
from .verifiers import CHOICE, CHOICE_SET, choices, truth_text


def _input(p):
    params = json.loads(p["params"])
    label = p["question_no"].replace(p["section"], "", 1) or p["question_no"]
    key = f"exam-{p['id']}"
    if p["verifier_id"] == CHOICE:
        v = st.selectbox(label, ["—"] + choices(params), key=key)
        return None if v == "—" else v
    if p["verifier_id"] == CHOICE_SET:
        return "".join(st.multiselect(label + "（すべて選択）", choices(params), key=key)) or None
    return st.text_input(label + "（数字）", key=key) or None


def render(con):
    ss = st.session_state
    st.subheader("本番モード")
    years = [r["year"] for r in con.execute(
        "SELECT DISTINCT year FROM problems WHERE exam_body='IAJ' ORDER BY year DESC")]
    if not years:
        st.info("公式過去問がまだ読み込まれていません。サイドバーから読み込んでください。")
        return

    if "exam_result" in ss:
        r = ss.exam_result
        st.success(f"{r['year']}年度：{r['total']} / {r['max']} 点（{r['answered']}/{r['slots']} 欄解答、{r['minutes']}分）")
        if r["over_time"]:
            st.warning("制限時間を超えて提出しました。")
        cols = st.columns(len(r["by_section"]))
        for c, (sec, (e, m)) in zip(cols, r["by_section"].items()):
            c.metric(sec, f"{e} / {m}")
        st.subheader("採点結果（採点単位ごと）")
        rows = []
        for key, earned, mx, ids in r["units"]:
            first = db.get_problem(con, ids[0])
            last = db.get_problem(con, ids[-1])["question_no"]
            name = first["question_no"] + (f"〜{last.replace(first['section'], '', 1)} 完答" if len(ids) > 1 else "")
            rows.append({"問題": name,
                         "分野": first["topic"], "得点": f"{earned} / {mx}",
                         "結果": "○" if earned == mx and mx > 0 else ("—" if mx == 0 else "×"),
                         "正答": " ".join(truth_text(db.get_problem(con, i)["verifier_id"],
                                                    json.loads(db.get_problem(con, i)["params"])) for i in ids),
                         "解答例": db.source_url(con, first, "answer_page")})
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     column_config={"解答例": st.column_config.LinkColumn("解答例", display_text="PDF")})
        st.caption("誤答した欄は復習キューに入り、演習画面で優先的に出題されます。")
        if st.button("もう一度受ける / 年度を選ぶ"):
            del ss["exam_result"]
            st.rerun()
        return

    if "exam_sid" not in ss:
        year = st.selectbox("年度", years)
        limit = st.number_input("制限時間（分）", 10, 300, exam.DEFAULT_LIMIT_MIN, step=10)
        st.caption("2026年度の年金数理は 12月9日 10:00 開始・180分（日本アクチュアリー会 試験日程）。"
                   "問題文は公式PDFを別ウィンドウで開いて解いてください。")
        if st.button("開始する"):
            ss.exam_sid, ss.exam_year = exam.start(con, int(year), limit_min=int(limit)), int(year)
            st.rerun()
        return

    remain = exam.remaining_seconds(con, ss.exam_sid)
    probs = exam.problems(con, ss.exam_year)
    url = db.source_url(con, probs[0])
    st.metric("残り時間（画面操作のたびに更新）", f"{int(remain // 60)}分" if remain > 0 else "時間切れ")
    if url:
        st.markdown(f"📄 [{ss.exam_year}年度の問題PDFを開く]({url.split('#')[0]})")
    responses = {}
    with st.form("exam"):
        by_section: dict[str, list] = {}
        for p in probs:
            by_section.setdefault(p["section"], []).append(p)
        for section, items in by_section.items():
            st.subheader(section)
            for i in range(0, len(items), 4):          # mark-sheet style: 4 slots per row
                for col, p in zip(st.columns(4), items[i:i + 4]):
                    with col:
                        responses[p["id"]] = _input(p)
        submitted = st.form_submit_button("提出して採点する")
    if submitted:
        r = exam.submit(con, ss.exam_sid, responses)
        ss.exam_result = {**r, "year": ss.exam_year}
        del ss["exam_sid"]
        st.rerun()
