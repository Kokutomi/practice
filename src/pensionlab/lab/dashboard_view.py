"""Streamlit rendering of the dashboard."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

import os
import tempfile

from . import anki, dashboard, exam, notes
from .recommend import recommend

SERIES_1 = "#2a78d6"   # single series: one hue, no legend (the title names it)
CONF = {1: "1 自信なし", 2: "2 まあまあ", 3: "3 自信あり"}


def render(con):
    st.subheader("学習ダッシュボード")
    recs = recommend(con, n=8)
    if recs:
        st.subheader("今日のおすすめ")
        st.caption("演習画面の「状態」で「今日のおすすめ」を選ぶと、この順に出題します。")
        st.dataframe(pd.DataFrame([{"問題": f"{r['problem']['year']} {r['problem']['question_no']}",
                                    "分野": r["problem"]["topic"], "理由": r["reason"]} for r in recs]),
                     hide_index=True)
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

    hist = exam.history(con)
    if hist:
        st.subheader("本番モードの履歴")
        st.dataframe(pd.DataFrame([{"年度": h["year"], "得点": f"{h['score']} / {h['max_score']}",
                                    "解答欄": h["answered"], "所要(分)": round((h["submitted_at"] - h["started_at"]) / 60),
                                    "時間超過": "あり" if h["over_time"] else ""} for h in hist]), hide_index=True)

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
                                            "tried": "解いた問題", "available": "登録問題",
                                            "median_min": "解答時間の中央値(分)"}), hide_index=True)
        pc = dashboard.pace(con)
        if pc["median_min_per_point"] is not None:
            over = pc["median_min_per_point"] > pc["budget_min_per_point"]
            st.metric("1点あたりの解答時間（中央値）", f"{pc['median_min_per_point']} 分",
                      help=f"本番は180分で100点 → 1点あたり {pc['budget_min_per_point']} 分。演習の配点付き {pc['samples']} 回から計算。")
            st.caption(("⚠ 本番のペース（1点あたり1.8分）より遅めです。" if over else "本番のペースの範囲内です。")
                       + " 確信度の低い問題に時間をかけすぎていないか確認しましょう。")
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

    st.subheader("Anki に書き出す")
    st.caption("最新の解答が誤答、または正解でも確信度1だった欄をカードにします（問題文は公式PDFへのリンク）。")
    n = len(anki.select(con))
    if n:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "pensionlab_anki.txt")
            anki.export(con, path)
            data = open(path, "rb").read()
        st.download_button(f"復習カード {n} 枚をダウンロード（.txt）", data, "pensionlab_anki.txt", "text/plain")
    else:
        st.caption("対象の欄はまだありません。")

    st.subheader("Obsidian に書き出す")
    st.caption("解いた問題・メモのある問題を1問1ファイルの Markdown にし、分野ごとの索引ページ（[[リンク]]）を付けます。")
    if con.execute("SELECT 1 FROM attempts UNION SELECT 1 FROM notes LIMIT 1").fetchone():
        st.download_button("ノート一式をダウンロード（.zip）", notes.export_zip(con), "pensionlab_obsidian.zip",
                           "application/zip")
    else:
        st.caption("まだ書き出す内容がありません。")
