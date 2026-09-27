"""Deterministic human-weighted ranking over cached Round 1 / Chair scores.

This is the user's own weighted view. It does not pick a preferred typology.
No network or model calls.
"""

from __future__ import annotations

from collections.abc import Mapping

from housing_review.schemas.chair import ChairSynthesis, TypologyComparison
from housing_review.schemas.common import AnalystName, Typology, coerce_agent
from housing_review.schemas.debate import AGENT_ORDER, Round1Transcript
from housing_review.schemas.weighting import (
    AgentContribution,
    AgentGaps,
    TypologyWeightedResult,
    ViewLabel,
    WeightedView,
)

EQUAL_AGENT_WEIGHT = 0.2
EQUAL_WEIGHT_VIEW_LABEL: ViewLabel = "equal-weight view"
USER_WEIGHTED_VIEW_LABEL: ViewLabel = "user-weighted view"
EQUITY_NON_DIFFERENTIATING_NOTE = (
    "Equity scores are identical across typologies because they rest on "
    "tract-constant CHAS facts, not unit prices. Increasing the Equity weight "
    "does not rank one typology above another."
)

_WEIGHT_TOLERANCE = 1e-12


def default_weights() -> dict[AnalystName, float]:
    return {name: EQUAL_AGENT_WEIGHT for name in AGENT_ORDER}


def normalize_weights(weights: Mapping[AnalystName | str, float] | None = None) -> dict[AnalystName, float]:
    """Turn user sliders into shares that sum to 1. Relative magnitudes are what matter."""
    raw = (
        default_weights()
        if weights is None
        else {coerce_agent(item): float(value) for item, value in weights.items()}
    )
    missing = [name for name in AGENT_ORDER if name not in raw]
    extra = [name for name in raw if name not in AGENT_ORDER]
    if missing or extra:
        raise ValueError(f"Weights must include exactly the five analysts; missing={missing} extra={extra}")
    if any(raw[name] < 0 for name in AGENT_ORDER):
        raise ValueError("Agent weights must be non-negative")
    total = sum(raw[name] for name in AGENT_ORDER)
    if total <= _WEIGHT_TOLERANCE:
        raise ValueError("At least one agent weight must be positive")
    return {name: raw[name] / total for name in AGENT_ORDER}


def apply_agent_weights(
    round1: Round1Transcript,
    chair: ChairSynthesis,
    weights: Mapping[AnalystName | str, float] | None = None,
) -> WeightedView:
    """Re-rank typologies from cached scores. Instant; no model calls."""
    if round1.site_id != chair.site_id:
        raise ValueError(f"Round 1 site_id {round1.site_id!r} does not match Chair {chair.site_id!r}")
    shares = normalize_weights(weights)
    typologies = round1.typologies()
    chair_by_typ = {row.typology: row for row in chair.typology_comparison}
    missing_chair = [item for item in typologies if item not in chair_by_typ]
    extra_chair = [item for item in chair_by_typ if item not in set(typologies)]
    if missing_chair or extra_chair:
        raise ValueError(f"Chair typologies must match Round 1; missing={missing_chair} extra={extra_chair}")

    scored: list[tuple[float, int, dict]] = []
    for index, typology in enumerate(typologies):
        scores = _scores_for(round1, chair_by_typ[typology], typology)
        contributions = [
            AgentContribution(
                agent=name,
                score=scores[name],
                weight=shares[name],
                contribution=shares[name] * scores[name],
            )
            for name in AGENT_ORDER
        ]
        weighted_score = sum(item.contribution for item in contributions)
        chair_row = chair_by_typ[typology]
        scored.append(
            (
                weighted_score,
                index,
                {
                    "typology": typology,
                    "weighted_score": weighted_score,
                    "contributions": contributions,
                    "cannot_determine": _gaps_for(round1, typology),
                    "factual_disputes": list(chair_row.factual_disputes),
                    "value_disputes": list(chair_row.value_disputes),
                },
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1]))
    ranking = [
        TypologyWeightedResult(rank=rank, **payload)
        for rank, (_score, _index, payload) in enumerate(scored, start=1)
    ]

    return WeightedView(
        site_id=round1.site_id,
        view_label=_view_label(shares),
        weights=shares,
        ranking=ranking,
        precision_notes=_precision_notes(round1, shares),
        limitations=list(chair.limitations),
        responsible_use_note=chair.responsible_use_note,
    )


def _scores_for(
    round1: Round1Transcript,
    chair_row: TypologyComparison,
    typology: Typology,
) -> dict[AnalystName, int]:
    by_agent = round1.by_agent()
    scores: dict[AnalystName, int] = {}
    for name in AGENT_ORDER:
        matches = [item for item in by_agent.get(name, []) if item.typology is typology]
        if len(matches) != 1:
            raise ValueError(f"Expected one {name.value} assessment for {typology.value}")
        score = matches[0].score
        if name not in chair_row.scores_by_agent:
            raise ValueError(f"Chair is missing {name.value} score for {typology.value}")
        if chair_row.scores_by_agent[name] != score:
            raise ValueError(
                f"Round 1 and Chair scores disagree for {typology.value}/{name.value}: "
                f"{score} vs {chair_row.scores_by_agent[name]}"
            )
        scores[name] = score
    return scores


def _gaps_for(round1: Round1Transcript, typology: Typology) -> list[AgentGaps]:
    by_agent = round1.by_agent()
    return [
        AgentGaps(
            agent=name,
            cannot_determine=list(next(item for item in by_agent[name] if item.typology is typology).cannot_determine),
        )
        for name in AGENT_ORDER
    ]


def _view_label(shares: Mapping[AnalystName, float]) -> ViewLabel:
    expected = 1.0 / len(AGENT_ORDER)
    if all(abs(shares[name] - expected) <= _WEIGHT_TOLERANCE for name in AGENT_ORDER):
        return EQUAL_WEIGHT_VIEW_LABEL
    return USER_WEIGHTED_VIEW_LABEL


def _precision_notes(round1: Round1Transcript, shares: Mapping[AnalystName, float]) -> list[str]:
    if shares[AnalystName.equity_analyst] <= _WEIGHT_TOLERANCE:
        return []
    equity_scores = [
        item.score
        for item in round1.assessments
        if item.agent is AnalystName.equity_analyst
    ]
    if equity_scores and len(set(equity_scores)) == 1:
        return [EQUITY_NON_DIFFERENTIATING_NOTE]
    return []
