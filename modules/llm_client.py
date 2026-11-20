from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx

try:
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover - dependency is declared, this keeps fallback mode usable.
    dotenv_values = None


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


@dataclass
class LLMConfig:
    api_key: Optional[str]
    base_url: Optional[str]
    model: str
    provider: str
    key_source: Optional[str]
    timeout_seconds: float

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def masked_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "****"
        return f"{self.api_key[:4]}...{self.api_key[-4:]}"


@dataclass
class LLMCallResult:
    content: str
    used_llm: bool
    fallback_used: bool
    model: str
    base_url: Optional[str]
    error: Optional[str] = None


KEY_CANDIDATES = [
    ("LLM_API_KEY", "自定义 OpenAI-compatible"),
    ("OPENAI_API_KEY", "OpenAI"),
    ("DEEPSEEK_API_KEY", "DeepSeek"),
    ("DASHSCOPE_API_KEY", "通义千问 / 百炼"),
    ("ZHIPUAI_API_KEY", "智谱 GLM"),
]


def get_llm_config() -> LLMConfig:
    file_settings = dotenv_values(ENV_FILE) if dotenv_values else {}

    def setting(name: str) -> Optional[str]:
        return os.environ.get(name, file_settings.get(name))

    api_key = None
    provider = "未配置"
    key_source = None
    for env_name, env_provider in KEY_CANDIDATES:
        value = setting(env_name)
        if value:
            api_key = value
            provider = env_provider
            key_source = env_name
            break

    base_url = setting("LLM_BASE_URL") or setting("OPENAI_BASE_URL")
    model = setting("LLM_MODEL") or setting("OPENAI_MODEL") or "gpt-4o-mini"
    try:
        timeout_seconds = float(setting("LLM_TIMEOUT_SECONDS") or "20")
    except ValueError:
        timeout_seconds = 20.0

    if base_url:
        lower_base_url = base_url.lower()
        if "deepseek" in lower_base_url:
            provider = "DeepSeek"
        elif "dashscope" in lower_base_url or "aliyun" in lower_base_url:
            provider = "通义千问 / 百炼"
        elif "bigmodel" in lower_base_url or "zhipu" in lower_base_url:
            provider = "智谱 GLM"

    return LLMConfig(
        api_key=api_key,
        base_url=base_url,
        model=model,
        provider=provider,
        key_source=key_source,
        timeout_seconds=timeout_seconds,
    )


def describe_llm_failure(exc: Exception) -> str:
    status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else getattr(exc, "status_code", None)
    if status == 401:
        return "服务商拒绝了 API Key（401）。请检查当前使用的 Key。"
    if status == 403:
        return "服务商拒绝了访问（403）。请检查账号和模型权限。"
    if status == 429:
        return "服务商限制了请求（429）。请检查额度或稍后重试。"
    if isinstance(status, int):
        return f"服务商返回 HTTP {status}。请检查接口地址和模型配置，或稍后重试。"
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)) or type(exc).__name__ == "APITimeoutError":
        return "连接或等待模型响应超时，请重试。"
    if isinstance(exc, (httpx.RequestError, ConnectionError)) or type(exc).__name__ == "APIConnectionError":
        return "无法连接到模型服务，请检查网络和接口地址。"
    return "模型调用失败，请检查本地配置。"


def _generate_public_content(config: LLMConfig, prompt: str, timeout: float) -> str:
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": "你是一个懂达人投放和内容运营的营销策略助手。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 500,
    }
    if config.provider == "通义千问 / 百炼":
        thinking = os.environ.get("LLM_ENABLE_THINKING", "").strip().lower()
        if thinking in {"true", "false"}:
            payload["enable_thinking"] = thinking == "true"
    transport = httpx.HTTPTransport(
        local_address="0.0.0.0", retries=0, verify=True, trust_env=False,
    )
    # One quota reservation produces one POST, with TLS verification and no redirects or retries.
    with httpx.Client(
        transport=transport, trust_env=False, follow_redirects=False,
        timeout=httpx.Timeout(timeout, connect=min(timeout, 5)),
    ) as client:
        response = client.post(
            (config.base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        result = response.json()
    content = result["choices"][0]["message"]["content"]
    if content is not None and not isinstance(content, str):
        raise ValueError("Invalid model content type")
    return content or ""


def generate_with_optional_llm(
    prompt: str, fallback: Callable[[], str], *, public_web: bool = False
) -> LLMCallResult:
    config = get_llm_config()
    fallback_content = fallback()

    if not config.enabled:
        return LLMCallResult(
            content=fallback_content,
            used_llm=False,
            fallback_used=True,
            model=config.model,
            base_url=config.base_url,
            error="未配置 API Key，已使用本地模板生成。",
        )

    started = time.monotonic()
    timeout = min(config.timeout_seconds, 30) if config.timeout_seconds > 0 else 20
    try:
        if public_web:
            content = _generate_public_content(config, prompt, timeout)
        else:
            from openai import OpenAI

            client_kwargs = {"api_key": config.api_key, "timeout": config.timeout_seconds}
            if config.base_url:
                client_kwargs["base_url"] = config.base_url
            client = OpenAI(**client_kwargs)
            response = client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": "你是一个懂达人投放和内容运营的营销策略助手。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            content = response.choices[0].message.content
        if not content or not content.strip():
            return LLMCallResult(
                content=fallback_content,
                used_llm=False,
                fallback_used=True,
                model=config.model,
                base_url=config.base_url,
                error="模型返回了空内容，请重试。",
            )

        if public_web:
            logging.getLogger(__name__).info(
                "AI provider success transport=httpx_ipv4 elapsed=%.1fs", time.monotonic() - started,
            )
        return LLMCallResult(
            content=content,
            used_llm=True,
            fallback_used=False,
            model=config.model,
            base_url=config.base_url,
        )
    except Exception as exc:
        if public_web:
            # Exception messages can contain URLs, headers or provider payloads.
            # Convert known connection messages to fixed categories without logging them.
            chain = []
            cause = exc
            seen = set()
            category = "unknown"
            connection_errors = (
                ("address_unavailable", ("cannot assign requested address",)),
                ("dns", ("temporary failure in name resolution", "name or service not known", "getaddrinfo failed", "nodename nor servname")),
                ("tls", ("certificate verify failed", "certificate_verify_failed", "ssl handshake", "tls handshake")),
                ("refused", ("connection refused",)),
                ("network", ("network is unreachable", "network unreachable", "no route to host")),
            )
            for _ in range(8):
                if cause is None or id(cause) in seen:
                    break
                seen.add(id(cause))
                error_number = getattr(cause, "errno", None)
                chain.append((type(cause).__name__, error_number if type(error_number) is int else None))
                if error_number == 99:
                    category = "address_unavailable"
                message = str(cause).lower()
                for label, tokens in connection_errors:
                    if any(token in message for token in tokens):
                        category = label
                        break
                cause = cause.__cause__ or (None if cause.__suppress_context__ else cause.__context__)
            endpoint = {
                "https://dashscope.aliyuncs.com/compatible-mode/v1": "dashscope_beijing",
                "https://trial.cn-beijing.maas.aliyuncs.com/compatible-mode/v1": "trial_beijing",
            }.get((config.base_url or "").rstrip("/"), "other")
            logging.getLogger(__name__).warning(
                "AI provider failure transport=httpx_ipv4 elapsed=%.1fs exceptions=%s category=%s endpoint=%s timeout=%s",
                time.monotonic() - started, chain, category, endpoint, timeout,
            )
        return LLMCallResult(
            content=fallback_content,
            used_llm=False,
            fallback_used=True,
            model=config.model,
            base_url=config.base_url,
            error=describe_llm_failure(exc),
        )
