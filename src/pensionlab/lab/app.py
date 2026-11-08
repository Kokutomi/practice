"""Streamlit practice screen: streamlit run src/pensionlab/lab/app.py"""
from __future__ import annotations

import json
import os
import time

import streamlit as st

from pensionlab.lab import backup, db
from pensionlab.lab.topics import TOPICS
from pensionlab.lab.verifiers import CHOICE, CHOICE_SET, DIGITS, KEYED, choices, truth_text

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
    page = st.radio("画面", ["演習", "本番モード", "ダッシュボード"], horizontal=True)
    if os.path.isdir(PROBLEMS_DIR) and st.button("問題と出典台帳を読み込む"):
        if os.path.exists(LEDGER):
            db.load_sources(con, LEDGER)
        n = sum(db.load_problems(con, os.path.join(PROBLEMS_DIR, f))
                for f in sorted(os.listdir(PROBLEMS_DIR)) if f.endswith(".json"))
        st.success(f"{n}問を読み込みました")
    st.metric("復習期限の問題", len(db.due_reviews(con)))
    with st.expander("学習記録のバックアップ"):
        st.download_button("バックアップをダウンロード", json.dumps(backup.dump(con), ensure_ascii=False),
                           f"pensionlab-backup-{time.strftime('%Y%m%d')}.json", "application/json")
        up = st.file_uploader("バックアップから復元（追加マージ）", type="json")
        if up is not None and st.button("復元する"):
            try:
                st.success(f"復元しました: {backup.restore(con, json.load(up))}")
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                st.error(f"復元できませんでした: {e}")
    recheck = db.problems_needing_recheck(con)
    if recheck:
        st.warning(f"出典が差替・要確認の問題 {len(recheck)}問: " + ", ".join(r["id"] for r in recheck))

if page == "本番モード":
    from pensionlab.lab import exam_view
    exam_view.render(con)
    st.stop()

if page == "ダッシュボード":
    from pensionlab.lab import dashboard_view
    dashboard_view.render(con)
    st.stop()

# ---- filters (practice only)
with st.sidebar:
    st.subheader("出題の絞り込み")
    years_all = [r[0] for r in con.execute("SELECT DISTINCT year FROM problems ORDER BY year DESC")]
    f_status = st.selectbox("状態", list(db.STATUSES), format_func=db.STATUSES.get)
    f_years = st.multiselect("年度", years_all)
    f_topics = st.multiselect("分野", TOPICS)
    f_body = st.selectbox("出題元", ["", "IAJ", "original"],
                          format_func=lambda v: {"": "すべて", "IAJ": "アクチュアリー会過去問", "original": "自作問題"}[v])
filters = {"status": f_status, "years": f_years, "topics": f_topics, "exam_body": f_body or None}
n_cand = len(db.candidates(con, **filters))
st.sidebar.caption(f"条件に合う問題: {n_cand}")
sig = json.dumps(filters, sort_keys=True)
if ss.get("filter_sig") != sig:
    ss.filter_sig = sig
    for k in ("pid", "result"):
        ss.pop(k, None)

# ---- pick problem
if "pid" not in ss:
    nxt = db.next_problem(con, **filters)
    if nxt:
        start(nxt["id"])
if "pid" not in ss:
    st.title("年金数理 Learning Lab")
    has_any = con.execute("SELECT 1 FROM problems LIMIT 1").fetchone()
    st.info("条件に合う問題がありません。絞り込みを変えてください。" if has_any
            else "問題がありません。サイドバーから問題を読み込んでください。")
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
vid = p["verifier_id"]
is_choice = vid in KEYED
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
        if vid == CHOICE:
            raw = st.radio("選択肢", choices(params), horizontal=True, index=None)
        elif vid == CHOICE_SET:
            picked = st.multiselect("当てはまるものをすべて選択", choices(params))
            raw = "".join(picked) or None
        elif vid == DIGITS:
            raw = st.text_input("答え（数字をそのまま。例: 050）") or None
        else:
            raw = st.text_input("答え（数値）")
        conf = st.radio("確信度", list(CONF), format_func=CONF.get, index=1, horizontal=True)
        if st.form_submit_button("解答する"):
            try:
                if raw is None:
                    raise ValueError
                ans = raw if is_choice else float(raw)
            except ValueError:
                st.error("解答を入力してください" if is_choice else "数値で入力してください")
            else:
                ok = db.record_attempt(con, p["id"], ans, conf, time.time() - ss.t0)
                shown = (f"({ans})" if vid == CHOICE else ans) if is_choice else f"{ans:.4f}"
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
        nxt = db.next_problem(con, exclude={p["id"]}, **filters)
        if nxt:
            start(nxt["id"])
        else:
            for k in ("pid", "result"):
                ss.pop(k, None)
        st.rerun()
