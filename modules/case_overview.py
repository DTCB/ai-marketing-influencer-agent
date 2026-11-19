from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from .analytics import build_campaign_review
from .prompt_templates import generate_cooperation_card
from .recommender import recommend_campaign_plan
from .review_goals import render_review_goals


def render_case_overview(
    brief: dict,
    creators: pd.DataFrame,
    review_data: pd.DataFrame,
    on_return: Callable[[], None],
) -> None:
    """Show the default campaign from fixtures without editing the working plan."""
    heading, action = st.columns([3, 2], vertical_alignment="center")
    heading.subheader("完整案例")
    action.button("试着调整方案", on_click=on_return, type="primary", key="case_overview_return")

    plan = recommend_campaign_plan(creators, brief)
    if plan.selected.empty:
        st.warning("当前样例条件下暂无可确认的达人组合。")
        return

    with st.container(border=True):
        budget = brief["budget_total"]
        st.markdown(f"### 在 ¥{budget:,.0f} 内选 {len(plan.selected)} 位达人")
        baseline_metric, plan_metric = st.columns(2)
        baseline_metric.metric("按综合分直接选", f"¥{plan.baseline_quote:,.0f}")
        plan_metric.metric("预算内名单", f"¥{plan.selected_quote:,.0f}")

        removed = plan.baseline.loc[~plan.baseline["creator_id"].isin(plan.selected["creator_id"])]
        added = plan.selected.loc[~plan.selected["creator_id"].isin(plan.baseline["creator_id"])]
        if len(removed) == len(added) == 1:
            outgoing, incoming = removed.iloc[0], added.iloc[0]
            st.write(
                f"由 **{incoming['creator_name']}** 替换 **{outgoing['creator_name']}**，"
                f"总报价少 ¥{plan.baseline_quote - plan.selected_quote:,.0f}。"
                f"替换席位的样例历史均播由 {outgoing['avg_views'] / 10_000:g} 万"
                f"调整为 {incoming['avg_views'] / 10_000:g} 万。"
            )
        st.caption("推荐名单　" + "、".join(plan.selected["creator_name"]))

    with st.container(border=True):
        st.markdown("### 按达人内容风格写合作 Brief")
        comparisons = plan.selected.loc[plan.selected["creator_id"].isin(["C001", "C002"])]
        if comparisons.empty:
            comparisons = plan.selected.head(2)
        for column, creator in zip(st.columns(len(comparisons)), comparisons.to_dict("records")):
            card = generate_cooperation_card(brief, creator)
            column.markdown(f"**{creator['creator_name']} · {creator['content_style']}**")
            column.caption(card["title"])
            column.write(card["delivery"])
            with column.expander("查看审稿要点"):
                st.write(card["review_notes"])

    review = build_campaign_review(review_data, brief["case_id"], plan.selected)
    with st.container(border=True):
        st.markdown("### 用模拟数据判断是否复投")
        received = review.loc[review["received"]]
        st.caption(f"{len(received)}/{len(review)} 位已回收")
        render_review_goals(review, brief["save_rate_target"], brief["cpa_target"])
        ranked = received.dropna(subset=["cpa"]).sort_values(["cpa", "creator_id"])
        if not ranked.empty:
            candidate = ranked.iloc[0]
            st.write(
                f"将 **{candidate['creator_name']}** 列为复投候选。"
                f"其模拟单次转化成本为 **¥{candidate['cpa']:,.2f}**，"
                "在本次已回收且可计算该指标的达人中最低。"
            )
        pending_names = "、".join(review.loc[~review["received"], "creator_name"])
        if pending_names:
            st.caption(f"待回收达人　{pending_names}")
