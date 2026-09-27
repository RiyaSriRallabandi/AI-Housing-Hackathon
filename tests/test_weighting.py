from __future__ import annotations

from pathlib import Path

import housing_review.weighting as weighting_mod
import pytest

from housing_review.schemas.analyst import AnalystAssessment
from housing_review.schemas.chair import RESPONSIBLE_USE_NOTE, ChairSynthesis
from housing_review.schemas.common import AnalystName, Typology
from housing_review.schemas.debate import AGENT_ORDER, Round1Transcript
from housing_review.weighting import (
    EQUAL_AGENT_WEIGHT,
    EQUAL_WEIGHT_VIEW_LABEL,
    EQUITY_NON_DIFFERENTIATING_NOTE,
    USER_WEIGHTED_VIEW_LABEL,
    apply_agent_weights,
    default_weights,
    normalize_weights,
)

SITE = "parcel-weighting-fixture"

# zoning, demographic, pro_forma, equity, sustainability
SCORES: dict[Typology, tuple[int, int, int, int, int]] = {
    Typology.duplex: (10, 4, 3, 5, 2),
    Typology.apartment: (1, 8, 6, 5, 9),
    Typology.townhome: (8, 5, 4, 5, 3),
    Typology.adu: (2, 3, 2, 5, 4),
    Typology.senior_housing: (4, 6, 5, 5, 7),
    Typology.detached_single_family: (9, 2, 7, 5, 1),
}

GAPS = {
    (AnalystName.zoning_analyst, Typology.apartment): ["Use Table cell is blank — not permitted as written."],
    (AnalystName.equity_analyst, Typology.duplex): ["Typology-specific affordability cannot be determined without price data."],
}


def _assessment(agent: AnalystName, typology: Typology, score: int) -> AnalystAssessment:
    return AnalystAssessment.model_validate(
        {
            "agent": agent.value,
            "site_id": SITE,
            "typology": typology.value,
            "score": score,
            "basis": "estimated",
            "claims": [
                {
                    "statement": f"{typology.value} scored {score} by {agent.value}.",
                    "basis": "estimated",
                    "source": "fixture",
                }
            ],
            "cannot_determine": list(GAPS.get((agent, typology), [])),
            "summary": f"{typology.value} fixture summary.",
        }
    )


def _round1() -> Round1Transcript:
    assessments = []
    for typology, scores in SCORES.items():
        for agent, score in zip(AGENT_ORDER, scores, strict=True):
            assessments.append(_assessment(agent, typology, score))
    return Round1Transcript(
        site_id=SITE,
        agents_in_order=list(AGENT_ORDER),
        assessments=assessments,
    )


def _chair() -> ChairSynthesis:
    comparisons = []
    for typology, scores in SCORES.items():
        factual = []
        value = []
        if typology is Typology.apartment:
            factual = [
                {
                    "issue": "Zoning and Sustainability disagree on R2-L apartment permission.",
                    "agents_involved": ["zoning_analyst", "sustainability_analyst"],
                    "resolution_needed": "Verify the Use Table cell.",
                }
            ]
            value = [
                {
                    "issue": "Legal permission vs carbon scoring.",
                    "agents_involved": ["zoning_analyst", "sustainability_analyst"],
                    "framing": "A permitted path and a climate score are different questions.",
                }
            ]
        comparisons.append(
            {
                "typology": typology.value,
                "scores_by_agent": {name.value: score for name, score in zip(AGENT_ORDER, scores, strict=True)},
                "factual_disputes": factual,
                "value_disputes": value,
            }
        )
    return ChairSynthesis.model_validate(
        {
            "site_id": SITE,
            "typology_comparison": comparisons,
            "limitations": [
                {
                    "question": "Typology-specific affordability cannot be determined without price data.",
                    "raised_by": "equity_analyst",
                    "next_step": "Not resolved in this tool. Verify with the relevant office before acting.",
                }
            ],
            "responsible_use_note": RESPONSIBLE_USE_NOTE,
        }
    )


def _by_typ(view) -> dict[Typology, object]:
    return {row.typology: row for row in view.ranking}


def test_weighting_module_does_not_import_llm() -> None:
    source = Path(weighting_mod.__file__).read_text()
    assert "housing_review.llm" not in source
    assert "import llm" not in source
    assert "completer" not in source.lower()
    assert "consensus" not in source.lower()
    assert "the answer" not in source.lower()


def test_default_weights_are_equal_twenty_percent() -> None:
    weights = default_weights()
    assert list(weights) == list(AGENT_ORDER)
    assert all(weight == EQUAL_AGENT_WEIGHT for weight in weights.values())
    assert sum(weights.values()) == pytest.approx(1.0)


def test_normalize_treats_equal_raw_sliders_as_equal_weight_view() -> None:
    shares = normalize_weights({name: 20 for name in AGENT_ORDER})
    assert shares == default_weights()


def test_equal_weight_ranking_matches_hand_calculated_averages() -> None:
    view = apply_agent_weights(_round1(), _chair())
    assert view.view_label == EQUAL_WEIGHT_VIEW_LABEL
    expected = {
        Typology.apartment: 5.8,
        Typology.senior_housing: 5.4,
        Typology.townhome: 5.0,
        Typology.duplex: 4.8,
        Typology.detached_single_family: 4.8,
        Typology.adu: 3.2,
    }
    by_typ = _by_typ(view)
    for typology, score in expected.items():
        assert by_typ[typology].weighted_score == pytest.approx(score)
    assert [row.typology for row in view.ranking] == [
        Typology.apartment,
        Typology.senior_housing,
        Typology.townhome,
        Typology.duplex,
        Typology.detached_single_family,
        Typology.adu,
    ]
    assert [row.rank for row in view.ranking] == [1, 2, 3, 4, 5, 6]


def test_equal_weight_contributions_are_share_times_score() -> None:
    apartment = _by_typ(apply_agent_weights(_round1(), _chair()))[Typology.apartment]
    by_agent = {item.agent: item for item in apartment.contributions}
    assert by_agent[AnalystName.zoning_analyst].contribution == pytest.approx(0.2 * 1)
    assert by_agent[AnalystName.demographic_analyst].contribution == pytest.approx(0.2 * 8)
    assert by_agent[AnalystName.pro_forma_analyst].contribution == pytest.approx(0.2 * 6)
    assert by_agent[AnalystName.equity_analyst].contribution == pytest.approx(0.2 * 5)
    assert by_agent[AnalystName.sustainability_analyst].contribution == pytest.approx(0.2 * 9)
    assert apartment.weighted_score == pytest.approx(sum(item.contribution for item in apartment.contributions))


def test_zoning_only_weight_ranks_by_zoning_scores() -> None:
    weights = {name: 0.0 for name in AGENT_ORDER}
    weights[AnalystName.zoning_analyst] = 1.0
    view = apply_agent_weights(_round1(), _chair(), weights)
    assert view.view_label == USER_WEIGHTED_VIEW_LABEL
    assert [row.typology for row in view.ranking] == [
        Typology.duplex,
        Typology.detached_single_family,
        Typology.townhome,
        Typology.senior_housing,
        Typology.adu,
        Typology.apartment,
    ]
    assert _by_typ(view)[Typology.duplex].weighted_score == pytest.approx(10.0)
    assert _by_typ(view)[Typology.apartment].weighted_score == pytest.approx(1.0)


def test_split_zoning_sustainability_weights() -> None:
    weights = {name: 0.0 for name in AGENT_ORDER}
    weights[AnalystName.zoning_analyst] = 0.5
    weights[AnalystName.sustainability_analyst] = 0.5
    view = apply_agent_weights(_round1(), _chair(), weights)
    by_typ = _by_typ(view)
    assert by_typ[Typology.duplex].weighted_score == pytest.approx(6.0)
    assert by_typ[Typology.townhome].weighted_score == pytest.approx(5.5)
    assert by_typ[Typology.senior_housing].weighted_score == pytest.approx(5.5)
    assert by_typ[Typology.apartment].weighted_score == pytest.approx(5.0)
    assert by_typ[Typology.detached_single_family].weighted_score == pytest.approx(5.0)
    assert by_typ[Typology.adu].weighted_score == pytest.approx(3.0)
    # Tied 5.5: keep Round 1 order (townhome before senior).
    assert [row.typology for row in view.ranking[:2]] == [Typology.duplex, Typology.townhome]


def test_cannot_determine_and_chair_disputes_stay_on_the_typology() -> None:
    view = apply_agent_weights(_round1(), _chair())
    apartment = _by_typ(view)[Typology.apartment]
    gaps = {item.agent: item.cannot_determine for item in apartment.cannot_determine}
    assert gaps[AnalystName.zoning_analyst] == ["Use Table cell is blank — not permitted as written."]
    assert apartment.factual_disputes[0].issue.startswith("Zoning and Sustainability disagree")
    assert apartment.value_disputes[0].framing
    duplex = _by_typ(view)[Typology.duplex]
    assert duplex.factual_disputes == []
    equity_gaps = next(item.cannot_determine for item in duplex.cannot_determine if item.agent is AnalystName.equity_analyst)
    assert "price data" in equity_gaps[0]


def test_equity_flat_scores_do_not_change_relative_rank_and_are_labeled() -> None:
    weights = {name: 0.0 for name in AGENT_ORDER}
    weights[AnalystName.equity_analyst] = 1.0
    view = apply_agent_weights(_round1(), _chair(), weights)
    assert all(row.weighted_score == pytest.approx(5.0) for row in view.ranking)
    assert [row.typology for row in view.ranking] == list(SCORES)
    assert EQUITY_NON_DIFFERENTIATING_NOTE in view.precision_notes
    equal = apply_agent_weights(_round1(), _chair())
    assert EQUITY_NON_DIFFERENTIATING_NOTE in equal.precision_notes


def test_json_dump_is_plain_and_keeps_chair_limitations() -> None:
    payload = apply_agent_weights(_round1(), _chair()).model_dump(mode="json")
    assert payload["view_label"] == EQUAL_WEIGHT_VIEW_LABEL
    assert "consensus" not in str(payload).lower()
    first = payload["ranking"][0]
    assert first["typology"] == "apartment"
    assert first["rank"] == 1
    assert {row["agent"] for row in first["contributions"]} == {name.value for name in AGENT_ORDER}
    assert payload["limitations"][0]["raised_by"] == "equity_analyst"


def test_rejects_negative_or_all_zero_weights() -> None:
    zeros = {name: 0.0 for name in AGENT_ORDER}
    with pytest.raises(ValueError, match="positive"):
        normalize_weights(zeros)
    bad = default_weights()
    bad[AnalystName.zoning_analyst] = -0.1
    with pytest.raises(ValueError, match="non-negative"):
        normalize_weights(bad)


def test_rejects_site_or_score_mismatch() -> None:
    chair = _chair()
    mismatched_site = chair.model_copy(update={"site_id": "other"})
    with pytest.raises(ValueError, match="site_id"):
        apply_agent_weights(_round1(), mismatched_site)
    row = chair.typology_comparison[0]
    tweaked_scores = dict(row.scores_by_agent)
    tweaked_scores[AnalystName.zoning_analyst] = 0
    tweaked_row = row.model_copy(update={"scores_by_agent": tweaked_scores})
    tweaked_chair = chair.model_copy(update={"typology_comparison": [tweaked_row, *chair.typology_comparison[1:]]})
    with pytest.raises(ValueError, match="scores disagree"):
        apply_agent_weights(_round1(), tweaked_chair)
