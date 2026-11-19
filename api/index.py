from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from modules.brief_parsing import MAX_EXACT_INTEGER, build_brief_prompt, parse_brief_response
from modules.llm_client import generate_with_optional_llm
from modules.web_campaign import (
    CampaignConditions,
    build_web_campaign,
    build_web_plan,
    creator_pool,
    default_brief_example,
    default_case,
    default_conditions,
)
from modules.web_quota import ai_available, reserve_ai_quota


app = FastAPI(title="小红书达人投放助手")


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_total: int = Field(
        default_factory=lambda: default_conditions()["budget_total"], strict=True, ge=0, le=MAX_EXACT_INTEGER
    )
    expected_creator_count: int = Field(
        default_factory=lambda: default_conditions()["expected_creator_count"], strict=True, ge=1, le=MAX_EXACT_INTEGER
    )
    excluded_creator_ids: list[str] = Field(default_factory=list, max_length=50)
    save_rate_target: float = Field(
        default_factory=lambda: default_conditions()["save_rate_target"], strict=True, ge=0, le=1
    )
    cpa_target: float = Field(
        default_factory=lambda: default_conditions()["cpa_target"], strict=True, ge=0, le=MAX_EXACT_INTEGER
    )

    def conditions(self) -> CampaignConditions:
        known_ids = set(creator_pool()["creator_id"])
        if set(self.excluded_creator_ids) - known_ids:
            raise HTTPException(422, "排除名单包含未知达人。")
        return {
            "budget_total": self.budget_total,
            "expected_creator_count": self.expected_creator_count,
            "excluded_creator_ids": sorted(set(self.excluded_creator_ids)),
            "save_rate_target": self.save_rate_target,
            "cpa_target": self.cpa_target,
        }


class AIBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: Literal["brief", "recommendation", "review"]
    sentence: str | None = Field(default=None, max_length=600)
    creator_id: str | None = Field(default=None, max_length=32)
    conditions: PlanBody | None = None


@app.get("/api/status")
def status() -> JSONResponse:
    available = ai_available()
    return JSONResponse(
        {
            "mode": "live" if available else "demo",
            "ai_available": available,
            "commit_sha": os.getenv("VERCEL_GIT_COMMIT_SHA") or None,
            "region": os.getenv("VERCEL_REGION") or None,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/plan")
def plan(body: PlanBody) -> dict:
    return build_web_plan(body.conditions())


def _require_campaign(conditions: CampaignConditions) -> dict:
    result = build_web_campaign(conditions)
    if result is None:
        raise HTTPException(409, "当前条件下没有可确认的达人组合，请调整预算或人数。")
    return result


@app.post("/api/campaign")
def campaign(body: PlanBody) -> dict:
    return _require_campaign(body.conditions())


def _review_fallback(review: dict) -> str:
    candidate = review["next_candidate"]
    if candidate is None:
        return "已回收数据暂无法计算单次转化成本，请先核对转化口径和数据回收进度。"
    return (
        f"{candidate['creator_name']}可进入复投候选。"
        f"其模拟单次转化成本为 ¥{candidate['cpa']:,.2f}，"
        "在本次已回收且可计算该指标的达人中最低。"
    )


def _ai_prompt(body: AIBody) -> tuple[str, dict]:
    if body.task == "brief":
        sentence = (body.sentence or "").strip()
        if not sentence:
            raise HTTPException(422, "请先填写一句话 Brief。")
        example = default_brief_example()
        if sentence == example.pop("sentence"):
            return build_brief_prompt(sentence), {"parsed": example}
        return build_brief_prompt(sentence), {}

    conditions = (body.conditions or PlanBody()).conditions()
    confirmed = _require_campaign(conditions)
    case = default_case()
    if body.task == "recommendation":
        creator = next(
            (item for item in confirmed["plan"]["selected"] if item["creator_id"] == body.creator_id), None
        )
        if creator is None:
            raise HTTPException(422, "请选择本次名单中的达人。")
        prompt = (
            f"用中文为{case['product_name']}投放写一段不超过 180 字的达人推荐解释。"
            f"仅依据已确认的样例档案和投放目标：{case['campaign_goal']}。"
            f"达人档案：{json.dumps(creator, ensure_ascii=False)}。"
            "说明合作适配点及档案已经记录的取舍。不要编造观看人数、评价或投放成果。"
        )
        return prompt, {"content": creator["evidence"]}

    review = confirmed["review"]
    prompt = (
        f"用中文为{case['product_name']}写不超过 180 字的模拟投后复盘。"
        f"数据与目标：{json.dumps(review, ensure_ascii=False)}。"
        "引用实际已回收的收藏率、单次转化成本与回收进度，给出下一步动作。"
        "待回收数据不能按零转化处理。所有结果属于模拟样例，不代表实际投放。"
    )
    return prompt, {"content": _review_fallback(review)}


@app.post("/api/ai")
def ai(body: AIBody, request: Request) -> JSONResponse:
    prompt, fallback = _ai_prompt(body)
    decision = reserve_ai_quota(request.headers.get("x-vercel-forwarded-for"))
    headers = {"Cache-Control": "no-store"}
    if not decision.allowed:
        if decision.retry_after is not None:
            headers["Retry-After"] = str(decision.retry_after)
        return JSONResponse(
            {"mode": "demo", "message": decision.message, "code": decision.code, **fallback},
            status_code=decision.status_code,
            headers=headers,
        )

    result = generate_with_optional_llm(prompt, lambda: fallback.get("content", ""), public_web=True)
    if result.used_llm and body.task == "brief":
        try:
            parsed = parse_brief_response(result.content)
        except ValueError:
            return JSONResponse(
                {"mode": "demo", "message": "模型返回格式异常。可手动填写，或载入内置示例。", **fallback},
                headers=headers,
            )
        return JSONResponse({"mode": "live", "parsed": asdict(parsed)}, headers=headers)
    if result.used_llm:
        return JSONResponse({"mode": "live", "content": result.content}, headers=headers)
    return JSONResponse(
        {"mode": "demo", "message": "实时模型暂不可用，可继续使用内置示例和模板。", **fallback},
        headers=headers,
    )
