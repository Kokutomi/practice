"""Streamlit rendering of the formula cards (Anki deck)."""
from __future__ import annotations

import streamlit as st

from . import cards
from .topics import TOPICS, canonical


def show(card, reveal: bool) -> None:
    label = f"{card['num']}　" if card["num"] else ""
    st.caption(f"{label}{card['topic'] or '未分類'}")
    st.markdown(card["front"], unsafe_allow_html=True)
    if reveal:
        st.markdown("<hr style='margin:6px 0'>", unsafe_allow_html=True)
        st.markdown(card["back"], unsafe_allow_html=True)


def flash(rows, key: str) -> None:
    """One card at a time: number picker + reveal toggle."""
    if not rows:
        return
    i = st.number_input(f"カード（全{len(rows)}枚）", min_value=1, max_value=len(rows), value=1, step=1,
                        key=f"{key}-i") - 1
    reveal = st.toggle("答えを表示", key=f"{key}-reveal-{i}")
    with st.container(border=True):
        show(rows[i], reveal)


def practice_panel(con, topic: str | None) -> None:
    """Expander under a practice problem: the formula cards of its topic."""
    t = canonical(topic or "")
    rows = cards.for_topic(con, t)
    if not cards.counts(con):
        return
    with st.expander(f"🃏 公式カード：{t}（{len(rows)}枚）"):
        if rows:
            flash(rows, f"pc-{t}")
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
    opts = [t for t in TOPICS if cnt.get(t)] + (["未分類"] if cnt.get(None) else [])
    topic = st.selectbox("分野", opts, format_func=lambda t: f"{t}（{cnt.get(None if t == '未分類' else t, 0)}枚）",
                         key="cards-topic")
    rows = cards.for_topic(con, None if topic == "未分類" else topic) if topic != "未分類" else \
        [r for r in cards.for_topic(con, None) if not r["topic"]]
    empty = [t for t in TOPICS if not cnt.get(t)]
    if empty:
        st.caption("公式カードのない分野: " + "、".join(empty))
    mode = st.radio("表示", ["1枚ずつ", "一覧（答えも表示）"], horizontal=True, key="cards-mode")
    if mode == "1枚ずつ":
        flash(rows, f"cp-{topic}")
    else:
        for r in rows:
            with st.container(border=True):
                show(r, True)
