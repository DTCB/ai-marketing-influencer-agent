from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .scoring import CREATOR_REQUIRED_COLUMNS, merge_tags, score_creator, validate_creator_columns


def load_creators(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = validate_creator_columns(df)
    if missing:
        raise ValueError(f"达人数据缺少必要字段: {', '.join(missing)}")
    return df


def normalize_uploaded_creators(uploaded_file: Any) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    missing = validate_creator_columns(df)
    if missing:
        raise ValueError(f"上传 CSV 缺少必要字段: {', '.join(missing)}")
    return df


def filter_creators(
    df: pd.DataFrame,
    platform: str = "不限",
    max_quote: Optional[float] = None,
    min_engagement: float = 0.0,
) -> pd.DataFrame:
    result = df.copy()
    if platform and platform != "不限":
        result = result[result["platform"] == platform]
    if max_quote is not None:
        result = result[result["base_quote"] <= max_quote]
    if min_engagement:
        result = result[result["engagement_rate"] >= min_engagement]
    return result


def recommend_creators(df: pd.DataFrame, brief: Dict[str, Any], top_n: Optional[int] = None) -> pd.DataFrame:
    preferred_platform = brief.get("preferred_platform", "不限")
    filtered = filter_creators(
        df,
        platform=preferred_platform,
        max_quote=float(brief.get("budget_total", 0) or 0),
    )
    if filtered.empty:
        filtered = df.copy()

    scored_rows = []
    for _, row in filtered.iterrows():
        scores = score_creator(row, brief)
        item = row.to_dict()
        item.update(scores)
        item["matched_category_tags"] = "|".join(
            sorted(set(merge_tags(brief.get("product_category"), brief.get("product_keywords"))).intersection(
                set(merge_tags(row.get("category_tags"), row.get("past_brand_categories")))
            ))
        )
        item["matched_audience_tags"] = "|".join(
            sorted(set(merge_tags(brief.get("target_audience"))).intersection(set(merge_tags(row.get("audience_tags")))))
        )
        item["recommendation_summary"] = build_recommendation_summary(item, brief)
        scored_rows.append(item)

    result = pd.DataFrame(scored_rows).sort_values("total_score", ascending=False)
    count = top_n or int(brief.get("expected_creator_count", 5) or 5)
    return result.head(count).reset_index(drop=True)


def build_recommendation_summary(row: Dict[str, Any], brief: Dict[str, Any]) -> str:
    strengths = []
    if row.get("matched_category_tags"):
        strengths.append(f"品类标签命中 {row['matched_category_tags']}")
    if row.get("matched_audience_tags"):
        strengths.append(f"受众标签命中 {row['matched_audience_tags']}")
    if float(row.get("engagement_rate", 0)) >= 0.05:
        strengths.append("互动率高于样例均值")
    if float(row.get("historical_roi", 0)) >= 1.5:
        strengths.append("历史 ROI 表现稳定")
    if float(row.get("base_quote", 0)) <= float(brief.get("budget_total", 0) or 0) / max(int(brief.get("expected_creator_count", 1) or 1), 1):
        strengths.append("报价符合单人预算")
    if not strengths:
        strengths.append("综合标签和预算后具备基础投放价值")
    return "；".join(strengths)
