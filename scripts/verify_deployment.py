"""Verify a Vercel deployment. The --live flag uses three real AI requests."""

from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def request(url: str, body: dict | None = None) -> tuple[int, dict | str]:
    kwargs = {} if body is None else {
        "data": json.dumps(body).encode(),
        "headers": {"Content-Type": "application/json"},
    }
    try:
        response = urlopen(Request(url, **kwargs), timeout=50)
    except HTTPError as error:
        response = error
    with response:
        content = response.read().decode("utf-8")
        return response.status, json.loads(content) if "/api/" in url else content


def verify(base: str, expected_commit: str | None, live: bool) -> None:
    code, page = request(f"{base}/")
    assert code == 200 and isinstance(page, str) and "<html" in page, "Home page did not load"
    code, status = request(f"{base}/api/status")
    assert code == 200 and isinstance(status, dict) and status["region"] == "hkg1", "API region is not hkg1"
    if expected_commit:
        assert (status["commit_sha"] or "").startswith(expected_commit), "Unexpected deployed commit"
    assert status["ai_available"] is live, "Unexpected AI mode"
    for body, quote, gap in (
        ({}, 49_800, None),
        ({"excluded_creator_ids": ["C013"]}, 49_600, None),
        ({"budget_total": 30_000}, 0, 8_200),
    ):
        code, plan = request(f"{base}/api/plan", body)
        assert code == 200 and plan["selected_quote"] == quote and plan["budget_gap"] == gap, "Plan mismatch"
    code, campaign = request(f"{base}/api/campaign", {})
    assert code == 200 and campaign["review"]["received_count"] == 4, "Review coverage mismatch"
    assert round(campaign["review"]["save_rate"]["actual"] * 100, 2) == 1.52, "Save rate mismatch"
    assert round(campaign["review"]["cpa"]["actual"], 2) == 36.58, "CPA mismatch"
    print(f"Case, plan, review and status passed at {base} · {status['commit_sha']} · {status['region']}")
    if live:
        tasks = (
            {"task": "brief", "sentence": "预算 5 万元，找 5 位，内容温和一点。"},
            {"task": "recommendation", "creator_id": "C001", "conditions": {}},
            {"task": "review", "conditions": {}},
        )
        for task in tasks:
            code, result = request(f"{base}/api/ai", task)
            assert code == 200 and result["mode"] == "live", f"Live AI failed for {task['task']}"
        code, result = request(f"{base}/api/ai", tasks[-1])
        assert code == 429 and result["code"] == "daily_limit" and result.get("content"), "Daily quota mismatch"
        print("Three live tasks, daily 429 and template fallback passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="The Vercel deployment root URL")
    parser.add_argument("--commit", help="Expected Git SHA or prefix")
    parser.add_argument("--live", action="store_true", help="Test real AI from a network with unused daily quota")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.username or parsed.query or parsed.fragment:
        parser.error("Provide a deployment root HTTPS URL.")
    verify(base, args.commit, args.live)


if __name__ == "__main__":
    main()
