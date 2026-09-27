from __future__ import annotations

import json
from typing import Any

from housing_review.schemas.analyst import AnalystAssessment, AnalystAssessmentRound2
from housing_review.schemas.chair import ChairSynthesis

__all__ = [
    "parse_analyst_assessment",
    "parse_chair_synthesis",
]


def _as_mapping(payload: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Agent output must be a JSON object")
    return data


def parse_analyst_assessment(
    payload: str | bytes | dict[str, Any],
    *,
    round_2: bool = False,
) -> AnalystAssessment | AnalystAssessmentRound2:
    """Parse and reject malformed Analyst JSON. Callers should retry on ValidationError."""
    data = _as_mapping(payload)
    model = AnalystAssessmentRound2 if round_2 else AnalystAssessment
    return model.model_validate(data)


def parse_chair_synthesis(payload: str | bytes | dict[str, Any]) -> ChairSynthesis:
    return ChairSynthesis.model_validate(_as_mapping(payload))
