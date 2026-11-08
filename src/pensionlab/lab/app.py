"""Streamlit practice screen: streamlit run src/pensionlab/lab/app.py"""
from __future__ import annotations

import json
import os
import time

import streamlit as st

from pensionlab.lab import db
from pensionlab.lab.verifiers import CHOICE, choices, truth_text

DB_PATH = os.environ.get("LAB_DB", "data/lab.sqlite")
PROBLEMS_DIR = os.environ.get("LAB_PROBLEMS", "problems")
LEDGER = os.environ.get("LAB_LEDGER", "sources/ledger.json")
ERROR_TYPES = ["timing(due/immediate)", "interest/discount", "mortality/survival", "arithmetic", "other"]
CONF = {1: "1 自信なし", 2: "2 まあまあ", 3: "3 自信あり"}

st.set_page_config(page_title="年金数理 Learning Lab", page_icon="📘")
con = db.connect(DB_PATH)
ss = st.session_state


def start(problem_id):
    ss.update(pid=problem_id, hint=0, t0=time.time(), result=None, saved=False)


# ---- sidebar: data + stats
with st.sidebar:
    st.header("📘 Learning Lab")
    if os.path.isdir(PROBLEMS_DIR) and st.button("問題と出典台帳を読み込む"):
        if os.path.exists(LEDGER):
            db.load_sources(con, LEDGER)
        n = sum(db.load_problems(con, os.path.join(PROBLEMS_DIR, f))
                for f in sorted(os.listdir(PROBLEMS_DIR)) if f.endswith(".json"))
        st.success(f"{n}問を読み込みました")
    stats = db.stats_by_topic(con)
    st.subheader("分野別成績")
    if stats:
        st.dataframe([{"分野": r["topic"], "回数": r["n"], "正答率%": r["pct"], "正解だが低確信": r["correct_unsure"]}
                      for r in stats], hide_index=True)
    else:
        st.caption("まだ解答がありません")
    st.metric("復習期限の問題", len(db.due_reviews(con)))
    recheck = db.problems_needing_recheck(con)
    if recheck:
        st.warning(f"出典が差替・要確認の問題 {len(recheck)}問: " + ", ".join(r["id"] for r in recheck))

# ---- pick problem
if "pid" not in ss:
    nxt = db.next_problem(con)
    if nxt:
        start(nxt["id"])
if "pid" not in ss:
    st.title("年金数理 Learning Lab")
    st.info("問題がありません。サイドバーから問題を読み込んでください。")
    st.stop()

p = db.get_problem(con, ss.pid)
st.title("年金数理 Learning Lab")
src = con.execute("SELECT title, version, verification FROM sources WHERE id=?", (p["source_id"],)).fetchone() \
    if p["source_id"] else None
where = f"{src['title']}" + (f"（{src['version']}）" if src and src["version"] else "") if src else p["source"]
qno = f" {p['question_no']}" if p["question_no"] else ""
extra = f" ｜ 難易度 {p['difficulty']}" if p["difficulty"] else ""
extra += f" ｜ 配点 {p['points']}点" if p["points"] else ""
st.caption(f"{p['id']} ｜ {p['exam_body']}{qno} ｜ {p['topic']}{extra} ｜ 出典: {where}")
if src and src["verification"] in ("needs_recheck", "superseded"):
    st.warning("この問題の出典資料は差し替え・要確認です。正答を最新版と照合してください。")
st.markdown(f"#### {p['statement']}")
is_choice = p["verifier_id"] == CHOICE
params = json.loads(p["params"])
q_url = db.source_url(con, p)
if q_url:
    st.markdown(f"📄 [問題文を公式PDFで開く（p.{p['page']}）]({q_url})")
if p["note"]:
    st.caption(f"注: {p['note']}")

# ---- hints
if ss.result is None and db.get_hint(con, p["id"], 1):
    if st.button("💡 ヒントを見る"):
        ss.hint += 1
for lvl in range(1, ss.hint + 1):
    st.info(f"ヒント{lvl}: " + (db.get_hint(con, p["id"], lvl) or "これ以上ヒントはありません"))

# ---- answer
if ss.result is None:
    with st.form("answer"):
        if is_choice:
            raw = st.radio("選択肢", choices(params), horizontal=True, index=None)
        else:
            raw = st.text_input("答え（数値）")
        conf = st.radio("確信度", list(CONF), format_func=CONF.get, index=1, horizontal=True)
        if st.form_submit_button("解答する"):
            try:
                if raw is None:
                    raise ValueError
                ans = raw if is_choice else float(raw)
            except ValueError:
                st.error("選択肢を選んでください" if is_choice else "数値で入力してください")
            else:
                ok = db.record_attempt(con, p["id"], ans, conf, time.time() - ss.t0)
                shown = f"({ans})" if is_choice else f"{ans:.4f}"
                ss.result = {"ok": ok, "ans": shown, "truth": truth_text(p["verifier_id"], params)}
                st.rerun()
else:
    r = ss.result
    if r["ok"]:
        st.success(f"✅ 正解！（あなたの答え {r['ans']}）")
    else:
        label = "正答" if is_choice else "再計算値"
        st.error(f"❌ 不正解。{label} = {r['truth']}（あなたの答え {r['ans']}）")
    a_url = db.source_url(con, p, "answer_page")
    if a_url and p["answer_page"]:
        st.markdown(f"📘 [公式の解答例を開く（p.{p['answer_page']}）]({a_url})")
    if not r["ok"]:
        if not ss.saved:
            et = st.selectbox("誤りの種類", ERROR_TYPES)
            if st.button("誤りタイプを記録"):
                db.set_last_error_type(con, p["id"], et)
                ss.saved = True
                st.rerun()
        else:
            st.caption("誤りタイプを記録しました")
    if st.button("次の問題へ ▶"):
        nxt = db.next_problem(con)
        if nxt:
            start(nxt["id"])
        else:
            for k in ("pid", "result"):
                ss.pop(k, None)
        st.rerun()
