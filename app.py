from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd
import plotly.express as px
import streamlit as st

from modules.analytics import enrich_review_metrics, summarize_metrics
from modules.llm_client import LLMCallResult, generate_with_optional_llm, get_llm_config
from modules.prompt_templates import (
    generate_content_suggestion,
    generate_recap_summary,
    generate_recommendation_reason,
)
from modules.recommender import load_creators, normalize_uploaded_creators, recommend_creators
from modules.scoring import CREATOR_REQUIRED_COLUMNS, get_goal_weights


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"


st.set_page_config(
    page_title="AI营销 Agent：达人投放推荐工具",
    page_icon="📣",
    layout="wide",
)


@st.cache_data
def load_default_creators() -> pd.DataFrame:
    return load_creators(DATA_DIR / "creators.csv")


@st.cache_data
def load_default_case() -> Dict[str, Any]:
    case = pd.read_csv(DATA_DIR / "campaign_cases.csv").iloc[0].to_dict()
    case["budget_total"] = int(case["budget_total"])
    case["expected_creator_count"] = int(case["expected_creator_count"])
    return case


@st.cache_data
def load_review_metrics() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "review_metrics.csv")


def init_state() -> None:
    if "brief" not in st.session_state:
        st.session_state.brief = load_default_case()
    if "creators_df" not in st.session_state:
        st.session_state.creators_df = load_default_creators()
    if "recommendations" not in st.session_state:
        st.session_state.recommendations = recommend_creators(
            st.session_state.creators_df,
            st.session_state.brief,
        )
    if "selected_creator_id" not in st.session_state and not st.session_state.recommendations.empty:
        st.session_state.selected_creator_id = st.session_state.recommendations.iloc[0]["creator_id"]


def refresh_recommendations() -> None:
    st.session_state.recommendations = recommend_creators(
        st.session_state.creators_df,
        st.session_state.brief,
    )
    if not st.session_state.recommendations.empty:
        st.session_state.selected_creator_id = st.session_state.recommendations.iloc[0]["creator_id"]


def format_currency(value: float) -> str:
    return f"¥{value:,.0f}"


def brief_summary(brief: Dict[str, Any]) -> None:
    st.caption(
        f"{brief['brand_name']} / {brief['product_name']} / {brief['campaign_goal']} / "
        f"{format_currency(float(brief['budget_total']))} / {brief['preferred_platform']}"
    )


def render_llm_status() -> None:
    config = get_llm_config()
    st.sidebar.subheader("LLM API 状态")
    if config.enabled:
        st.sidebar.success("真实 LLM：已配置")
        st.sidebar.caption(f"Provider: {config.provider}")
        st.sidebar.caption(f"Model: {config.model}")
        st.sidebar.caption(f"Timeout: {config.timeout_seconds:g}s")
        if config.base_url:
            st.sidebar.caption(f"Base URL: {config.base_url}")
        if config.key_source:
            st.sidebar.caption(f"Key: {config.key_source} / {config.masked_key}")
        st.sidebar.caption("调用失败时会自动回退到本地模板。")
    else:
        st.sidebar.info("模板模式：未配置 API Key")
        st.sidebar.caption("复制 `.env.example` 为 `.env` 后填写 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 即可启用真实模型。")


def show_llm_call_status(result: LLMCallResult) -> None:
    if result.used_llm:
        st.success(f"已调用真实 LLM：{result.model}")
    elif result.fallback_used:
        st.warning(f"已使用本地模板生成。原因：{result.error}")


def page_home() -> None:
    st.title("AI营销 Agent：达人投放推荐工具")
    st.write("面向品牌达人投放场景，把投前选人、投中内容建议和投后复盘串成一个可解释的业务闭环。")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("默认案例", "美妆护肤")
    col2.metric("样例达人", len(st.session_state.creators_df))
    col3.metric("推荐方式", "可解释评分")
    col4.metric("AI 模式", "模板 + 可选 API")

    st.subheader("Agent 工作流")
    st.markdown(
        """
        ```text
        品牌目标输入 → 达人匹配推荐 → 推荐理由与内容建议 → 投放复盘分析
        ```
        """
    )

    st.subheader("第一版解决的业务问题")
    st.write(
        "品牌做达人投放时，经常遇到达人筛选效率低、推荐依据不透明、内容方向依赖经验、投后复盘不系统的问题。"
        "本 Demo 用规则评分保证推荐可解释，用 AI 文案生成辅助运营表达，用复盘指标沉淀下一轮优化建议。"
    )

    st.subheader("核心能力")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**达人标签体系**")
        st.write("基于领域标签、受众画像、内容风格、历史表现和报价构建达人池。")
    with c2:
        st.markdown("**可解释推荐排序**")
        st.write("按投放目标动态调整标签、受众、效果、成本和转化权重。")
    with c3:
        st.markdown("**投放复盘闭环**")
        st.write("用 CTR、CVR、CPA、ROI 等指标判断复投和优化方向。")


def page_brief() -> None:
    st.title("品牌投放目标输入")
    st.write("默认案例为美妆护肤新品投放，你可以直接使用，也可以调整字段观察推荐结果变化。")

    brief = st.session_state.brief.copy()
    with st.form("brief_form"):
        left, right = st.columns(2)
        with left:
            brand_name = st.text_input("品牌名称", brief["brand_name"])
            product_name = st.text_input("产品名称", brief["product_name"])
            product_category = st.selectbox(
                "产品品类",
                ["护肤", "美妆", "食品饮料", "数码3C", "母婴", "服饰", "校园生活"],
                index=0,
            )
            campaign_goal = st.selectbox(
                "投放目的",
                ["种草转化", "品牌曝光", "新品上市", "转化", "私域引流"],
                index=["种草转化", "品牌曝光", "新品上市", "转化", "私域引流"].index(brief["campaign_goal"]),
            )
            preferred_platform = st.selectbox(
                "目标平台",
                ["不限", "小红书", "抖音", "B站", "微博"],
                index=["不限", "小红书", "抖音", "B站", "微博"].index(brief["preferred_platform"]),
            )
            content_format = st.multiselect(
                "内容形式",
                ["图文", "短视频", "直播", "长视频"],
                default=str(brief["content_format"]).split("|"),
            )
        with right:
            budget_total = st.number_input("总预算", min_value=1000, max_value=500000, value=int(brief["budget_total"]), step=1000)
            expected_creator_count = st.slider("期望达人数", min_value=1, max_value=10, value=int(brief["expected_creator_count"]))
            price_range = st.selectbox("价格带", ["平价", "中端", "高端"], index=["平价", "中端", "高端"].index(brief["price_range"]))
            product_keywords = st.text_input("产品关键词，用 | 分隔", brief["product_keywords"])
            target_audience = st.text_input("目标人群，用 | 分隔", brief["target_audience"])
            key_selling_points = st.text_input("核心卖点，用 | 分隔", brief["key_selling_points"])
            avoid_categories = st.text_input("规避方向，用 | 分隔", brief["avoid_categories"])

        submitted = st.form_submit_button("保存投放目标并刷新推荐", type="primary")

    if submitted:
        st.session_state.brief = {
            "case_id": "CUSTOM",
            "brand_name": brand_name,
            "product_name": product_name,
            "product_category": product_category,
            "product_keywords": product_keywords,
            "target_audience": target_audience,
            "campaign_goal": campaign_goal,
            "budget_total": int(budget_total),
            "expected_creator_count": int(expected_creator_count),
            "preferred_platform": preferred_platform,
            "content_format": "|".join(content_format),
            "price_range": price_range,
            "key_selling_points": key_selling_points,
            "launch_stage": brief.get("launch_stage", "新品期"),
            "avoid_categories": avoid_categories,
        }
        refresh_recommendations()
        st.success("已更新投放目标，推荐结果会按新 Brief 重新排序。")

    st.subheader("当前投放任务摘要")
    st.json(st.session_state.brief)


def page_recommendations() -> None:
    st.title("达人推荐与排序")
    brief_summary(st.session_state.brief)

    uploaded = st.file_uploader("上传达人 CSV，可替换内置样例数据", type=["csv"])
    with st.expander("CSV 字段要求"):
        st.code(", ".join(CREATOR_REQUIRED_COLUMNS), language="text")
    if uploaded:
        try:
            st.session_state.creators_df = normalize_uploaded_creators(uploaded)
            refresh_recommendations()
            st.success("上传成功，已使用上传数据重新计算推荐。")
        except ValueError as exc:
            st.error(str(exc))

    col1, col2, col3 = st.columns(3)
    platform_filter = col1.selectbox("页面筛选：平台", ["不限", "小红书", "抖音", "B站", "微博"])
    min_score = col2.slider("最低推荐分", 0, 100, 0)
    min_engagement = col3.slider("最低互动率", 0.0, 0.12, 0.0, 0.005, format="%.3f")

    recommendations = recommend_creators(st.session_state.creators_df, st.session_state.brief)
    if platform_filter != "不限":
        recommendations = recommendations[recommendations["platform"] == platform_filter]
    recommendations = recommendations[
        (recommendations["total_score"] >= min_score) & (recommendations["engagement_rate"] >= min_engagement)
    ].reset_index(drop=True)
    st.session_state.recommendations = recommendations

    if recommendations.empty:
        st.warning("当前筛选条件下没有推荐结果，请放宽平台、分数或互动率限制。")
        return

    display_cols = [
        "creator_name",
        "platform",
        "category_tags",
        "audience_tags",
        "content_style",
        "follower_count",
        "engagement_rate",
        "base_quote",
        "historical_roi",
        "total_score",
        "recommendation_summary",
    ]
    st.dataframe(
        recommendations[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "engagement_rate": st.column_config.NumberColumn("互动率", format="%.2f"),
            "historical_roi": st.column_config.NumberColumn("历史 ROI", format="%.2f"),
            "base_quote": st.column_config.NumberColumn("报价", format="¥%d"),
            "total_score": st.column_config.ProgressColumn("推荐分", min_value=0, max_value=100),
        },
    )

    st.subheader("评分解释")
    selected_name = st.selectbox("选择达人查看分项得分", recommendations["creator_name"].tolist())
    selected = recommendations[recommendations["creator_name"] == selected_name].iloc[0]
    score_cols = [
        "tag_score",
        "audience_score",
        "performance_score",
        "cost_score",
        "conversion_score",
        "safety_score",
    ]
    score_df = pd.DataFrame(
        {"维度": ["标签匹配", "受众匹配", "内容效果", "成本效率", "历史转化", "品牌安全"], "分数": [selected[col] for col in score_cols]}
    )
    st.plotly_chart(px.bar(score_df, x="维度", y="分数", text="分数", range_y=[0, 100]), use_container_width=True)
    st.info(selected["recommendation_summary"])

    st.subheader("当前目标权重")
    weights = get_goal_weights(st.session_state.brief["campaign_goal"])
    st.dataframe(
        pd.DataFrame({"评分维度": list(weights.keys()), "权重": [f"{value:.0%}" for value in weights.values()]}),
        use_container_width=True,
        hide_index=True,
    )


def get_selected_creator() -> Dict[str, Any]:
    recommendations = st.session_state.recommendations
    if recommendations.empty:
        recommendations = recommend_creators(st.session_state.creators_df, st.session_state.brief)
    names = recommendations["creator_name"].tolist()
    selected_name = st.selectbox("选择达人", names)
    return recommendations[recommendations["creator_name"] == selected_name].iloc[0].to_dict()


def page_ai_content() -> None:
    st.title("AI 推荐理由与内容建议")
    brief_summary(st.session_state.brief)
    creator = get_selected_creator()

    st.subheader("推荐理由")
    reason_prompt = f"请为 {creator['creator_name']} 生成面向品牌运营的达人推荐理由。品牌 Brief: {st.session_state.brief}; 达人数据: {creator}"
    reason_result = generate_with_optional_llm(
        reason_prompt,
        lambda: generate_recommendation_reason(st.session_state.brief, creator),
    )
    show_llm_call_status(reason_result)
    st.write(reason_result.content)

    st.subheader("内容建议")
    content = generate_content_suggestion(st.session_state.brief, creator)
    c1, c2 = st.columns(2)
    c1.markdown("**标题建议**")
    c1.write(content["title"])
    c1.markdown("**内容方向**")
    c1.write(content["content_direction"])
    c2.markdown("**卖点拆解**")
    c2.write(content["selling_points"])
    c2.markdown("**风险提示**")
    c2.write(content["risk_note"])
    st.markdown("**短视频/图文脚本框架**")
    st.text(content["script"])


def page_review() -> None:
    st.title("投放复盘看板")
    brief_summary(st.session_state.brief)

    review_df = enrich_review_metrics(load_review_metrics())
    summary = summarize_metrics(review_df)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("总花费", format_currency(summary["spend"]))
    m2.metric("总曝光", f"{int(summary['impressions']):,}")
    m3.metric("点击率 CTR", f"{summary['ctr']:.2%}")
    m4.metric("转化率 CVR", f"{summary['cvr']:.2%}")
    m5.metric("整体 ROI", f"{summary['roi']:.2f}")

    st.subheader("达人表现对比")
    st.dataframe(
        review_df[
            [
                "creator_name",
                "platform",
                "spend",
                "impressions",
                "clicks",
                "conversions",
                "revenue",
                "ctr",
                "cvr",
                "cpa",
                "roi",
                "result_tag",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        column_config={
            "spend": st.column_config.NumberColumn("花费", format="¥%d"),
            "revenue": st.column_config.NumberColumn("收入", format="¥%d"),
            "ctr": st.column_config.NumberColumn("CTR", format="%.2f"),
            "cvr": st.column_config.NumberColumn("CVR", format="%.2f"),
            "cpa": st.column_config.NumberColumn("CPA", format="¥%.2f"),
            "roi": st.column_config.NumberColumn("ROI", format="%.2f"),
        },
    )

    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.bar(review_df.sort_values("roi", ascending=False), x="creator_name", y="roi", text="roi", title="达人 ROI 排名"), use_container_width=True)
    with right:
        funnel = pd.DataFrame(
            {
                "阶段": ["曝光", "点击", "转化"],
                "数量": [summary["impressions"], summary["clicks"], summary["conversions"]],
            }
        )
        st.plotly_chart(px.funnel(funnel, x="数量", y="阶段", title="投放转化漏斗"), use_container_width=True)

    st.subheader("AI 复盘摘要")
    recap_prompt = f"请根据品牌 Brief 和复盘数据生成投放复盘摘要。Brief: {st.session_state.brief}; Summary: {summary}; Data: {review_df.to_dict('records')}"
    recap_result = generate_with_optional_llm(
        recap_prompt,
        lambda: generate_recap_summary(st.session_state.brief, review_df, summary),
    )
    show_llm_call_status(recap_result)
    st.write(recap_result.content)

    with st.expander("复盘指标公式"):
        st.markdown(
            """
            - CTR = 点击量 / 曝光量
            - CVR = 转化量 / 点击量
            - CPM = 花费 / 曝光量 * 1000
            - CPC = 花费 / 点击量
            - CPA = 花费 / 转化量
            - ROI = 收入 / 花费
            """
        )


def main() -> None:
    init_state()
    st.sidebar.title("导航")
    page = st.sidebar.radio(
        "选择页面",
        ["首页", "品牌目标输入", "达人推荐与排序", "AI 推荐理由与内容建议", "投放复盘看板"],
    )
    st.sidebar.divider()
    st.sidebar.caption("内置样例数据保证首次打开即可演示；上传 CSV 是增强入口。")
    st.sidebar.divider()
    render_llm_status()

    if page == "首页":
        page_home()
    elif page == "品牌目标输入":
        page_brief()
    elif page == "达人推荐与排序":
        page_recommendations()
    elif page == "AI 推荐理由与内容建议":
        page_ai_content()
    else:
        page_review()


if __name__ == "__main__":
    main()
