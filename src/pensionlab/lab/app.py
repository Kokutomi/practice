"""Streamlit practice screen: streamlit run src/pensionlab/lab/app.py"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[3]          # repo root (src/pensionlab/lab/app.py)
if str(ROOT / "src") not in sys.path:                # works without `pip install -e .` (e.g. Streamlit Cloud)
    sys.path.insert(0, str(ROOT / "src"))

from pensionlab.lab import backup, db, notes, textbook, wblink, workbook  # noqa: E402
from pensionlab.lab.topics import TOPICS, canonical  # noqa: E402
from pensionlab.lab.verifiers import CHOICE, CHOICE_SET, DIGITS, KEYED, choices, truth_text

DB_PATH = os.environ.get("LAB_DB", str(ROOT / "data" / "lab.sqlite"))
PROBLEMS_DIR = os.environ.get("LAB_PROBLEMS", str(ROOT / "problems"))
LEDGER = os.environ.get("LAB_LEDGER", str(ROOT / "sources" / "ledger.json"))
PAGES = ["演習", "本番モード", "ダッシュボード", "学習計画", "計算ツール"]
ERROR_TYPES = ["timing(due/immediate)", "interest/discount", "mortality/survival", "arithmetic", "other"]
CONF = {1: "1 自信なし", 2: "2 まあまあ", 3: "3 自信あり"}

st.set_page_config(page_title="年金数理 Learning Lab", page_icon="📘")
con = db.connect(DB_PATH)
ss = st.session_state


@st.cache_data(max_entries=64, show_spinner=False)
def wb_page(page: int) -> bytes:
    return workbook.render(page)


def start(problem_id):
    ss.update(pid=problem_id, hint=0, t0=time.time(), result=None, saved=False)


# page switcher on top of the main area: on a phone the sidebar is hidden behind a button
page = st.radio("画面", PAGES, horizontal=True, key="page", label_visibility="collapsed")

# a fresh database (e.g. after the cloud app restarted) gets an obvious restore prompt
if not con.execute("SELECT 1 FROM attempts LIMIT 1").fetchone() and page == "演習":
    with st.expander("学習記録が空です。バックアップがあればここから復元できます", expanded=False):
        up0 = st.file_uploader("バックアップ（.json）", type="json", key="restore_main")
        if up0 is not None and st.button("復元する", key="restore_main_btn"):
            try:
                st.success(f"復元しました: {backup.restore(con, json.load(up0))}")
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                st.error(f"復元できませんでした: {e}")

# ---- sidebar: data + stats
with st.sidebar:
    st.header("📘 Learning Lab")
    synced = db.sync_data(con, PROBLEMS_DIR, LEDGER)      # picks up updated problem files automatically
    if synced:
        st.caption(f"問題データを更新しました（{synced}欄）")
    if wblink.sync_marks(con):                          # data/wb_marks.json (PC only; the phone gets it via backup)
        st.caption("ワークブックの◎/△記録を取り込みました")
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

if page == "計算ツール":
    from pensionlab.lab import tools_view
    tools_view.render(con)
    st.stop()

if page == "学習計画":
    from pensionlab.lab import plan_view
    plan_view.render(con)
    st.stop()

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
    st.subheader("年金数理 Learning Lab")
    has_any = con.execute("SELECT 1 FROM problems LIMIT 1").fetchone()
    st.info("条件に合う問題がありません。絞り込みを変えてください。" if has_any
            else "問題がありません。サイドバーから問題を読み込んでください。")
    st.stop()

p = db.get_problem(con, ss.pid)
src = con.execute("SELECT title, version, verification FROM sources WHERE id=?", (p["source_id"],)).fetchone() \
    if p["source_id"] else None
short_ver = (src["version"] or "").split("（")[0] if src else ""
where = f"{src['title']}" + (f"（{short_ver}）" if short_ver else "") if src else p["source"]
qno = f" {p['question_no']}" if p["question_no"] else ""
extra = f" ｜ 難易度 {p['difficulty']}" if p["difficulty"] else ""
extra += f" ｜ 配点 {p['points']}点" if p["points"] else ""
st.caption(f"{p['id']} ｜ {p['exam_body']}{qno} ｜ {canonical(p['topic'] or '')}{extra} ｜ 出典: {where}")
if src and src["verification"] in ("needs_recheck", "superseded"):
    st.warning("この問題の出典資料は差し替え・要確認です。正答を最新版と照合してください。")
if f_status == "recommend":
    from pensionlab.lab.recommend import recommend
    why = next((r["reason"] for r in recommend(con, n=100, exam_body=None) if r["problem"]["id"] == p["id"]), None)
    if why:
        st.info(f"おすすめの理由: {why}")
st.markdown(f"**{p['statement']}**")
vid = p["verifier_id"]
is_choice = vid in KEYED
params = json.loads(p["params"])
q_url = db.source_url(con, p)
if q_url:
    st.markdown(f"📄 [問題文を公式PDFで開く（p.{p['page']}）]({q_url})")
if p["note"]:
    st.caption(f"注: {p['note']}")
tb = textbook.refs(p["topic"] or "")
if tb:
    st.caption("📖 教科書: " + " ／ ".join(f"[{t}（p.{pg}）]({u})" for t, pg, u in tb))
MATCH_JA = {"strong": "同型", "related": "同じ論点"}
rel = wblink.related(p["id"])
if rel:
    with st.expander(f"📒 ワークブックの対応問題（{len(rel)}問）", expanded=False):
        for r in rel:
            e, h = r["entry"], wblink.history(con, r["wb_id"])
            sol = "・".join(str(x) for x in e["solution_pages"])
            tags = f" ｜ {'・'.join(h['tags'])}" if h["tags"] else ""
            st.markdown(f"**問題{e['wb_id']}**（{MATCH_JA[r['match']]}）{e.get('summary', '')}  \n"
                        f"p.{e['page']}／手書き解答 p.{sol} ｜ {r['reason']}  \n"
                        f"昨年の記録: {wblink.history_text(h)}{tags}")
        if workbook.available():
            pick = st.selectbox("ページを表示", rel, format_func=lambda r: f"問題{r['wb_id']}（p.{r['entry']['page']}）",
                                key=f"wb-rel-{p['id']}")
            e = pick["entry"]
            tabs = st.tabs([f"問題 p.{x}" for x in e["pages"]] + [f"手書き解答 p.{x}" for x in e["solution_pages"]])
            for tab, pg in zip(tabs, e["pages"] + e["solution_pages"]):
                with tab:
                    st.image(wb_page(pg))
        else:
            st.caption("PDF はこの端末にないため、問題番号とページだけを表示しています。")
wb = workbook.refs(p["topic"] or "")
if wb and workbook.available():
    with st.expander("📒 ワークブック（手書き解答付き）の該当章"):
        sec = st.selectbox("章・節", wb, format_func=lambda r: f"{r[1]}（PDF p.{r[2]}–{r[3]}）",
                           key=f"wb-sec-{p['id']}")
        _, _, first, last = sec
        pg = st.number_input("問題ページ（奇数）", min_value=first, max_value=last, value=first, step=2,
                             key=f"wb-pg-{p['id']}-{first}")
        pg = int(pg) if (int(pg) - first) % 2 == 0 else int(pg) - 1
        t_prob, t_sol = st.tabs([f"問題 p.{pg}", f"手書き解答 p.{pg + 1}"])
        with t_prob:
            st.image(wb_page(pg))
        with t_sol:
            if pg + 1 <= workbook.LAST_PAGE:
                st.image(wb_page(pg + 1))

# ---- hints
if ss.result is None and db.get_hint(con, p["id"], 1):
    if st.button("💡 ヒントを見る"):
        ss.hint += 1
for lvl in range(1, ss.hint + 1):
    st.info(f"ヒント{lvl}: " + (db.get_hint(con, p["id"], lvl) or "これ以上ヒントはありません"))
if ss.hint and p["exam_body"] != "original":
    st.caption("ヒントは自作（公式解答例の解き方の方針を参考に要約）。数値は含めていません。")

# ---- answer
if ss.result is None:
    with st.form("answer"):
        if vid == CHOICE:
            raw = st.radio("選択肢", choices(params), horizontal=True, index=None, key=f"ans-{p['id']}")
        elif vid == CHOICE_SET:
            picked = st.multiselect("当てはまるものをすべて選択", choices(params))
            raw = "".join(picked) or None
        elif vid == DIGITS:
            raw = st.text_input("答え（数字をそのまま。例: 050）") or None
        else:
            raw = st.text_input("答え（数値）")
        conf = st.radio("確信度", list(CONF), format_func=CONF.get, index=1, horizontal=True, key=f"conf-{p['id']}")
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
    with st.expander("✎ メモ（誤答ノート）", expanded=bool(notes.get(con, p["id"]))):
        memo = st.text_area("気づき・間違えた理由・使った公式", notes.get(con, p["id"]), key=f"memo-{p['id']}")
        if st.button("メモを保存"):
            notes.save(con, p["id"], memo)
            st.toast("メモを保存しました")
    if st.button("次の問題へ ▶"):
        nxt = db.next_problem(con, exclude={p["id"]}, **filters)
        if nxt:
            start(nxt["id"])
        else:
            for k in ("pid", "result"):
                ss.pop(k, None)
        st.rerun()
