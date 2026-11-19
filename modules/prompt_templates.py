from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from .scoring import parse_tags


def format_creator_evidence(creator: Dict[str, Any]) -> str:
    category_tags = parse_tags(creator.get("matched_category_tags"))
    audience_tags = parse_tags(creator.get("matched_audience_tags"))
    evidence = []
    if category_tags:
        evidence.append(f"品类匹配 {'、'.join(category_tags)}")
    if audience_tags:
        evidence.append(f"受众标签匹配 {'、'.join(audience_tags)}")
    return "。".join(evidence) if evidence else "暂无直接匹配的标签，合作前核对内容与受众。"


def generate_cooperation_card(brief: Dict[str, Any], creator: Dict[str, Any]) -> Dict[str, str]:
    product = brief["product_name"]
    style = creator["content_style"]
    review_notes = "卖点以品牌已核实的材料为准，肤感由达人按实际使用体验填写。"
    avoid = parse_tags(brief.get("avoid_categories"))
    if avoid:
        review_notes += f"审稿时避开{'、'.join(avoid)}。"

    if style == "成分测评":
        return {
            "title": f"{product}成分测评｜质地、使用顺序和肤感",
            "delivery": "交付 1 篇测评图文，包含成分信息图、取样和涂抹的近景照片，说明在晚间护肤流程中的使用顺序，记录实际肤感。",
            "review_notes": f"{review_notes}核对成分表与品牌资料，删除由单一成分推导的产品效果承诺。",
        }
    if style == "图文种草":
        return {
            "title": f"换季晚间护肤日记｜{product}怎么搭配日常步骤",
            "delivery": "交付 1 篇步骤图文，封面写明换季场景，正文按清洁、精华、保湿组织图片，在精华步骤展示用量与使用场景。",
            "review_notes": f"{review_notes}核对使用顺序和用量，删去适用于所有肤质的表述。",
        }

    return {
        "title": f"{product}使用记录｜{style}",
        "delivery": f"沿用「{style}」风格交付 1 篇笔记。开头说明使用场景，正文用实拍展示产品质地和用法，结尾整理可收藏的使用要点。",
        "review_notes": review_notes,
    }


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
