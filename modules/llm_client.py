from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared, this keeps fallback mode usable.
    load_dotenv = None


if load_dotenv:
    load_dotenv()


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
    api_key = None
    provider = "未配置"
    key_source = None
    for env_name, env_provider in KEY_CANDIDATES:
        value = os.getenv(env_name)
        if value:
            api_key = value
            provider = env_provider
            key_source = env_name
            break

    base_url = os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))

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


def generate_with_optional_llm(prompt: str, fallback: Callable[[], str]) -> LLMCallResult:
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

    try:
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
        if not content:
            return LLMCallResult(
                content=fallback_content,
                used_llm=False,
                fallback_used=True,
                model=config.model,
                base_url=config.base_url,
                error="模型返回内容为空，已使用本地模板生成。",
            )

        return LLMCallResult(
            content=content,
            used_llm=True,
            fallback_used=False,
            model=config.model,
            base_url=config.base_url,
        )
    except Exception as exc:
        return LLMCallResult(
            content=fallback_content,
            used_llm=False,
            fallback_used=True,
            model=config.model,
            base_url=config.base_url,
            error=f"{type(exc).__name__}: {exc}",
        )
