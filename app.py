from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from modules.analytics import build_campaign_review, summarize_metrics
from modules.brief_input import render_brief_input, reset_brief_input
from modules.case_overview import render_case_overview
from modules.llm_client import generate_with_optional_llm, get_llm_config
from modules.prompt_templates import format_creator_evidence, generate_cooperation_card
from modules.recommender import CampaignPlan, load_creators, recommend_campaign_plan
from modules.review_goals import DEFAULT_CPA_TARGET, DEFAULT_SAVE_RATE_TARGET, render_review_goals


DATA_DIR = Path(__file__).parent / "data"
ASSETS_DIR = Path(__file__).parent / "assets"
STEPS = ("选人", "合作内容", "模拟复盘")
CASE_OVERVIEW = "完整案例"


@dataclass
class ConfirmedCampaign:
    case_id: str
    budget: int
    creator_count: int
    creators: pd.DataFrame
    save_rate_target: float = DEFAULT_SAVE_RATE_TARGET
    cpa_target: float = DEFAULT_CPA_TARGET


st.set_page_config(page_title="小红书达人投放助手", layout="wide")


@st.cache_data
def load_default_case() -> dict:
    brief = pd.read_csv(DATA_DIR / "campaign_cases.csv").iloc[0].to_dict()
    return dict(brief, save_rate_target=DEFAULT_SAVE_RATE_TARGET, cpa_target=DEFAULT_CPA_TARGET)


@st.cache_data
def load_default_creators() -> pd.DataFrame:
    return load_creators(DATA_DIR / "creators.csv")


@st.cache_data
def load_review_metrics() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "review_metrics.csv")


@st.cache_data
def product_image() -> str:
    return b64encode((ASSETS_DIR / "serum.webp").read_bytes()).decode("ascii")


def money(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"¥{value:,.0f}" if value == int(value) else f"¥{value:,.2f}"


def ratio(value: float, denominator: float, format_spec: str) -> str:
    return format(value, format_spec) if denominator and pd.notna(value) else "—"


def save_rate_percent(brief: dict) -> float:
    return float(Decimal(str(brief["save_rate_target"])).scaleb(2))


def set_step(step: str) -> None:
    st.session_state.step = step


def invalidate_confirmation() -> None:
    st.session_state.confirmed = None
    st.session_state.generation_results = {}


def apply_conditions(**updates) -> None:
    brief = st.session_state.brief
    if any(brief.get(key) != value for key, value in updates.items()):
        st.session_state.brief = dict(brief, **updates)
        invalidate_confirmation()


def apply_brief_input(budget: int, creator_count: int, excluded_ids: set[str]) -> None:
    st.session_state.budget_input = budget
    st.session_state.count_input = creator_count
    apply_conditions(budget_total=budget, expected_creator_count=creator_count)
    existing = st.session_state.excluded_creators
    if not excluded_ids.issubset(existing):
        st.session_state.excluded_creators = existing | excluded_ids
        invalidate_confirmation()


def reset_case() -> None:
    default = load_default_case()
    st.session_state.budget_input = int(default["budget_total"])
    st.session_state.count_input = int(default["expected_creator_count"])
    st.session_state.save_rate_input = save_rate_percent(default)
    st.session_state.cpa_target_input = default["cpa_target"]
    apply_conditions(**default)
    reset_brief_input()
    if st.session_state.excluded_creators:
        st.session_state.excluded_creators = set()
        invalidate_confirmation()


def submit_conditions() -> None:
    save_rate = Decimal(str(st.session_state.save_rate_input)).scaleb(-2)
    apply_conditions(
        budget_total=st.session_state.budget_input,
        expected_creator_count=st.session_state.count_input,
        save_rate_target=float(save_rate),
        cpa_target=st.session_state.cpa_target_input,
    )


def toggle_excluded_creator(creator_id: str) -> None:
    st.session_state.excluded_creators ^= {creator_id}
    invalidate_confirmation()


def confirm_plan(brief: dict, plan: CampaignPlan) -> None:
    st.session_state.confirmed = ConfirmedCampaign(
        case_id=brief["case_id"],
        budget=brief["budget_total"],
        creator_count=brief["expected_creator_count"],
        creators=plan.selected.copy(),
        save_rate_target=brief["save_rate_target"],
        cpa_target=brief["cpa_target"],
    )
    st.session_state.generation_results = {}
    set_step("合作内容")


def render_conditions(brief: dict, plan: CampaignPlan, creators: pd.DataFrame, excluded: pd.DataFrame) -> None:
    st.subheader("投放 Brief")
    audience = "".join(
        f"<span>{escape(tag)}</span>" for tag in brief["target_audience"].split("|")
    )
    st.html(f'<p class="field-label">目标人群</p><div class="audience-tags">{audience}</div>')
    st.session_state.setdefault("budget_input", int(brief["budget_total"]))
    st.session_state.setdefault("count_input", int(brief["expected_creator_count"]))
    st.session_state.setdefault("save_rate_input", save_rate_percent(brief))
    st.session_state.setdefault("cpa_target_input", brief["cpa_target"])
    render_brief_input(brief, creators, st.session_state.excluded_creators, apply_brief_input)
    with st.form("campaign_conditions", border=False):
        st.number_input("总预算（元）", min_value=0, step=1000, key="budget_input")
        st.number_input("合作达人数", min_value=1, step=1, key="count_input")
        with st.expander("设定复盘目标"):
            st.caption("默认值为案例演示目标，确认名单时一并保存。")
            st.number_input(
                "收藏率目标（%）", min_value=0.0, max_value=100.0,
                step=0.1, format="%.2f", key="save_rate_input",
            )
            st.number_input(
                "单次转化成本上限（元）", min_value=0.0,
                step=1.0, format="%.2f", key="cpa_target_input",
            )
        apply, reset = st.columns(2)
        apply.form_submit_button("重新计算", on_click=submit_conditions, use_container_width=True)
        reset.form_submit_button("恢复默认", on_click=reset_case, use_container_width=True)

    with st.expander("查看完整投放需求"):
        st.write(f"**品牌提供的卖点**　{brief['key_selling_points'].replace('|', '、')}")
        st.write(f"**审稿规避项**　{brief['avoid_categories'].replace('|', '、')}")

    if not excluded.empty:
        st.markdown("**本轮暂不合作**")
        for creator in excluded.itertuples():
            st.button(
                f"恢复 {creator.creator_name} 的候选资格",
                key=f"restore_{creator.creator_id}",
                on_click=toggle_excluded_creator,
                args=(creator.creator_id,),
            )

    st.button(
        "确认名单",
        type="primary",
        disabled=plan.selected.empty,
        on_click=confirm_plan,
        args=(brief, plan),
        use_container_width=True,
    )


def render_creator_list(creators: pd.DataFrame) -> None:
    st.subheader("推荐达人名单")
    for creator in creators.to_dict("records"):
        label = f"**{creator['creator_name']}** · {creator['content_style']} · {money(creator['base_quote'])}"
        with st.expander(label):
            st.write(format_creator_evidence(creator))
            st.caption(f"样例代表作《{creator['sample_post_title']}》")
            if pd.notna(creator["risk_note"]) and creator["risk_note"]:
                st.write(f"**档案备注**　{creator['risk_note']}")
            st.button(
                "暂不合作",
                key=f"exclude_{creator['creator_id']}",
                on_click=toggle_excluded_creator,
                args=(creator["creator_id"],),
                help=f"将{creator['creator_name']}移出本轮候选并重新计算整组名单",
            )


def render_exclusion_comparison(original: CampaignPlan, adjusted: CampaignPlan) -> None:
    if original.selected.empty:
        return

    previous_ids = original.selected["creator_id"]
    current_ids = adjusted.selected["creator_id"]
    removed = original.selected.loc[~previous_ids.isin(current_ids), "creator_name"]
    added = adjusted.selected.loc[~current_ids.isin(previous_ids)]
    if removed.empty and added.empty:
        st.caption("已重新计算，当前推荐名单与调整前一致。")
        return

    previous_score = original.selected["total_score"].sum()
    current_score = adjusted.selected["total_score"].sum()
    st.info(
        f"**与排除前相比**　换出 {'、'.join(removed)}，换入 {'、'.join(added['creator_name'])}。\n\n"
        f"整组报价 **{money(original.selected_quote)} → {money(adjusted.selected_quote)}**。"
        f"综合分合计 **{previous_score:.2f} → {current_score:.2f}**。"
    )
    for creator in added.to_dict("records"):
        st.caption(f"{creator['creator_name']}补位 · {format_creator_evidence(creator)}")


def render_comparison(plan: CampaignPlan) -> None:
    baseline = plan.baseline.set_index("creator_id")
    selected = plan.selected.set_index("creator_id")
    removed = baseline.loc[~baseline.index.isin(selected.index)]
    added = selected.loc[~selected.index.isin(baseline.index)]
    if len(removed) == len(added) == 1:
        outgoing, incoming = removed.iloc[0], added.iloc[0]
        difference = outgoing["base_quote"] - incoming["base_quote"]
        quote_change = (
            f"报价少 {money(difference)}" if difference > 0 else
            f"报价多 {money(-difference)}" if difference < 0 else "报价相同"
        )
        st.html(
            f"""
            <section class="swap-card" aria-label="换人对比">
              <div class="swap-heading"><h3>为什么换人</h3><span>{quote_change}</span></div>
              <p class="swap-totals">原名单 <strong>{money(plan.baseline_quote)}</strong> →
                预算内方案 <strong>{money(plan.selected_quote)}</strong></p>
              <div class="swap-people">
                <div><small>换出</small><strong>{escape(outgoing['creator_name'])}</strong>
                  <span>{money(outgoing['base_quote'])} · 均播 {outgoing['avg_views'] / 10000:g} 万</span></div>
                <span class="swap-arrow" aria-hidden="true">→</span>
                <div><small>换入</small><strong>{escape(incoming['creator_name'])}</strong>
                  <span>{money(incoming['base_quote'])} · 均播 {incoming['avg_views'] / 10000:g} 万</span></div>
              </div>
              <p class="swap-note">均播为达人档案中的样例历史平均播放量。</p>
            </section>
            """
        )
    elif not removed.empty:
        removed_names = "、".join(removed["creator_name"])
        added_names = "、".join(added["creator_name"])
        st.info(
            f"按综合分取前 {len(baseline)} 位需 **{money(plan.baseline_quote)}**。"
            f"为满足总预算，换出 {removed_names}，换入 {added_names}。"
        )
    else:
        st.caption("按综合分取前几位的名单已符合本次预算。")


def render_budget(plan: CampaignPlan, budget: int, count: int, *, has_exclusions: bool) -> None:
    if plan.selected.empty:
        if plan.minimum_quote is None:
            title = f"当前有 {plan.candidate_count} 位候选达人"
            detail = "请减少合作人数。"
        else:
            title = f"预算还差 {money(plan.minimum_quote - budget)}"
            detail = f"{count} 位达人最低需 {money(plan.minimum_quote)}。请提高预算或减少合作人数。"
        if has_exclusions:
            detail += "也可以恢复暂不合作的达人后重新计算。"
        st.html(f'<div class="budget-conflict" role="status"><strong>{title}</strong><p>{detail}</p></div>')
        return

    usage = plan.selected_quote / budget if budget else 0
    st.html(
        f"""
        <section class="budget-card" aria-label="预算内推荐方案">
          <div class="budget-figures">
            <div class="budget-main"><span>方案报价</span><strong>{money(plan.selected_quote)}</strong></div>
            <div><span>合作达人</span><strong>{count} 位</strong></div>
            <div><span>预算剩余</span><strong>{money(budget - plan.selected_quote)}</strong></div>
          </div>
          <progress class="budget-progress" max="1" value="{usage}" aria-label="预算使用比例"></progress>
          <div class="budget-scale"><span>已使用 {usage:.1%}</span><span>预算上限 {money(budget)}</span></div>
        </section>
        """
    )


def render_selection() -> None:
    brief = st.session_state.brief
    budget = brief["budget_total"]
    count = brief["expected_creator_count"]
    creators = load_default_creators()
    excluded_mask = creators["creator_id"].isin(st.session_state.excluded_creators)
    excluded = creators.loc[excluded_mask]
    original = recommend_campaign_plan(creators, brief)
    plan = original if excluded.empty else recommend_campaign_plan(creators.loc[~excluded_mask], brief)

    with st.container(key="selection"):
        with st.container(key="selection_summary"):
            st.button("查看完整案例", on_click=set_step, args=(CASE_OVERVIEW,))
            st.subheader(f"{money(budget)} 怎么选 {count} 位达人？")
            render_budget(plan, budget, count, has_exclusions=not excluded.empty)
            if not plan.selected.empty:
                if excluded.empty:
                    render_comparison(plan)
                else:
                    render_exclusion_comparison(original, plan)
        with st.container(key="selection_brief", border=True):
            render_conditions(brief, plan, creators, excluded)
        with st.container(key="selection_list"):
            if not plan.selected.empty:
                render_creator_list(plan.selected)
            if not plan.baseline.empty:
                with st.expander(f"查看按分数排序的名单 · {money(plan.baseline_quote)}"):
                    st.caption("按品类、受众、内容效果、成本、历史转化和品牌安全六项评分排序。")
                    for row in plan.baseline.itertuples():
                        st.write(f"**{row.creator_name}** · {money(row.base_quote)} · 综合分 {row.total_score:.2f}")


def render_optional_generation(key: str, label: str, prompt: str, template: str) -> None:
    results = st.session_state.generation_results
    if get_llm_config().enabled and st.button(label, key=key):
        with st.spinner("正在生成…"):
            results[key] = generate_with_optional_llm(prompt, lambda: template)

    result = results.get(key)
    if result is None:
        st.write(template)
    elif result.used_llm:
        st.caption("AI 生成 · 基于演示数据")
        st.write(result.content)
    else:
        st.caption(f"{result.error or '生成暂不可用。'} 已使用本地模板。")
        st.write(result.content)


def render_cooperation(brief: dict, confirmed: ConfirmedCampaign) -> None:
    st.subheader("达人合作内容")
    st.caption(f"已确认 {confirmed.creator_count} 位达人 · 总预算 {money(confirmed.budget)}")
    creators = confirmed.creators.set_index("creator_id", drop=False)
    creator_id = st.selectbox(
        "选择达人",
        creators.index.tolist(),
        format_func=lambda item: creators.at[item, "creator_name"],
    )
    creator = creators.loc[creator_id].to_dict()
    card = generate_cooperation_card(brief, creator)
    evidence = format_creator_evidence(creator)
    st.markdown(f"### {creator['creator_name']}")
    st.caption(f"{creator['content_style']} · {money(creator['base_quote'])}")
    with st.container(border=True):
        st.markdown("**入选证据**")
        st.caption(f"样例代表作《{creator['sample_post_title']}》")
        render_optional_generation(
            f"reason_{creator_id}",
            "生成 AI 推荐解释",
            f"用中文给品牌运营写两句推荐解释。品牌目标：{brief['campaign_goal']}。"
            f"达人：{creator['creator_name']}。档案证据：{evidence}，内容风格：{creator['content_style']}，"
            f"基础报价：{money(creator['base_quote'])}。只使用提供的证据，避免补写受众覆盖或效果预测。",
            evidence,
        )

        st.markdown("**合作 Brief**")
        brief_key = (confirmed.case_id, creator_id)
        saved = st.session_state.brief_edits.get(brief_key, card)
        with st.form(f"brief_{confirmed.case_id}_{creator_id}", border=False):
            title = st.text_input("选题", value=saved["title"], key=f"brief_title_{creator_id}")
            delivery = st.text_area("交付要求", value=saved["delivery"], key=f"brief_delivery_{creator_id}")
            review_notes = st.text_area("审稿要点", value=saved["review_notes"], key=f"brief_review_{creator_id}")
            if st.form_submit_button("保存 Brief"):
                saved = {"title": title, "delivery": delivery, "review_notes": review_notes}
                st.session_state.brief_edits[brief_key] = saved
                st.success("已保存，复制和下载内容已更新。")

        brief_text = "\n".join(
            [
                "达人合作 Brief",
                f"{brief['brand_name']} · {brief['product_name']}",
                f"{creator['creator_name']} · {brief['preferred_platform']} · {brief['campaign_goal']}",
                "",
                f"选题\n{saved['title']}",
                f"\n交付要求\n{saved['delivery']}",
                f"\n审稿要点\n{saved['review_notes']}",
            ]
        )
        with st.expander("查看并复制 Brief"):
            st.code(brief_text, language=None, wrap_lines=True)
        st.download_button(
            "下载 Brief",
            data=brief_text,
            file_name=f"{creator['creator_name']}-合作Brief.txt",
            mime="text/plain; charset=utf-8",
            on_click="ignore",
        )
    st.button("查看模拟复盘", type="primary", on_click=set_step, args=("模拟复盘",))


def render_next_round_candidates() -> None:
    candidates = st.session_state.next_round_candidates
    if not candidates:
        return

    st.markdown("**下一轮复投候选**")
    st.caption("来源为已回收的模拟数据，候选保存在当前会话。")
    for creator_id, candidate in candidates.items():
        with st.container(border=True):
            st.write(f"**{candidate['name']}** · 单次转化成本 ¥{candidate['cpa']:,.2f}")
            st.button(
                f"移除 {candidate['name']}",
                key=f"remove_next_round_{creator_id}",
                on_click=candidates.pop,
                args=(creator_id,),
            )


def render_review(brief: dict, confirmed: ConfirmedCampaign) -> None:
    st.subheader("模拟投后复盘")
    review = build_campaign_review(load_review_metrics(), confirmed.case_id, confirmed.creators)
    received = review[review["received"]]
    coverage, spend, revenue, efficiency = st.columns(4)
    coverage.metric("数据已回收", f"{len(received)}/{confirmed.creator_count} 位")
    summary = summarize_metrics(received)
    spend.metric("已回收花费", money(summary["spend"]) if not received.empty else "—")
    revenue.metric("已回收归因收入", money(summary["revenue"]) if not received.empty else "—")
    return_ratio = ratio(summary["roi"], summary["spend"], ".2f")
    efficiency.metric("收入 ÷ 花费", f"{return_ratio} 倍" if return_ratio != "—" else "—")
    render_review_goals(review, confirmed.save_rate_target, confirmed.cpa_target)

    table = pd.DataFrame(
        {
            "达人": review["creator_name"],
            "回收状态": review["received"].map({True: "已回收", False: "待回收"}),
            "计划报价": review["base_quote"].map(money),
            "模拟花费": review["spend"].map(money),
            "转化数": review["conversions"].map(lambda value: "—" if pd.isna(value) else f"{value:,.0f}"),
            "单次转化成本": review["cpa"].map(money),
        }
    )
    st.dataframe(table, hide_index=True, use_container_width=True)
    pending_names = "、".join(review.loc[~review["received"], "creator_name"])
    if pending_names:
        st.info(f"待回收达人：{pending_names}。补齐笔记表现与转化记录后，再评估这些达人的复投机会。")
    if received.empty:
        render_next_round_candidates()
        return

    st.caption(
        f"已回收范围 · 曝光 {summary['impressions']:,.0f} · 点击 {summary['clicks']:,.0f} · "
        f"点击率 {ratio(summary['ctr'], summary['impressions'], '.2%')} · "
        f"点击后转化率 {ratio(summary['cvr'], summary['clicks'], '.2%')}"
    )
    st.markdown("**下一轮建议**")
    ranked = received.dropna(subset=["cpa"]).sort_values(["cpa", "creator_id"])
    if ranked.empty:
        recommendation = "已回收数据暂无法计算单次转化成本，先核对转化口径和数据回收进度。"
    else:
        best = ranked.iloc[0]
        recommendation = (
            f"{best['creator_name']}可进入复投候选。其模拟单次转化成本为 ¥{best['cpa']:,.2f}，"
            "在本次已回收且可计算该指标的达人中最低。"
        )
    render_optional_generation(
        "review_summary",
        "生成 AI 复盘摘要",
        f"为「{brief['product_name']}」用中文写简短的模拟投放复盘。"
        f"已回收 {len(received)}/{confirmed.creator_count} 位。"
        f"已回收范围的汇总：{summary}，其中 roi 表示归因收入除以花费。"
        f"逐达人数据：{received[['creator_name', 'spend', 'conversions', 'cpa']].to_dict('records')}。"
        "优先说明可执行的复投候选，仅使用已回收的数据，缺失数据不得当作零转化。",
        recommendation,
    )
    if not ranked.empty:
        candidates = st.session_state.next_round_candidates
        creator_id = best["creator_id"]
        if creator_id not in candidates:
            candidate = {
                "name": best["creator_name"],
                "cpa": float(best["cpa"]),
                "case_id": confirmed.case_id,
            }
            st.button(
                f"将{best['creator_name']}加入下一轮候选",
                key=f"add_next_round_{creator_id}",
                on_click=candidates.__setitem__,
                args=(creator_id, candidate),
            )

    render_next_round_candidates()


def render_project_header(brief: dict, confirmed: ConfirmedCampaign | None) -> None:
    step = st.session_state.step
    with st.container(key="project_header"):
        st.html(
            f"""
            <header class="project-identity">
              <img src="data:image/webp;base64,{product_image()}" alt="样例精华产品图" width="72" height="72">
              <div>
                <p class="product-label">小红书达人投放助手</p>
                <h1>{escape(brief['brand_name'])} · {escape(brief['product_name'])}</h1>
                <p class="project-meta">{escape(brief['preferred_platform'])} · {escape(brief['campaign_goal'])} · 演示样例</p>
              </div>
            </header>
            """
        )
        with st.container(key="project_steps"):
            for name in STEPS:
                st.button(
                    name,
                    type="primary" if name == step else "secondary",
                    disabled=confirmed is None and name != STEPS[0],
                    on_click=set_step,
                    args=(name,),
                )


def main() -> None:
    if "brief" not in st.session_state:
        st.session_state.brief = load_default_case()
        st.session_state.step = STEPS[0]
        st.session_state.confirmed = None
        st.session_state.generation_results = {}
    st.session_state.brief.setdefault("save_rate_target", DEFAULT_SAVE_RATE_TARGET)
    st.session_state.brief.setdefault("cpa_target", DEFAULT_CPA_TARGET)
    st.session_state.setdefault("excluded_creators", set())
    st.session_state.setdefault("brief_edits", {})
    st.session_state.setdefault("next_round_candidates", {})
    st.html(ASSETS_DIR / "workspace.css")
    brief = st.session_state.brief
    confirmed = st.session_state.confirmed
    render_project_header(brief, confirmed)
    step = st.session_state.step
    if step == CASE_OVERVIEW:
        render_case_overview(
            load_default_case(), load_default_creators(), load_review_metrics(), lambda: set_step(STEPS[0])
        )
    elif step == STEPS[1] and confirmed is not None:
        render_cooperation(brief, confirmed)
    elif step == STEPS[2] and confirmed is not None:
        render_review(brief, confirmed)
    else:
        render_selection()


if __name__ == "__main__":
    main()
