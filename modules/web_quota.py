from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DAILY_IP_LIMIT = 3
MONTHLY_SITE_LIMIT = 200
QUOTA_NAMESPACE = "influencer-campaign:production:ai"


# Both counters are checked and updated by one script so separate Vercel instances
# share the same allowance. A denied request leaves both counters untouched.
RESERVE_SCRIPT = """
local daily_count = tonumber(redis.call("GET", KEYS[1]) or "0")
local monthly_count = tonumber(redis.call("GET", KEYS[2]) or "0")
if monthly_count >= tonumber(ARGV[2]) then
    return 2
end
if daily_count >= tonumber(ARGV[1]) then
    return 1
end
redis.call("INCR", KEYS[1])
redis.call("EXPIREAT", KEYS[1], ARGV[3])
redis.call("INCR", KEYS[2])
redis.call("EXPIREAT", KEYS[2], ARGV[4])
return 0
"""


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    status_code: int
    code: str
    message: str
    retry_after: int | None = None


def _configured_value(name: str) -> str:
    return os.getenv(name, "").strip()


def _https_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return bool(url.scheme == "https" and url.hostname and not url.username and not url.password)
    except ValueError:
        return False


def ai_available() -> bool:
    """Report configuration readiness without reserving quota or contacting a provider."""
    return (
        os.getenv("VERCEL_ENV") == "production"
        and os.getenv("AI_BUDGET_CONFIRMED") == "1"
        and bool(_configured_value("LLM_API_KEY"))
        and _https_url(_configured_value("LLM_BASE_URL"))
        and bool(_configured_value("LLM_MODEL"))
        and _https_url(_configured_value("UPSTASH_REDIS_REST_URL"))
        and bool(_configured_value("UPSTASH_REDIS_REST_TOKEN"))
        and bool(_configured_value("QUOTA_HASH_SECRET"))
    )


def _quota_windows(now: datetime) -> tuple[datetime, datetime]:
    next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    return next_day, next_month


def _daily_identifier(client_ip: str, day: str) -> str:
    address = ipaddress.ip_address(client_ip.strip())
    if isinstance(address, ipaddress.IPv6Address):
        if address.scope_id is not None:
            raise ValueError("IPv6 zones are invalid for public client IPs")
        address = address.ipv4_mapped or address
    secret = _configured_value("QUOTA_HASH_SECRET").encode("utf-8")
    return hmac.new(secret, f"{day}:{address}".encode("ascii"), hashlib.sha256).hexdigest()


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def _redis_command(command: list[str | int]) -> object:
    request = Request(
        _configured_value("UPSTASH_REDIS_REST_URL"),
        data=json.dumps(command).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_configured_value('UPSTASH_REDIS_REST_TOKEN')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with build_opener(_NoRedirect).open(request, timeout=5) as response:
        payload = json.loads(response.read(1024))
    if not isinstance(payload, dict) or "error" in payload or "result" not in payload:
        raise ValueError("Invalid quota response")
    return payload["result"]


def _redis_reserve(command: list[str | int]) -> int:
    result = _redis_command(command)
    if type(result) is not int or result not in (0, 1, 2):
        raise ValueError("Invalid quota reservation")
    return result


def reserve_ai_quota(client_ip: str | None) -> QuotaDecision:
    """Reserve one shared AI invocation using Vercel's trusted client IP header."""
    if not ai_available():
        return QuotaDecision(False, 503, "ai_unavailable", "实时 AI 暂未开放，请使用内置示例和模板。")

    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    try:
        if not client_ip:
            raise ValueError("No client IP")
        identifier = _daily_identifier(client_ip, today)
    except ValueError:
        return QuotaDecision(False, 503, "client_ip_unavailable", "暂时无法确认 AI 访问额度，请使用内置示例和模板。")

    next_day, next_month = _quota_windows(now)
    command = [
        "EVAL", RESERVE_SCRIPT, 2,
        f"{QUOTA_NAMESPACE}:ip:{today}:{identifier}",
        f"{QUOTA_NAMESPACE}:site:{now:%Y-%m}",
        DAILY_IP_LIMIT, MONTHLY_SITE_LIMIT,
        int(next_day.timestamp()), int(next_month.timestamp()),
    ]
    try:
        result = _redis_reserve(command)
    except (HTTPException, OSError, ValueError):
        return QuotaDecision(False, 503, "quota_unavailable", "暂时无法确认 AI 访问额度，请使用内置示例和模板。")

    if result == 2:
        retry_after = max(1, int(next_month.timestamp()) - int(now.timestamp()))
        return QuotaDecision(False, 429, "monthly_limit", "本月 AI 体验额度已用完，请使用内置示例和模板。", retry_after)
    if result == 1:
        retry_after = max(1, int(next_day.timestamp()) - int(now.timestamp()))
        return QuotaDecision(False, 429, "daily_limit", "今日 AI 体验额度已用完，请使用内置示例和模板。", retry_after)
    return QuotaDecision(True, 200, "reserved", "")
