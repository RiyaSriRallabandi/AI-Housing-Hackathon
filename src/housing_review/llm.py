from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from housing_review.config import load_llm_config

JsonDict = dict[str, Any]
Completer = Callable[[str, str], str]


def complete_json(system_instruction: str, user_content: str) -> str:
    """Call the configured model and return raw JSON text. Agents do not pick the model."""
    cfg = load_llm_config()
    if cfg.provider == "groq":
        return _complete_groq(cfg, system_instruction, user_content)
    if cfg.provider == "google_gemini":
        return _complete_gemini(cfg, system_instruction, user_content)
    raise ValueError(f"Unsupported LLM_PROVIDER={cfg.provider!r}; expected groq or google_gemini")


def _complete_groq(cfg, system_instruction: str, user_content: str) -> str:
    from groq import Groq
    from groq import RateLimitError

    if not cfg.api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    client = Groq(api_key=cfg.api_key)
    last_error: Exception | None = None
    for attempt in range(cfg.max_retries):
        try:
            response = client.chat.completions.create(
                model=cfg.model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content},
                ],
            )
            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("Model returned empty text")
            return text
        except RateLimitError as exc:
            last_error = exc
            if attempt < cfg.max_retries - 1:
                time.sleep(cfg.retry_backoff_seconds * (2**attempt))
                continue
            raise
    raise RuntimeError(f"LLM call failed after retries: {last_error}")


def _complete_gemini(cfg, system_instruction: str, user_content: str) -> str:
    from google.genai import Client
    from google.genai import errors as genai_errors
    from google.genai import types

    if not cfg.api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    client = Client(api_key=cfg.api_key)
    last_error: Exception | None = None
    for attempt in range(cfg.max_retries):
        try:
            response = client.models.generate_content(
                model=cfg.model,
                contents=user_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("Model returned empty text")
            return text
        except (genai_errors.ClientError, genai_errors.ServerError) as exc:
            last_error = exc
            message = str(exc).lower()
            retryable = (
                "429" in message
                or "503" in message
                or "resource_exhausted" in message
                or "unavailable" in message
                or "high demand" in message
                or "rate" in message
            )
            if retryable and attempt < cfg.max_retries - 1:
                time.sleep(cfg.retry_backoff_seconds * (2**attempt))
                continue
            raise
    raise RuntimeError(f"LLM call failed after retries: {last_error}")


def parse_json_object(raw: str) -> JsonDict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    return data


def parse_json_list(raw: str) -> list[Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    if isinstance(data, dict) and "assessments" in data:
        data = data["assessments"]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array of assessments")
    return data
