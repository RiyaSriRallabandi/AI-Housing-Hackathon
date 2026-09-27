from __future__ import annotations

import json

from collections.abc import Callable

from pydantic import BaseModel, ValidationError, field_validator

from housing_review.llm import Completer
from housing_review.schemas.analyst import AnalystAssessment, Claim
from housing_review.schemas.common import (
    STRICT_CONFIG,
    AnalystName,
    ConfidenceBasis,
    NonEmptyStr,
    Score,
    Typology,
    coerce_typology,
)
from housing_review.schemas.parse import parse_analyst_assessment

MAX_SCHEMA_RETRIES = 1


class AgentJudgment(BaseModel):
    """LLM-only slice: score and summary. Claims are attached in code."""

    model_config = STRICT_CONFIG

    typology: Typology
    score: Score
    basis: ConfidenceBasis
    summary: NonEmptyStr
    cannot_determine: list[str]

    @field_validator("typology", mode="before")
    @classmethod
    def _typology(cls, value: object) -> Typology:
        if not isinstance(value, (Typology, str)):
            raise TypeError("typology must be a string")
        return coerce_typology(value)


def failure_note(agent_label: str, claims_kept: str) -> str:
    return (
        f"{agent_label} model failed to produce valid score/summary JSON twice; "
        "numeric score is a withheld placeholder (0), not a comparative ranking. "
        f"{claims_kept}"
    )


def collect_judgments(
    generate: Completer,
    system: str,
    user: str,
    typologies: list[Typology],
    *,
    agent_label: str,
    claims_kept: str,
    check: Callable[[list[AgentJudgment]], None] | None = None,
) -> list[AgentJudgment]:
    """Retry once on schema or content-guard failure; then salvage or fallback."""
    raw = ""
    for _ in range(MAX_SCHEMA_RETRIES + 1):
        raw = generate(system, user)
        try:
            judgments = [_parse_judgment(item) for item in _parse_judgments(raw)]
            _assert_complete(judgments, typologies, agent_label)
            ordered = _order(judgments, typologies)
            if check:
                check(ordered)
        except (ValidationError, ValueError, TypeError) as exc:
            user = (
                user
                + "\n\nYour previous output failed judgment-schema validation: "
                + str(exc)
                + "\nReturn {\"judgments\": [...]} only. Each object: typology, score, "
                "basis, summary, cannot_determine. No claims. Include every typology."
            )
            continue
        return ordered
    salvaged = _salvage(raw, typologies)
    note = failure_note(agent_label, claims_kept)
    if len(salvaged) == len(typologies):
        ordered = [salvaged[item] for item in typologies]
        try:
            if check:
                check(ordered)
            return ordered
        except (ValidationError, ValueError, TypeError):
            return [_fallback(item, note) for item in typologies]
    return [salvaged.get(item) or _fallback(item, note) for item in typologies]


def _parse_judgments(raw: str) -> list:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)
    if isinstance(data, dict) and "judgments" in data:
        data = data["judgments"]
    if not isinstance(data, list):
        raise ValueError("Expected a JSON object with key judgments")
    return data


def _parse_judgment(item: object) -> AgentJudgment:
    if not isinstance(item, dict):
        raise TypeError("each judgment must be an object")
    return AgentJudgment.model_validate(item)


def _assert_complete(
    judgments: list[AgentJudgment],
    typologies: list[Typology],
    agent_label: str,
) -> None:
    got = {item.typology for item in judgments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in {agent_label} judgments: {missing}")


def _order(judgments: list[AgentJudgment], typologies: list[Typology]) -> list[AgentJudgment]:
    by_typ = {item.typology: item for item in judgments}
    return [by_typ[item] for item in typologies]


def _salvage(raw: str, typologies: list[Typology]) -> dict[Typology, AgentJudgment]:
    wanted = set(typologies)
    found: dict[Typology, AgentJudgment] = {}
    try:
        items = _parse_judgments(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return found
    for item in items:
        try:
            judgment = _parse_judgment(item)
        except (ValidationError, TypeError, ValueError):
            continue
        if judgment.typology in wanted and judgment.typology not in found:
            found[judgment.typology] = judgment
    return found


def _fallback(typology: Typology, note: str) -> AgentJudgment:
    return AgentJudgment(
        typology=typology,
        score=0,
        basis=ConfidenceBasis.estimated,
        summary=(
            "Score and narrative judgment could not be determined: the model "
            "failed to produce valid output twice."
        ),
        cannot_determine=[note],
    )


def merge_assessment(
    *,
    agent: AnalystName | str,
    site_id: str,
    judgment: AgentJudgment,
    claims: list[Claim],
    extra_gaps: list[str],
) -> AnalystAssessment:
    gaps = list(dict.fromkeys(list(extra_gaps) + list(judgment.cannot_determine)))
    return parse_analyst_assessment(
        {
            "agent": agent if isinstance(agent, str) else agent.value,
            "site_id": site_id,
            "typology": judgment.typology.value,
            "score": judgment.score,
            "basis": judgment.basis.value,
            "claims": [item.model_dump(mode="json") for item in claims],
            "cannot_determine": gaps,
            "summary": judgment.summary,
        }
    )
