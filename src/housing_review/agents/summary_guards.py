from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from housing_review.agents.judgment import AgentJudgment
from housing_review.data.equity_facts import PRICE_DATA_TOKEN
from housing_review.llm import Completer, parse_json_object
from housing_review.schemas.analyst import Claim
from housing_review.schemas.common import STRICT_CONFIG, Typology

# Live Round 1 used "growing demand" / "notable demand trend" despite the prompt.
_DEMAND_WORD = re.compile(r"(?i)\bdemand\b")

_PRICE_GAP = re.compile(r"(?i)price_data|sale/rent price|price of a new unit")

_TYPOLOGY_MENTION = {
    Typology.duplex: ("duplex", "two-unit", "two unit"),
    Typology.apartment: ("apartment", "multi-unit", "multi unit"),
    Typology.townhome: ("townhome", "townhouse", "attached"),
    Typology.adu: ("adu", "accessory"),
    Typology.senior_housing: ("senior", "elderly"),
    Typology.detached_single_family: ("detached", "single-family", "single family"),
}

# Concept stems, not a two-word ban list. Tract CHAS restatements may say
# "cost-burdened" without these; typology-linked affordability may not.
_AFFORDABILITY_CONCEPT = re.compile(
    r"(?i)"
    r"afford|"
    r"mismatch|"
    r"(?:beyond|within)(?:\s+the)?\s+means|"
    r"\bpriced\b|"
    r"price(?:d)?\s+point|"
    r"economic fit|financial fit|"
    r"housing[- ]cost pressure|"
    r"ability to pay|"
    r"cheaper (?:for|than)|more expensive|"
    r"cost[- ]burden(?:ed)?\s+risk|"
    r"\brisk\b.{0,40}cost[- ]burden|cost[- ]burden.{0,40}\brisk\b"
)

_TYPOLOGY_REF = re.compile(
    r"(?i)\b(this typology|this type|this option|this product|the typology|"
    r"this housing type|this candidate)\b"
)

_CANNOT_DETERMINE_AFFORD = re.compile(
    r"(?i)(cannot be determined|cannot determine|not determined|"
    r"undetermined|is not in the (payload|data|facts))"
)

_TRACT_CHAS = re.compile(
    r"(?i)(\bchas\b|hamfi|occupied households|cost-burden)"
)

EQUITY_REVIEW_TASK = "equity_affordability_semantic_review"


class EquityAffordabilityViolation(BaseModel):
    model_config = STRICT_CONFIG

    typology: str
    reason: str


class EquityAffordabilityReview(BaseModel):
    model_config = STRICT_CONFIG

    overreach: bool
    violations: list[EquityAffordabilityViolation] = Field(default_factory=list)


def gaps_include_unknown_price(cannot_determine: list[str]) -> bool:
    blob = " ".join(cannot_determine)
    return PRICE_DATA_TOKEN in blob or bool(_PRICE_GAP.search(blob))


def assert_equity_summaries_respect_unknown_price(
    judgments: list[AgentJudgment],
    extra_gaps: list[str] | None = None,
) -> None:
    """Reject typology-linked affordability claims when unit price is unknown."""
    extra = extra_gaps or []
    for item in judgments:
        gaps = list(item.cannot_determine) + extra
        if not gaps_include_unknown_price(gaps):
            continue
        _assert_summary_does_not_link_typology_to_affordability(item)


def _assert_summary_does_not_link_typology_to_affordability(item: AgentJudgment) -> None:
    for sentence in _sentences(item.summary):
        if _is_allowed_cannot_determine_sentence(sentence):
            continue
        if _is_tract_chas_restatement(sentence, item.typology):
            continue
        if _AFFORDABILITY_CONCEPT.search(sentence):
            raise ValueError(
                f"{item.typology.value} summary implies typology-specific affordability "
                f"without price data: {sentence!r}"
            )


def review_equity_summaries_against_claims(
    generate: Completer,
    judgments: list[AgentJudgment],
    claims_by_typology: dict[Typology, list[Claim]],
) -> None:
    """LLM semantic check: implied affordability vs cited facts, not word matching."""
    payload = {
        "task": EQUITY_REVIEW_TASK,
        "question": (
            "Does this summary state or imply anything about a typology's "
            "affordability that isn't supported by the cited facts?"
        ),
        "items": [
            {
                "typology": item.typology.value,
                "summary": item.summary,
                "cited_facts": [claim.statement for claim in claims_by_typology[item.typology]],
                "cannot_determine": item.cannot_determine,
            }
            for item in judgments
        ],
    }
    system = (
        "You review Equity Analyst summaries against cited facts. The facts are "
        "tract-level CHAS cost-burden counts only. They do not include sale or rent "
        "prices for any housing type. Return JSON only with keys overreach (boolean) "
        "and violations (list of {typology, reason}). overreach is true if ANY "
        "summary states or implies that a typology is more or less affordable, is an "
        "affordability or cost-burden mismatch/risk, is within or beyond residents' "
        "means, or otherwise has an affordability relationship the cited facts do not "
        "support. Restating tract CHAS percentages and saying typology-specific "
        "affordability cannot be determined is not overreach. Do not invent facts."
    )
    raw = generate(system, json.dumps(payload))
    review = EquityAffordabilityReview.model_validate(parse_json_object(raw))
    if review.overreach or review.violations:
        details = "; ".join(
            f"{item.typology}: {item.reason}" for item in review.violations
        ) or "overreach=true with empty violations"
        raise ValueError(
            "Equity semantic review: a summary states or implies typology "
            f"affordability unsupported by cited facts. {details}"
        )


def assert_demographic_summaries_avoid_demand_claims(judgments: list[AgentJudgment]) -> None:
    for item in judgments:
        if _DEMAND_WORD.search(item.summary):
            raise ValueError(
                f"{item.typology.value} summary uses banned demand language "
                f"(use 'trends suggest' / 'consistent with'): {item.summary!r}"
            )


def assert_sustainability_summaries_are_comparative(judgments: list[AgentJudgment]) -> None:
    """Reject copy-pasted templates; each summary must name its own typology."""
    if len(judgments) >= 2:
        normalized = [_norm(item.summary) for item in judgments]
        if len(set(normalized)) < len(normalized):
            raise ValueError(
                "Sustainability summaries must be unique per typology; "
                "identical or templated summaries were repeated."
            )
    for item in judgments:
        text = item.summary.lower()
        mentions = _TYPOLOGY_MENTION[item.typology]
        if not any(token in text for token in mentions):
            raise ValueError(
                f"Sustainability summary for {item.typology.value} must name that typology: "
                f"{item.summary!r}"
            )


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _is_allowed_cannot_determine_sentence(sentence: str) -> bool:
    if not _CANNOT_DETERMINE_AFFORD.search(sentence):
        return False
    return bool(re.search(r"(?i)afford|price|sale|rent", sentence))


def _is_tract_chas_restatement(sentence: str, typology: Typology) -> bool:
    if not _TRACT_CHAS.search(sentence):
        return False
    lower = sentence.lower()
    if _TYPOLOGY_REF.search(sentence):
        return False
    if any(token in lower for token in _TYPOLOGY_MENTION[typology]):
        return False
    return not bool(_AFFORDABILITY_CONCEPT.search(sentence))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()
