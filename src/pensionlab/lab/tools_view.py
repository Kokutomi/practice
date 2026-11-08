"""Streamlit page: calculators (commutation table, annuity values, Trowbridge financing methods)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pensionlab import LifeTable, annuity_due, deferred_annuity_due, gompertz_makeham
from pensionlab.commutation import annuity_certain_due, guaranteed_life_annuity_due, table
from pensionlab.finance import METHODS, Trowbridge


def _mortality():
    with st.expander("死亡率（Gompertz–Makeham: μx = A + B·c^x）"):
        c1, c2, c3 = st.columns(3)
        A = c1.number_input("A", 0.0, 0.01, 0.0007, step=0.0001, format="%.4f")
        B = c2.number_input("B", 0.0, 0.001, 0.00005, step=0.00001, format="%.5f")
        c = c3.number_input("c", 1.01, 1.2, 1.10, step=0.01)
    return LifeTable(gompertz_makeham(A, B, c))


def render(con=None):
    st.title("計算ツール")
    st.caption("検算・理解用。死亡率は Gompertz–Makeham の仮定値で、試験の基数表とは異なります。")
    lt = _mortality()
    t1, t2, t3 = st.tabs(["計算基数表", "年金現価", "財政方式の比較（Trowbridge）"])

    with t1:
        c1, c2, c3 = st.columns(3)
        i = c1.number_input("予定利率", 0.0, 0.2, 0.03, step=0.005, format="%.3f", key="ci")
        lo, hi = c2.number_input("年齢 from", 0, 110, 20), c3.number_input("to", 0, 110, 70)
        df = pd.DataFrame(table(lt, i, range(int(lo), int(hi) + 1)))
        st.dataframe(df.style.format({"l_x": "{:,.1f}", "d_x": "{:,.1f}", "D_x": "{:,.2f}", "N_x": "{:,.1f}",
                                      "C_x": "{:,.3f}", "M_x": "{:,.2f}", "ä_x": "{:.4f}"}), hide_index=True)
        st.download_button("CSV で保存", df.to_csv(index=False).encode("utf-8-sig"), "commutation.csv", "text/csv")
        st.caption("D_x = vˣ l_x, N_x = Σ D, C_x = vˣ⁺¹ d_x, M_x = Σ C（= D_x − d N_x）")

    with t2:
        c1, c2, c3, c4 = st.columns(4)
        x = c1.number_input("年齢 x", 0, 110, 60)
        i2 = c2.number_input("利率", 0.0, 0.2, 0.03, step=0.005, format="%.3f", key="ai")
        n = c3.number_input("年数 n（確定・保証・据置）", 0, 60, 10)
        m = c4.selectbox("年間支払回数 m（確定年金）", [1, 2, 4, 6, 12], index=0)
        rows = [("ä_x（終身・期初）", annuity_due(lt, int(x), i2)),
                ("a_x（終身・期末）", annuity_due(lt, int(x), i2) - 1),
                (f"{n}|ä_x（{n}年据置）", deferred_annuity_due(lt, int(x), int(n), i2)),
                (f"ä⁽{m}⁾_{n}|（{n}年確定・年額1）", annuity_certain_due(int(n), i2, int(m))),
                (f"{n}年保証期間付終身年金（期初）", guaranteed_life_annuity_due(lt, int(x), int(n), i2))]
        st.dataframe(pd.DataFrame(rows, columns=["年金現価", "値"]).style.format({"値": "{:.5f}"}), hide_index=True)
        st.caption("確定年金を「月額1」で考える問題は、上の値 × 12。")

    with t3:
        c1, c2, c3 = st.columns(3)
        xe = c1.number_input("加入年齢 xe", 15, 50, 20)
        xr = c2.number_input("定年 xr", 50, 75, 60)
        i3 = c3.number_input("予定利率", 0.001, 0.2, 0.03, step=0.005, format="%.3f", key="ti")
        try:
            m3 = Trowbridge(lt, int(xe), int(xr), i3)
        except ValueError as e:
            st.error(str(e))
            return
        df = pd.DataFrame([{"財政方式": name, "保険料 C": m3.contribution(k), "積立金 F": m3.fund(k),
                            "F / B": m3.fund(k) / m3.B} for k, name in METHODS.items()])
        st.dataframe(df.style.format({"保険料 C": "{:,.1f}", "積立金 F": "{:,.0f}", "F / B": "{:.2f}"}), hide_index=True)
        st.caption(f"給付 B = {m3.B:,.1f}（年金受給者数）、在職者数 L = {m3.L:,.1f}。"
                   "前提：保険料・給付とも期初払い、F は期初（収支前）の積立金、定常状態の収支相等 C + dF = B。"
                   "F の大小：賦課 < 退職時年金現価 < 単位 < 平準 < 加入時 を確認できます。")
