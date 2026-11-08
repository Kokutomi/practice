"""Streamlit rendering of the dashboard."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from . import dashboard

SERIES_1 = "#2a78d6"   # single series: one hue, no legend (the title names it)
CONF = {1: "1 自信なし", 2: "2 まあまあ", 3: "3 自信あり"}


def render(con):
    st.title("学習ダッシュボード")
    ys = dashboard.year_scores(con)
    if not ys:
        st.info("まだ公式過去問の解答がありません。演習画面で解くとここに集計されます。")
    else:
        st.subheader("年度別の得点")
        st.caption("各解答欄の最新の解答で採点。完答問題はグループ全問正解で得点。")
        cols = st.columns(min(len(ys), 4))
        for c, y in zip(cols * (len(ys) // len(cols) + 1), ys):
            c.metric(f"{y['year']}年度", f"{y['score']} / {y['max']}点")
            c.caption(f"{y['answered']} / {y['slots']} 欄 解答済")

    acc = dashboard.topic_accuracy(con)
    st.subheader("分野別正答率（低い順）")
    if acc:
        df = pd.DataFrame(acc)
        df["label"] = df["accuracy"].map(lambda v: f"{v:g}%")
        base = alt.Chart(df).encode(
            x=alt.X("accuracy:Q", title="正答率 (%)", scale=alt.Scale(domain=[0, 110]),
                    axis=alt.Axis(values=list(range(0, 101, 20)))),
            y=alt.Y("topic:N", sort=None, title=None),
            tooltip=[alt.Tooltip("topic:N", title="分野"), alt.Tooltip("accuracy:Q", title="正答率%"),
                                  alt.Tooltip("attempts:Q", title="解答回数"), alt.Tooltip("tried:Q", title="解いた問題"),
                     alt.Tooltip("available:Q", title="登録問題")])
        bars = base.mark_bar(color=SERIES_1, cornerRadiusEnd=4, size=14)
        labels = base.mark_text(align="left", dx=4, color="#52514e").encode(text="label:N")  # text ink, not series color
        chart = ((bars + labels).properties(height=max(120, 28 * len(df)))
                 .configure_axis(grid=False, labelLimit=260))
        st.altair_chart(chart, use_container_width=True)
        with st.expander("表で見る"):
            st.dataframe(df.drop(columns="label").rename(columns={"topic": "分野", "attempts": "解答回数", "accuracy": "正答率%",
                                            "tried": "解いた問題", "available": "登録問題"}), hide_index=True)
    else:
        st.caption("まだ解答がありません")

    st.subheader("確信度 × 正誤")
    m = dashboard.confidence_matrix(con)
    c1, c2 = st.columns(2)
    c1.metric("正解だが自信なし（定着前）", m[1]["correct"])
    c2.metric("自信ありで誤答（誤解の可能性）", m[3]["wrong"])
    st.dataframe(pd.DataFrame([{"確信度": CONF[k], "正解": v["correct"], "誤答": v["wrong"]} for k, v in m.items()]),
                 hide_index=True)

    et = dashboard.error_types(con)
    if et:
        st.subheader("誤りの種類")
        st.dataframe(pd.DataFrame(et).rename(columns={"error_type": "誤りの種類", "n": "件数"}), hide_index=True)
