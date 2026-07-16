from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pandas as pd


TAG_SEPARATOR = "|"

CREATOR_REQUIRED_COLUMNS = [
    "creator_id",
    "creator_name",
    "platform",
    "category_tags",
    "audience_tags",
    "content_style",
    "follower_count",
    "avg_views",
    "engagement_rate",
    "base_quote",
    "cpm_quote",
    "historical_conversion_rate",
    "historical_roi",
    "brand_safety_score",
    "recent_growth_rate",
    "past_brand_categories",
    "sample_post_title",
    "risk_note",
]


DEFAULT_WEIGHTS = {
    "tag_score": 0.30,
    "audience_score": 0.20,
    "performance_score": 0.20,
    "cost_score": 0.15,
    "conversion_score": 0.10,
    "safety_score": 0.05,
}

GOAL_WEIGHTS = {
    "品牌曝光": {
        "tag_score": 0.25,
        "audience_score": 0.15,
        "performance_score": 0.35,
        "cost_score": 0.15,
        "conversion_score": 0.05,
        "safety_score": 0.05,
    },
    "种草转化": {
        "tag_score": 0.30,
        "audience_score": 0.25,
        "performance_score": 0.20,
        "cost_score": 0.10,
        "conversion_score": 0.10,
        "safety_score": 0.05,
    },
    "转化": {
        "tag_score": 0.25,
        "audience_score": 0.20,
        "performance_score": 0.15,
        "cost_score": 0.15,
        "conversion_score": 0.20,
        "safety_score": 0.05,
    },
}


def parse_tags(value: Any) -> List[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).replace("，", TAG_SEPARATOR).replace(",", TAG_SEPARATOR)
    return [item.strip() for item in text.split(TAG_SEPARATOR) if item.strip()]


def merge_tags(*values: Any) -> List[str]:
    tags: List[str] = []
    for value in values:
        tags.extend(parse_tags(value))
    seen = set()
    result = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def overlap_score(target_tags: Iterable[str], creator_tags: Iterable[str]) -> float:
    targets = {tag.strip().lower() for tag in target_tags if tag.strip()}
    candidates = {tag.strip().lower() for tag in creator_tags if tag.strip()}
    if not targets:
        return 0.0
    hits = len(targets.intersection(candidates))
    return round(hits / len(targets) * 100, 2)


def bucket_score(value: float, thresholds: List[tuple[float, float]]) -> float:
    for minimum, score in thresholds:
        if value >= minimum:
            return score
    return 20.0


def engagement_score(rate: float) -> float:
    return bucket_score(rate, [(0.08, 100), (0.05, 80), (0.03, 60), (0.01, 40)])


def view_score(avg_views: float) -> float:
    return bucket_score(avg_views, [(100000, 100), (50000, 80), (20000, 60), (5000, 40)])


def roi_score(roi: float) -> float:
    return bucket_score(roi, [(2.0, 100), (1.5, 80), (1.0, 60), (0.5, 40)])


def conversion_rate_score(rate: float) -> float:
    return bucket_score(rate, [(0.05, 100), (0.03, 80), (0.015, 60), (0.005, 40)])


def get_goal_weights(campaign_goal: str) -> Dict[str, float]:
    goal = campaign_goal or ""
    if "曝光" in goal:
        return GOAL_WEIGHTS["品牌曝光"]
    if "转化" in goal and "种草" not in goal:
        return GOAL_WEIGHTS["转化"]
    if "种草" in goal or "新品" in goal:
        return GOAL_WEIGHTS["种草转化"]
    return DEFAULT_WEIGHTS


def validate_creator_columns(df: pd.DataFrame) -> List[str]:
    return [column for column in CREATOR_REQUIRED_COLUMNS if column not in df.columns]


def score_creator(row: pd.Series, brief: Dict[str, Any]) -> Dict[str, float]:
    target_category_tags = merge_tags(
        brief.get("product_category"),
        brief.get("product_keywords"),
        brief.get("key_selling_points"),
    )
    target_audience_tags = merge_tags(brief.get("target_audience"))
    creator_category_tags = merge_tags(row.get("category_tags"), row.get("past_brand_categories"))
    creator_audience_tags = merge_tags(row.get("audience_tags"))

    tag_score = overlap_score(target_category_tags, creator_category_tags)
    audience_score = overlap_score(target_audience_tags, creator_audience_tags)

    performance_score = round(
        engagement_score(float(row.get("engagement_rate", 0))) * 0.5
        + view_score(float(row.get("avg_views", 0))) * 0.5,
        2,
    )

    expected_count = max(int(brief.get("expected_creator_count", 1) or 1), 1)
    per_creator_budget = float(brief.get("budget_total", 0) or 0) / expected_count
    base_quote = max(float(row.get("base_quote", 0) or 0), 1)
    cost_score = round(min(per_creator_budget / base_quote, 1.0) * 100, 2)

    conversion_score = round(
        conversion_rate_score(float(row.get("historical_conversion_rate", 0))) * 0.6
        + roi_score(float(row.get("historical_roi", 0))) * 0.4,
        2,
    )
    safety_score = round(max(min(float(row.get("brand_safety_score", 0) or 0), 1), 0) * 100, 2)

    weights = get_goal_weights(str(brief.get("campaign_goal", "")))
    total_score = round(
        tag_score * weights["tag_score"]
        + audience_score * weights["audience_score"]
        + performance_score * weights["performance_score"]
        + cost_score * weights["cost_score"]
        + conversion_score * weights["conversion_score"]
        + safety_score * weights["safety_score"],
        2,
    )

    return {
        "tag_score": tag_score,
        "audience_score": audience_score,
        "performance_score": performance_score,
        "cost_score": cost_score,
        "conversion_score": conversion_score,
        "safety_score": safety_score,
        "total_score": total_score,
    }
