from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from math import isfinite
from typing import Dict

import pandas as pd


DEFAULT_SAVE_RATE_TARGET = 0.016
DEFAULT_CPA_TARGET = 40.0


@dataclass(frozen=True)
class GoalResult:
    actual: float | None
    status: str


def evaluate_review_goals(
    review: pd.DataFrame, save_rate_target: float, cpa_target: float
) -> tuple[GoalResult, GoalResult]:
    """Evaluate the save-rate and cost-per-conversion goals, in that order."""
    received = review.loc[review["received"], ["saves", "impressions", "spend", "conversions"]]
    totals = received.sum(min_count=len(received))
    partial = len(received) < len(review)
    return (
        _evaluate_goal(totals["saves"], totals["impressions"], save_rate_target, partial=partial),
        _evaluate_goal(totals["spend"], totals["conversions"], cpa_target, partial=partial, lower_is_better=True),
    )


def _evaluate_goal(
    numerator: float,
    denominator: float,
    target: float,
    *,
    partial: bool,
    lower_is_better: bool = False,
) -> GoalResult:
    if pd.isna(numerator) or pd.isna(denominator) or denominator <= 0:
        return GoalResult(None, "无法判断")
    actual = float(numerator / denominator)
    if not isfinite(actual):
        return GoalResult(None, "无法判断")
    met = actual <= target if lower_is_better else actual >= target
    status = "达标" if met else "未达标"
    return GoalResult(actual, f"暂{status}" if partial else status)


def safe_divide(numerator: float, denominator: float, *, undefined: float = 0.0) -> float:
    if pd.isna(denominator) or denominator == 0:
        return undefined
    if pd.isna(numerator):
        return float("nan")
    return round(float(numerator) / float(denominator), 4)


def enrich_review_metrics(review_df: pd.DataFrame, *, undefined: float = 0.0) -> pd.DataFrame:
    df = review_df.copy()
    divide = partial(safe_divide, undefined=undefined)
    df["ctr"] = df.apply(lambda row: divide(row["clicks"], row["impressions"]), axis=1)
    df["cvr"] = df.apply(lambda row: divide(row["conversions"], row["clicks"]), axis=1)
    df["cpm"] = df.apply(lambda row: round(divide(row["spend"], row["impressions"]) * 1000, 2), axis=1)
    df["cpc"] = df.apply(lambda row: round(divide(row["spend"], row["clicks"]), 2), axis=1)
    df["cpa"] = df.apply(lambda row: round(divide(row["spend"], row["conversions"]), 2), axis=1)
    df["roi"] = df.apply(lambda row: round(divide(row["revenue"], row["spend"]), 2), axis=1)
    df["engagement_rate_actual"] = df.apply(
        lambda row: divide(row["likes"] + row["comments"] + row["saves"] + row["shares"], row["impressions"]),
        axis=1,
    )
    df["result_tag"] = df.apply(classify_result, axis=1)
    return df


def build_campaign_review(
    review_df: pd.DataFrame, campaign_id: str, confirmed_creators: pd.DataFrame
) -> pd.DataFrame:
    """Return one row per confirmed creator, including those awaiting data."""
    confirmed = confirmed_creators[["creator_id", "creator_name", "base_quote"]]
    campaign_rows = review_df.loc[
        review_df["campaign_id"].eq(campaign_id) & review_df["creator_id"].isin(confirmed["creator_id"])
    ].drop(columns="creator_name")
    metrics = enrich_review_metrics(campaign_rows, undefined=float("nan"))
    review = confirmed.merge(metrics, how="left", on="creator_id", validate="one_to_one")
    review["received"] = review["campaign_id"].notna()
    return review


def classify_result(row: pd.Series) -> str:
    if row["roi"] >= 2 and row["cvr"] >= 0.04:
        return "高转化达人，建议复投"
    if row["impressions"] >= 150000 and row["ctr"] < 0.03:
        return "高曝光低点击，优化标题封面"
    if row["ctr"] >= 0.05 and row["cvr"] < 0.025:
        return "兴趣强但转化弱，优化卖点承接"
    if row["engagement_rate_actual"] >= 0.06 and row["roi"] < 1.2:
        return "适合种草，不宜直接追转化"
    if row["cpm"] <= 70 and row["impressions"] >= 100000:
        return "低成本曝光，可扩大投放"
    return "表现中性，继续观察"


def summarize_metrics(df: pd.DataFrame) -> Dict[str, float]:
    return {
        "spend": float(df["spend"].sum()),
        "impressions": float(df["impressions"].sum()),
        "clicks": float(df["clicks"].sum()),
        "conversions": float(df["conversions"].sum()),
        "revenue": float(df["revenue"].sum()),
        "ctr": safe_divide(df["clicks"].sum(), df["impressions"].sum()),
        "cvr": safe_divide(df["conversions"].sum(), df["clicks"].sum()),
        "roi": round(safe_divide(df["revenue"].sum(), df["spend"].sum()), 2),
    }
