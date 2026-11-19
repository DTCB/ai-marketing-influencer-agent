from __future__ import annotations

import json
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import pandas as pd

from .analytics import (
    DEFAULT_CPA_TARGET,
    DEFAULT_SAVE_RATE_TARGET,
    build_campaign_review,
    evaluate_review_goals,
    summarize_metrics,
)
from .brief_parsing import EXAMPLE_SENTENCE
from .prompt_templates import format_creator_evidence, generate_cooperation_card
from .recommender import CampaignPlan, load_creators, recommend_campaign_plan


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CREATOR_COLUMNS = [
    "creator_id", "creator_name", "content_style", "base_quote", "avg_views",
    "risk_note", "sample_post_title",
]
REVIEW_COLUMNS = [
    "creator_id", "creator_name", "received", "base_quote", "spend", "impressions",
    "clicks", "saves", "revenue", "conversions", "cpa", "roi",
]


class CampaignConditions(TypedDict):
    budget_total: int
    expected_creator_count: int
    excluded_creator_ids: list[str]
    save_rate_target: float
    cpa_target: float


@lru_cache(maxsize=1)
def default_case() -> dict:
    return pd.read_csv(DATA_DIR / "campaign_cases.csv").iloc[0].to_dict()


@lru_cache(maxsize=1)
def creator_pool() -> pd.DataFrame:
    case = default_case()
    creators = load_creators(DATA_DIR / "creators.csv")
    return creators.loc[creators["platform"] == case["preferred_platform"]]


@lru_cache(maxsize=1)
def review_data() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "review_metrics.csv")


def default_conditions() -> CampaignConditions:
    case = default_case()
    return {
        "budget_total": case["budget_total"],
        "expected_creator_count": case["expected_creator_count"],
        "excluded_creator_ids": [],
        "save_rate_target": DEFAULT_SAVE_RATE_TARGET,
        "cpa_target": DEFAULT_CPA_TARGET,
    }


def default_brief_example() -> dict:
    conditions = default_conditions()
    return {
        "sentence": EXAMPLE_SENTENCE,
        "budget": conditions["budget_total"],
        "count": conditions["expected_creator_count"],
        "tone": "gentle",
        "uncertainties": [],
    }


def records(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
    # pandas emits null for missing values, including unavailable review metrics.
    return json.loads(frame[columns].to_json(orient="records", force_ascii=False))


def creator_records(frame: pd.DataFrame) -> list[dict]:
    if "total_score" not in frame:
        return records(frame, CREATOR_COLUMNS)

    rows = records(frame, CREATOR_COLUMNS + ["total_score", "matched_category_tags", "matched_audience_tags"])
    for row in rows:
        row["evidence"] = format_creator_evidence(row)
    return rows


def _plan_snapshot(conditions: CampaignConditions) -> tuple[dict, CampaignPlan, dict]:
    conditions = dict(conditions, excluded_creator_ids=sorted(set(conditions["excluded_creator_ids"])))
    brief = dict(default_case(), **conditions)
    creators = creator_pool()
    original = recommend_campaign_plan(creators, brief)
    if conditions["excluded_creator_ids"]:
        filtered = creators.loc[~creators["creator_id"].isin(conditions["excluded_creator_ids"])]
        plan = recommend_campaign_plan(filtered, brief)
        comparison, comparison_quote = original.selected, original.selected_quote
    else:
        plan = original
        comparison, comparison_quote = plan.baseline, plan.baseline_quote

    selected = plan.selected
    removed = comparison.loc[~comparison["creator_id"].isin(selected["creator_id"])]
    added = selected.loc[~selected["creator_id"].isin(comparison["creator_id"])]
    budget_gap = None
    if selected.empty and plan.minimum_quote is not None:
        budget_gap = max(0, plan.minimum_quote - conditions["budget_total"])
    payload = {
        "conditions": conditions,
        "baseline": creator_records(plan.baseline),
        "selected": creator_records(selected),
        "candidate_count": plan.candidate_count,
        "minimum_quote": plan.minimum_quote,
        "baseline_quote": plan.baseline_quote,
        "selected_quote": plan.selected_quote,
        "budget_gap": budget_gap,
        "removed": creator_records(removed),
        "added": creator_records(added),
        "comparison_quote": comparison_quote,
        "comparison_score": round(float(comparison["total_score"].sum()), 2),
        "selected_score": round(float(selected["total_score"].sum()), 2),
    }
    return payload, plan, brief


def build_web_plan(conditions: CampaignConditions) -> dict:
    payload, _, _ = _plan_snapshot(conditions)
    return payload


def build_web_campaign(conditions: CampaignConditions) -> dict | None:
    payload, plan, brief = _plan_snapshot(conditions)
    if plan.selected.empty:
        return None

    briefs = {
        creator["creator_id"]: generate_cooperation_card(brief, creator)
        for creator in plan.selected.to_dict("records")
    }
    review = build_campaign_review(review_data(), brief["case_id"], plan.selected)
    received = review.loc[review["received"]]
    save_rate, cpa = evaluate_review_goals(review, brief["save_rate_target"], brief["cpa_target"])
    ranked = received.dropna(subset=["cpa"]).sort_values(["cpa", "creator_id"]).head(1)
    candidates = records(ranked, REVIEW_COLUMNS)
    return {
        "plan": payload,
        "briefs": briefs,
        "review": {
            "rows": records(review, REVIEW_COLUMNS),
            "received_count": len(received),
            "summary": summarize_metrics(received),
            "save_rate": asdict(save_rate),
            "cpa": asdict(cpa),
            "next_candidate": candidates[0] if candidates else None,
        },
    }


def build_demo_snapshot() -> dict:
    conditions = default_conditions()
    campaign = build_web_campaign(conditions)
    if campaign is None:
        raise ValueError("Default case must produce a feasible campaign")
    return {
        "case": default_case(),
        "conditions": conditions,
        "creators": creator_records(creator_pool()),
        "plan": campaign["plan"],
        "campaign": campaign,
        "brief_example": default_brief_example(),
    }
