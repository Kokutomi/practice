"""Streamlit rendering of the formula cards (Anki deck + own cards), with self-grading."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from . import cards
from .topics import TOPICS, canonical

GRADE_HELP = {"◎": "すらすら書けた", "○": "思い出せたが迷った", "△": "書けなかった"}
DUE = "今日の復習"


def show(card, reveal: bool) -> None:
    label = f"{card['num']}　" if card["num"] else ""
    st.caption(f"{label}{card['topic'] or '未分類'}")
    st.markdown(card["front"], unsafe_allow_html=True)
    if reveal:
        st.markdown("<hr style='margin:6px 0'>", unsafe_allow_html=True)
        st.markdown(card["back"], unsafe_allow_html=True)


def _grade_buttons(con, card, key: str) -> None:
    s = cards.state(con, card["guid"])
    if s:
        st.caption(f"前回 {s['last_grade']}・次回 {datetime.fromtimestamp(s['due_at']):%m/%d}")
    cols = st.columns(3)
    for col, g in zip(cols, cards.GRADES):
        if col.button(f"{g} {GRADE_HELP[g]}", key=f"{key}-g-{g}", use_container_width=True):
            days = cards.review(con, card["guid"], g)
            st.session_state[f"{key}-msg"] = f"{g} を記録しました（次回は{days:g}日後）"
            st.session_state[f"{key}-next"] = True
            st.rerun()


def flash(con, rows, key: str) -> None:
    """One card at a time: number picker, reveal toggle, then ◎/○/△ to schedule the next review."""
    if not rows:
        return
    ik = f"{key}-i"
    if st.session_state.pop(f"{key}-next", False):          # after grading, move on to the next card
        st.session_state[ik] = min(st.session_state.get(ik, 1) + 1, len(rows))
    if st.session_state.get(ik, 1) > len(rows):
        st.session_state[ik] = len(rows)
    i = st.number_input(f"カード（全{len(rows)}枚）", min_value=1, max_value=len(rows), step=1, key=ik) - 1
    msg = st.session_state.pop(f"{key}-msg", None)
    if msg:
        st.success(msg)
    reveal = st.toggle("答えを表示", key=f"{key}-reveal-{rows[i]['guid']}")
    with st.container(border=True):
        show(rows[i], reveal)
    if reveal:
        _grade_buttons(con, rows[i], key)


def practice_panel(con, topic: str | None) -> None:
    """Expander under a practice problem: the formula cards of its topic."""
    t = canonical(topic or "")
    if not cards.counts(con):
        return
    rows = cards.for_topic(con, t)
    n_due = len(cards.due(con, t))
    label = f"🃏 公式カード：{t}（{len(rows)}枚" + (f"・復習期限{n_due}枚" if n_due else "") + "）"
    with st.expander(label):
        if rows:
            flash(con, rows, f"pc-{t}")
        else:
            st.caption("この分野に分類された公式カードはありません。「公式カード」画面で他の分野を見られます。")


def uploader(con) -> None:
    """Sidebar: load the deck where data/anki/cards.json is not available (phone / cloud)."""
    with st.expander("公式カード（Anki）"):
        n = sum(cards.counts(con).values())
        st.caption(f"登録済み: {n}枚" if n else "未登録。Anki の .apkg（または cards.json）を選んでください。")
        up = st.file_uploader("デッキを読み込む", type=["apkg", "json"], key="cards_upload")
        if up is not None and st.button("読み込む", key="cards_upload_btn"):
            try:
                st.success(f"{cards.load_upload(con, up.name, up.getvalue())}枚を読み込みました")
            except Exception as e:                        # bad/unsupported file: tell the learner, keep running
                st.error(f"読み込めませんでした: {e}")


def render(con) -> None:
    st.subheader("公式カード")
    cnt = cards.counts(con)
    if not cnt:
        st.info("公式カードがまだありません。PC では `python tools/import_anki.py <デッキ.apkg>`、"
                "スマホではサイドバーの「公式カード（Anki）」から .apkg を読み込んでください。")
        return
    due_all = cards.due(con)
    st.caption("答えを表示したら ◎（すらすら書けた）・○（迷った）・△（書けなかった）を付けてください。"
               "△は翌日、○は少し先、◎は間隔を広げて「今日の復習」に戻ってきます。結果は得意・不得意の指標に入ります。")
    opts = [DUE] + [t for t in TOPICS if cnt.get(t)] + (["未分類"] if cnt.get(None) else [])
    mastery = cards.mastery_by_topic(con)

    def label(t):
        if t == DUE:
            return f"{DUE}（{len(due_all)}枚）"
        n = cnt.get(None if t == "未分類" else t, 0)
        g = mastery.get(None if t == "未分類" else t, {}).get("graded", 0)
        return f"{t}（{n}枚・採点済み{g}）"

    topic = st.selectbox("分野", opts, format_func=label, key="cards-topic")
    if topic == DUE:
        rows = due_all
        if not rows:
            st.success("今日復習するカードはありません。分野を選んで新しいカードを進めましょう。")
            return
    elif topic == "未分類":
        rows = [r for r in cards.for_topic(con, None) if not r["topic"]]
    else:
        rows = cards.for_topic(con, topic)
    empty = [t for t in TOPICS if not cnt.get(t)]
    if empty:
        st.caption("公式カードのない分野: " + "、".join(empty))
    mode = st.radio("表示", ["1枚ずつ（採点あり）", "一覧（答えも表示）"], horizontal=True, key="cards-mode")
    if mode.startswith("1枚ずつ"):
        flash(con, rows, f"cp-{topic}")
    else:
        for r in rows:
            with st.container(border=True):
                show(r, True)
