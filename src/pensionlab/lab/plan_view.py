"""Streamlit page: study plan to the exam date + .ics download."""
from __future__ import annotations

from datetime import date, time as dtime

import pandas as pd
import streamlit as st

from . import plan

KIND = {"practice": "演習", "mock": "本番演習", "review": "総復習", "exam": "本番"}
WD = "月火水木金土日"


def render(con):
    st.title("学習計画")
    left = (plan.EXAM_DATE - date.today()).days
    st.metric("本番まで", f"{left}日" if left >= 0 else "終了", help="2026年度 年金数理：12月9日(水) 10:00〜180分")
    c1, c2, c3 = st.columns(3)
    start = c1.date_input("開始日", date.today())
    wtime = c2.time_input("平日の学習開始", dtime(20, 30))
    wmin = c3.number_input("平日の学習時間（分）", 15, 240, 60, step=15)
    p = plan.build(con, start, weekday_time=wtime.strftime("%H:%M"), weekday_min=int(wmin))
    st.caption("土曜（年度が多いときは日曜も）の 10:00〜13:00 に本番と同じ時間帯で過去問を通しで解きます。"
               "本番モードで受験済みの年度は除きます。平日は弱点・未着手の分野から出題数を割り振ります。")
    st.dataframe(pd.DataFrame([{"日付": f"{e['date']:%m/%d}({WD[e['date'].weekday()]})", "種類": KIND[e["kind"]],
                                "時間": f"{e['start']}〜（{e['minutes']}分）", "内容": e["title"],
                                "メモ": e["detail"]} for e in p]), hide_index=True, height=480)
    st.download_button("カレンダーに取り込む（.ics）", plan.to_ics(p), "pensionlab_plan.ics", "text/calendar")
    st.caption("iPhone/Mac のカレンダー、Google カレンダー（設定→インポート）で読み込めます。")
