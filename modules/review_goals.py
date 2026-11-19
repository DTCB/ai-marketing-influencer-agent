from __future__ import annotations

import pandas as pd
import streamlit as st

from .analytics import DEFAULT_CPA_TARGET, DEFAULT_SAVE_RATE_TARGET, evaluate_review_goals


def render_review_goals(review: pd.DataFrame, save_rate_target: float, cpa_target: float) -> None:
    save_rate, cpa = evaluate_review_goals(review, save_rate_target, cpa_target)
    title = "案例演示目标" if (save_rate_target, cpa_target) == (DEFAULT_SAVE_RATE_TARGET, DEFAULT_CPA_TARGET) else "投放目标"
    st.markdown(f"**{title}**")
    save_column, cpa_column = st.columns(2)
    with save_column.container(border=True):
        st.metric(
            "收藏率",
            "—" if save_rate.actual is None else f"{save_rate.actual:.2%}",
            help="已回收数据的总收藏 ÷ 总曝光。按未舍入的汇总值判断。",
        )
        st.caption(f"目标 ≥ {save_rate_target:.2%} · **{save_rate.status}**")
    with cpa_column.container(border=True):
        st.metric(
            "单次转化成本",
            "—" if cpa.actual is None else f"¥{cpa.actual:,.2f}",
            help="已回收数据的总花费 ÷ 总转化。按未舍入的汇总值判断。",
        )
        formatted_target = f"{cpa_target:,.2f}".rstrip("0").rstrip(".")
        st.caption(f"目标 ≤ ¥{formatted_target} · **{cpa.status}**")
