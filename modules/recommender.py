from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .scoring import merge_tags, score_creator, validate_creator_columns


@dataclass(frozen=True)
class CampaignPlan:
    baseline: pd.DataFrame
    selected: pd.DataFrame
    candidate_count: int
    minimum_quote: float | None
    baseline_quote: float
    selected_quote: float


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

    result = _score_creators(filtered, brief)
    count = top_n or int(brief.get("expected_creator_count", 5) or 5)
    return result.sort_values("total_score", ascending=False).head(count).reset_index(drop=True)


def recommend_campaign_plan(df: pd.DataFrame, brief: Dict[str, Any]) -> CampaignPlan:
    """Compare the individual ranking with the best feasible roster for the sample pool."""
    count = int(brief["expected_creator_count"])
    budget = Decimal(str(brief["budget_total"]))
    pool = filter_creators(df, platform=brief.get("preferred_platform", "不限"))
    ranked = _score_creators(pool, brief).sort_values(
        ["total_score", "creator_id"], ascending=[False, True]
    ).reset_index(drop=True)

    baseline = ranked.head(count)
    selected = ranked.head(0)
    quotes = [Decimal(str(quote)) for quote in ranked["base_quote"]]
    scores = [Decimal(str(score)) for score in ranked["total_score"]]
    creator_ids = ranked["creator_id"].tolist()
    baseline_quote = sum(quotes[:count])
    if len(ranked) < count:
        return CampaignPlan(baseline, selected, len(ranked), None, float(baseline_quote), 0.0)

    minimum_quote = sum(sorted(quotes)[:count])
    best_indices = ()
    best_key = None
    if minimum_quote <= budget:
        for indices in combinations(range(len(ranked)), count):
            quote = sum(quotes[index] for index in indices)
            if quote > budget:
                continue
            score = sum(scores[index] for index in indices)
            key = (-score, quote, tuple(sorted(creator_ids[index] for index in indices)))
            if best_key is None or key < best_key:
                best_key = key
                best_indices = indices

    return CampaignPlan(
        baseline=baseline,
        selected=ranked.iloc[list(best_indices)].reset_index(drop=True),
        candidate_count=len(ranked),
        minimum_quote=float(minimum_quote),
        baseline_quote=float(baseline_quote),
        selected_quote=float(best_key[1]) if best_key is not None else 0.0,
    )


def _score_creators(df: pd.DataFrame, brief: Dict[str, Any]) -> pd.DataFrame:
    if df.empty:
        return df.assign(
            total_score=pd.Series(dtype=float),
            matched_category_tags=pd.Series(dtype=str),
            matched_audience_tags=pd.Series(dtype=str),
            recommendation_summary=pd.Series(dtype=str),
        )
    scored_rows = []
    for _, row in df.iterrows():
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

    return pd.DataFrame(scored_rows)


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
