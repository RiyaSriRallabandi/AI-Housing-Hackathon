from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator

from housing_review.data.demo_site import demo_site_record
from housing_review.data.site import ZoningSiteContext, load_zoning_site
from housing_review.data.zoning_facts import (
    code_side_cannot_determine,
    deterministic_claims_for_typology,
    district_code_from_context,
    facts_pack_for_llm,
)
from housing_review.llm import Completer, complete_json
from housing_review.schemas import AnalystAssessment, Typology
from housing_review.schemas.common import (
    STRICT_CONFIG,
    ConfidenceBasis,
    NonEmptyStr,
    Score,
    coerce_typology,
)
from housing_review.schemas.parse import parse_analyst_assessment

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "zoning_analyst_round1.txt"
CANDIDATE_TYPOLOGIES = list(Typology)
MAX_SCHEMA_RETRIES = 1
JUDGMENT_FAILURE_NOTE = (
    "Zoning Analyst model failed to produce valid score/summary JSON twice; "
    "numeric score is a withheld placeholder (0), not a comparative ranking. "
    "Use-table, parking, and dimensional claims were still attached from code."
)


class ZoningJudgment(BaseModel):
    """LLM-only slice: score and summary. Deterministic claims are attached in code."""

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


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _user_prompt(context: ZoningSiteContext, typologies: list[Typology], demo: dict | None) -> str:
    demo_slim = None
    if demo:
        demo_slim = {
            "address": (demo.get("address") or {}).get("full"),
            "neighborhood": (demo.get("neighborhood") or {}).get("name"),
        }
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_id": context.site_id,
        "mapped_district": district_code_from_context(context),
        "deterministic_facts": facts_pack_for_llm(context, typologies),
        "code_side_cannot_determine": code_side_cannot_determine(context.residential_profile),
        "demo_record": demo_slim,
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Score EVERY candidate typology in one comparative pass using ONLY "
        "deterministic_facts. Do not emit claims. Return JSON as "
        '{"judgments": [ ... ]}.\n'
        + json.dumps(payload)
    )


def run_zoning_analyst(
    context: ZoningSiteContext,
    *,
    typologies: list[Typology] | None = None,
    completer: Completer | None = None,
    demo_record: dict | None = None,
) -> list[AnalystAssessment]:
    """Round 1 Zoning. One LLM call for all requested typologies; claims come from code."""
    typologies = typologies or CANDIDATE_TYPOLOGIES
    generate = completer or complete_json
    system = _system_prompt()
    user = _user_prompt(context, typologies, demo_record)
    raw = ""
    for _ in range(MAX_SCHEMA_RETRIES + 1):
        raw = generate(system, user)
        try:
            judgments = [_parse_judgment(item) for item in _parse_judgments(raw)]
            _assert_judgments(judgments, typologies)
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            user = (
                user
                + "\n\nYour previous output failed judgment-schema validation: "
                + str(exc)
                + "\nReturn {\"judgments\": [...]} only. Each object: typology, score, "
                "basis, summary, cannot_determine. No claims. Include every typology."
            )
            continue
        return [_merge(context, item) for item in judgments]
    salvaged = _salvage_judgments(raw, typologies)
    return [
        _merge(context, salvaged.get(typology) or _fallback_judgment(typology))
        for typology in typologies
    ]


def run_zoning_analyst_for_demo(*, include_overlays: bool = True, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_zoning_site(record["pin"], include_overlays=include_overlays)
    return run_zoning_analyst(context, completer=completer, demo_record=record)


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


def _parse_judgment(item: object) -> ZoningJudgment:
    if not isinstance(item, dict):
        raise TypeError("each judgment must be an object")
    return ZoningJudgment.model_validate(item)


def _salvage_judgments(raw: str, typologies: list[Typology]) -> dict[Typology, ZoningJudgment]:
    """Keep any well-formed judgments after a second schema failure; skip the rest."""
    wanted = set(typologies)
    found: dict[Typology, ZoningJudgment] = {}
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


def _fallback_judgment(typology: Typology) -> ZoningJudgment:
    return ZoningJudgment(
        typology=typology,
        score=0,
        basis=ConfidenceBasis.estimated,
        summary=(
            "Score and narrative judgment could not be determined: the model "
            "failed to produce valid output twice."
        ),
        cannot_determine=[JUDGMENT_FAILURE_NOTE],
    )


def _assert_judgments(judgments: list[ZoningJudgment], typologies: list[Typology]) -> None:
    got = {item.typology for item in judgments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in Zoning judgments: {missing}")


def _merge(context: ZoningSiteContext, judgment: ZoningJudgment) -> AnalystAssessment:
    district = district_code_from_context(context) or ""
    claims = deterministic_claims_for_typology(
        judgment.typology,
        district_code=district,
        profile=context.residential_profile,
        adu_overlay=context.adu_overlay,
    )
    gaps = list(dict.fromkeys(
        code_side_cannot_determine(context.residential_profile) + list(judgment.cannot_determine)
    ))
    return parse_analyst_assessment(
        {
            "agent": "zoning_analyst",
            "site_id": context.site_id,
            "typology": judgment.typology.value,
            "score": judgment.score,
            "basis": judgment.basis.value,
            "claims": [item.model_dump(mode="json") for item in claims],
            "cannot_determine": gaps,
            "summary": judgment.summary,
        }
    )
