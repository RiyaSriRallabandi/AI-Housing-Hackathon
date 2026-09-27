from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator

from housing_review.llm import Completer, complete_json, parse_json_object
from housing_review.schemas.chair import (
    RESPONSIBLE_USE_NOTE,
    ChairSynthesis,
    FactualDispute,
    Limitation,
    TypologyComparison,
    ValueDispute,
)
from housing_review.schemas.common import STRICT_CONFIG, AnalystName, Typology, coerce_typology
from housing_review.schemas.debate import AGENT_ORDER, Round1Transcript
from housing_review.schemas.parse import parse_chair_synthesis

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "chair.txt"
MAX_SCHEMA_RETRIES = 1
SHARP_SPREAD = 4
LIMITATION_NEXT_STEP = (
    "Not resolved in this tool. Verify with the relevant office before acting."
)


class ChairTypologyJudgment(BaseModel):
    """LLM-only slice. Scores and limitations are attached in code."""

    model_config = STRICT_CONFIG

    typology: Typology
    factual_disputes: list[FactualDispute]
    value_disputes: list[ValueDispute]

    @field_validator("typology", mode="before")
    @classmethod
    def _typology(cls, value: object) -> Typology:
        if not isinstance(value, (Typology, str)):
            raise TypeError("typology must be a string")
        return coerce_typology(value)


def compact_round1_for_chair(transcript: Round1Transcript) -> dict:
    by_agent = transcript.by_agent()
    rows = []
    for typology in transcript.typologies():
        agents = {}
        scores = []
        for name in transcript.agents_in_order:
            item = next(x for x in by_agent[name] if x.typology is typology)
            scores.append(item.score)
            agents[name.value] = {
                "score": item.score,
                "basis": item.basis.value,
                "summary": item.summary,
                "claim_statements": [claim.statement for claim in item.claims[:2]],
            }
        spread = max(scores) - min(scores) if scores else 0
        rows.append(
            {
                "typology": typology.value,
                "scores_by_agent": {name.value: score for name, score in zip(transcript.agents_in_order, scores, strict=True)},
                "score_spread": spread,
                "sharp_divergence": spread >= SHARP_SPREAD,
                "agents": agents,
            }
        )
    return {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_id": transcript.site_id,
        "candidate_typologies": [item.value for item in transcript.typologies()],
        "round_1": rows,
    }


def compile_limitations(transcript: Round1Transcript) -> list[Limitation]:
    seen: set[tuple[str, str]] = set()
    out: list[Limitation] = []
    for item in transcript.assessments:
        for note in item.cannot_determine:
            question = note.strip()
            if not question:
                continue
            key = (item.agent.value, question)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Limitation(
                    question=question,
                    raised_by=item.agent,
                    next_step=LIMITATION_NEXT_STEP,
                )
            )
    return out


def scores_by_agent_for(transcript: Round1Transcript, typology: Typology) -> dict[AnalystName, int]:
    by_agent = transcript.by_agent()
    return {
        name: next(x.score for x in by_agent[name] if x.typology is typology)
        for name in transcript.agents_in_order
    }


def run_chair(
    transcript: Round1Transcript,
    *,
    completer: Completer | None = None,
) -> ChairSynthesis:
    """Chair reads independent Round 1 only. Scores and limitations are code-owned."""
    generate = completer or complete_json
    typologies = transcript.typologies()
    payload = compact_round1_for_chair(transcript)
    system = PROMPT_PATH.read_text()
    user = (
        "Classify factual vs value disputes for EVERY typology. Do not emit scores "
        "or a winner. Return JSON as {\"typology_comparison\": [...]}.\n"
        + json.dumps(payload)
    )
    raw = ""
    for _ in range(MAX_SCHEMA_RETRIES + 1):
        raw = generate(system, user)
        try:
            judgments = _parse_judgments(raw, typologies)
            return _merge(transcript, judgments)
        except (ValidationError, ValueError, TypeError) as exc:
            user = (
                user
                + "\n\nYour previous output failed Chair-schema validation: "
                + str(exc)
                + '\nReturn {"typology_comparison": [...]} only. Each object: typology, '
                "factual_disputes, value_disputes. No scores. No winner. Include every typology."
            )
            continue
    salvaged = _salvage(raw, typologies)
    judgments = [salvaged.get(item) or _empty_judgment(item) for item in typologies]
    return _merge(transcript, judgments)


def _parse_judgments(raw: str, typologies: list[Typology]) -> list[ChairTypologyJudgment]:
    data = parse_json_object(raw)
    if "winner" in data or "preferred_typology" in data:
        raise ValueError("Chair must not emit a winner typology")
    items = data.get("typology_comparison")
    if not isinstance(items, list):
        raise ValueError("Expected typology_comparison list")
    judgments = [_parse_one(item) for item in items]
    got = {item.typology for item in judgments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in Chair output: {missing}")
    by_typ = {item.typology: item for item in judgments}
    return [by_typ[item] for item in typologies]


def _parse_one(item: object) -> ChairTypologyJudgment:
    if not isinstance(item, dict):
        raise TypeError("each typology_comparison entry must be an object")
    if "scores_by_agent" in item:
        raise ValueError("Chair must not emit scores_by_agent; scores are attached in code")
    return ChairTypologyJudgment.model_validate(item)


def _salvage(raw: str, typologies: list[Typology]) -> dict[Typology, ChairTypologyJudgment]:
    wanted = set(typologies)
    found: dict[Typology, ChairTypologyJudgment] = {}
    try:
        data = parse_json_object(raw)
        items = data.get("typology_comparison")
        if not isinstance(items, list):
            return found
    except (json.JSONDecodeError, ValueError, TypeError):
        return found
    for item in items:
        try:
            judgment = _parse_one(item)
        except (ValidationError, TypeError, ValueError):
            continue
        if judgment.typology in wanted and judgment.typology not in found:
            found[judgment.typology] = judgment
    return found


def _empty_judgment(typology: Typology) -> ChairTypologyJudgment:
    return ChairTypologyJudgment(typology=typology, factual_disputes=[], value_disputes=[])


def _merge(transcript: Round1Transcript, judgments: list[ChairTypologyJudgment]) -> ChairSynthesis:
    comparisons = [
        TypologyComparison(
            typology=item.typology,
            scores_by_agent=scores_by_agent_for(transcript, item.typology),
            factual_disputes=item.factual_disputes,
            value_disputes=item.value_disputes,
        )
        for item in judgments
    ]
    return parse_chair_synthesis(
        {
            "site_id": transcript.site_id,
            "typology_comparison": [item.model_dump(mode="json") for item in comparisons],
            "limitations": [item.model_dump(mode="json") for item in compile_limitations(transcript)],
            "responsible_use_note": RESPONSIBLE_USE_NOTE,
        }
    )


# Imported by tests that patch AGENT_ORDER completeness
__all__ = ["AGENT_ORDER", "compact_round1_for_chair", "compile_limitations", "run_chair"]
