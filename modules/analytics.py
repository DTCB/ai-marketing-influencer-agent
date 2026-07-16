from __future__ import annotations

from typing import Dict

import pandas as pd


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator in (0, 0.0) or pd.isna(denominator):
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def enrich_review_metrics(review_df: pd.DataFrame) -> pd.DataFrame:
    df = review_df.copy()
    df["ctr"] = df.apply(lambda row: safe_divide(row["clicks"], row["impressions"]), axis=1)
    df["cvr"] = df.apply(lambda row: safe_divide(row["conversions"], row["clicks"]), axis=1)
    df["cpm"] = df.apply(lambda row: round(safe_divide(row["spend"], row["impressions"]) * 1000, 2), axis=1)
    df["cpc"] = df.apply(lambda row: round(safe_divide(row["spend"], row["clicks"]), 2), axis=1)
    df["cpa"] = df.apply(lambda row: round(safe_divide(row["spend"], row["conversions"]), 2), axis=1)
    df["roi"] = df.apply(lambda row: round(safe_divide(row["revenue"], row["spend"]), 2), axis=1)
    df["engagement_rate_actual"] = df.apply(
        lambda row: safe_divide(row["likes"] + row["comments"] + row["saves"] + row["shares"], row["impressions"]),
        axis=1,
    )
    df["result_tag"] = df.apply(classify_result, axis=1)
    return df


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
