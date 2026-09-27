"""Central LLM settings for every in-app agent.

Agents must not store their own model strings. Swap models via env vars
or the defaults in this file only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Defaults after 2026-09-26 live checks: Gemini 2.5 Flash 404s for new keys;
# Gemini 3.8 Flash accepted the key but returned 503 (high demand) while
# AI Studio still showed 0/20 RPD. Groq free-tier docs:
# https://console.groq.com/docs/models  (id openai/gpt-oss-120b)
# https://console.groq.com/docs/rate-limits (Free table: 30 RPM, 1K RPD, 8K TPM, 200K TPD)
LLM_PROVIDER = "groq"
LLM_MODEL = "openai/gpt-oss-120b"

LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF_SECONDS = 2.0


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str | None
    max_retries: int
    retry_backoff_seconds: float


def load_llm_config() -> LLMConfig:
    provider = os.environ.get("LLM_PROVIDER", LLM_PROVIDER).strip()
    if provider == "groq":
        api_key = (os.environ.get("GROQ_API_KEY") or "").strip() or None
    else:
        api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY") or "").strip() or None
    return LLMConfig(
        provider=provider,
        model=os.environ.get("LLM_MODEL", LLM_MODEL).strip(),
        api_key=api_key,
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", LLM_MAX_RETRIES)),
        retry_backoff_seconds=float(os.environ.get("LLM_RETRY_BACKOFF_SECONDS", LLM_RETRY_BACKOFF_SECONDS)),
    )
