"""Run with python -m scripts.verify_redis_quota --env-file .env.production.local."""

from __future__ import annotations

import argparse
import os
from concurrent.futures import ThreadPoolExecutor
from time import time
from uuid import uuid4

from dotenv import dotenv_values

from modules.web_quota import (
    DAILY_IP_LIMIT,
    MONTHLY_SITE_LIMIT,
    QUOTA_NAMESPACE,
    RESERVE_SCRIPT,
    _https_url,
    _redis_command,
    _redis_reserve,
)


def _require(test_passed: bool, check: str) -> None:
    if not test_passed:
        raise RuntimeError(check)


def verify() -> None:
    prefix = f"{QUOTA_NAMESPACE}:verify:{uuid4().hex}"
    daily_key = f"{prefix}:single-ip"
    daily_site = f"{prefix}:daily-test-site"
    monthly_dailies = [f"{prefix}:monthly-ip-{number}" for number in (1, 2)]
    monthly_site = f"{prefix}:monthly-test-site"
    expiration = int(time()) + 300
    keys = [daily_key, daily_site, *monthly_dailies, monthly_site]

    def reserve(ip_key: str, site_key: str) -> int:
        return _redis_reserve([
            "EVAL", RESERVE_SCRIPT, 2, ip_key, site_key,
            DAILY_IP_LIMIT, MONTHLY_SITE_LIMIT, expiration, expiration,
        ])

    try:
        _require(_redis_command(["PING"]) == "PONG", "ping")
        with ThreadPoolExecutor(max_workers=8) as executor:
            requests = [executor.submit(reserve, daily_key, daily_site) for _ in range(8)]
            result = [request.result() for request in requests]
            _require(
                result.count(0) == DAILY_IP_LIMIT and result.count(1) == len(requests) - DAILY_IP_LIMIT,
                "concurrent daily limit",
            )
            for key in (daily_key, daily_site):
                _require(int(_redis_command(["GET", key])) == DAILY_IP_LIMIT, "daily/site counter agreement")

            _require(
                _redis_command(["SET", monthly_site, MONTHLY_SITE_LIMIT - 1, "EXAT", expiration]) == "OK",
                "monthly setup",
            )
            requests = [executor.submit(reserve, key, monthly_site) for key in monthly_dailies]
            _require(sorted(request.result() for request in requests) == [0, 2], "cross-IP monthly limit")
            _require(int(_redis_command(["GET", monthly_site])) == MONTHLY_SITE_LIMIT, "monthly total")
            tenant_counts = [int(_redis_command(["GET", key]) or 0) for key in monthly_dailies]
            _require(sorted(tenant_counts) == [0, 1], "denied request leaves counters unchanged")

        for key in (daily_key, daily_site, monthly_site):
            _require(0 < int(_redis_command(["TTL", key])) <= 300, "expiration")
    finally:
        try:
            _redis_command(["DEL", *keys])
        except Exception:
            print("Temporary verification keys expire within five minutes.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Upstash counters using isolated, short-lived keys.")
    parser.add_argument("--env-file", help="Private dotenv file containing the two Upstash REST settings.")
    args = parser.parse_args()
    if args.env_file:
        settings = dotenv_values(args.env_file)
        for name in ("UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
            if settings.get(name):
                os.environ[name] = settings[name]
    if not _https_url(os.getenv("UPSTASH_REDIS_REST_URL", "")) or not os.getenv("UPSTASH_REDIS_REST_TOKEN"):
        parser.error("Valid Upstash HTTPS REST URL and writable REST token are required.")

    try:
        verify()
    except Exception as error:
        print(f"Redis quota verification failed ({type(error).__name__}).")
        return 1
    print("Redis quota verification passed: concurrent daily limit, cross-IP monthly limit, and expiration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
