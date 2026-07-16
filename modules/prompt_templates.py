from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def generate_recommendation_reason(brief: Dict[str, Any], creator: Dict[str, Any]) -> str:
    return (
        f"{creator['creator_name']} 适合本次「{brief['product_name']}」投放，主要因为其内容标签与"
        f"「{brief['product_category']} / {brief['product_keywords']}」高度相关，受众覆盖"
        f"「{brief['target_audience']}」。该达人互动率为 {float(creator['engagement_rate']):.1%}，"
        f"历史 ROI 为 {float(creator['historical_roi']):.2f}，报价 {int(creator['base_quote'])} 元，"
        f"综合推荐分 {float(creator['total_score']):.1f}。{creator.get('recommendation_summary', '')}。"
    )


def generate_content_suggestion(brief: Dict[str, Any], creator: Dict[str, Any]) -> Dict[str, str]:
    selling_points = brief.get("key_selling_points", "温和修护|敏感肌友好")
    style = creator.get("content_style", "种草")
    title = f"{brief['product_name']}真实体验：敏感肌也能安心用的{brief['product_category']}方案"
    script = (
        f"1. 开场痛点：用 5 秒讲清目标用户的肌肤困扰或换季不稳定问题。\n"
        f"2. 产品引入：结合「{selling_points}」说明产品核心卖点。\n"
        f"3. 达人体验：用「{style}」风格展示使用过程、肤感和场景。\n"
        f"4. 证据补充：展示成分、质地、使用前后感受或评论反馈。\n"
        f"5. 行动引导：引导收藏、评论肤质问题或进入购买/试用页面。"
    )
    risk = creator.get("risk_note", "注意避免夸大功效，内容表达保持真实体验。")
    return {
        "title": title,
        "content_direction": f"围绕「{brief['campaign_goal']}」目标，用{style}内容降低用户决策成本。",
        "script": script,
        "selling_points": selling_points,
        "risk_note": risk,
    }


def generate_recap_summary(brief: Dict[str, Any], review_df: pd.DataFrame, summary: Dict[str, float]) -> str:
    top_row = review_df.sort_values("roi", ascending=False).iloc[0]
    low_row = review_df.sort_values("roi", ascending=True).iloc[0]
    return (
        f"本次「{brief['product_name']}」投放累计曝光 {int(summary['impressions']):,}，"
        f"点击 {int(summary['clicks']):,}，转化 {int(summary['conversions']):,}，整体 ROI {summary['roi']:.2f}。"
        f"表现最好的达人是 {top_row['creator_name']}，ROI 达到 {top_row['roi']:.2f}，可作为下一轮复投对象。"
        f"{low_row['creator_name']} 的 ROI 相对较低，建议复盘其内容标题、卖点承接或落地页转化链路。"
        f"下一轮可优先增加标签匹配高、互动稳定且历史 ROI 高的测评/种草型达人。"
    )
