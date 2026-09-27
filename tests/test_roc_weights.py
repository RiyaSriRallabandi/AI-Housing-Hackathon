from __future__ import annotations

import pytest

from housing_review.schemas.common import AnalystName, Typology
from housing_review.weighting import (
    USER_WEIGHTED_VIEW_LABEL,
    apply_agent_weights,
    apply_weighted_view,
    roc_weights,
)
from tests.test_weighting import _by_typ, _chair, _round1

# Rank-order centroid for n=5: w_k = (1/5) * sum_{i=k..5} 1/i
ROC_SHARES = (137 / 300, 77 / 300, 47 / 300, 9 / 100, 1 / 25)

SAMPLE_ORDER = (
    AnalystName.zoning_analyst,
    AnalystName.sustainability_analyst,
    AnalystName.demographic_analyst,
    AnalystName.pro_forma_analyst,
    AnalystName.equity_analyst,
)


def test_roc_weights_sum_to_one_decrease_and_stay_positive() -> None:
    weights = roc_weights(SAMPLE_ORDER)
    ordered = [weights[name] for name in SAMPLE_ORDER]
    assert sum(ordered) == pytest.approx(1.0)
    assert ordered == pytest.approx(list(ROC_SHARES))
    assert ordered == sorted(ordered, reverse=True)
    assert all(share > 0 for share in ordered)
    assert min(ordered) == pytest.approx(0.04)


def test_roc_weights_follow_preference_not_agent_enum_order() -> None:
    flipped = tuple(reversed(SAMPLE_ORDER))
    weights = roc_weights(flipped)
    assert weights[AnalystName.equity_analyst] == pytest.approx(ROC_SHARES[0])
    assert weights[AnalystName.zoning_analyst] == pytest.approx(ROC_SHARES[-1])


def test_roc_rejects_incomplete_or_duplicate_order() -> None:
    with pytest.raises(ValueError, match="all 5"):
        roc_weights(SAMPLE_ORDER[:4])
    with pytest.raises(ValueError, match="exactly once"):
        roc_weights((*SAMPLE_ORDER[:4], SAMPLE_ORDER[0]))


def test_first_reveal_matches_apply_agent_weights_on_roc_shares() -> None:
    round1 = _round1()
    chair = _chair()
    from_rank = apply_weighted_view(round1, chair, preference_order=SAMPLE_ORDER)
    from_weights = apply_agent_weights(round1, chair, roc_weights(SAMPLE_ORDER))
    assert from_rank.view_label == USER_WEIGHTED_VIEW_LABEL
    assert [row.typology for row in from_rank.ranking] == [row.typology for row in from_weights.ranking]
    assert from_rank.ranking[0].weighted_score == pytest.approx(from_weights.ranking[0].weighted_score)
    apartment = _by_typ(from_rank)[Typology.apartment]
    assert apartment.factual_disputes
    assert any(item.cannot_determine for item in apartment.cannot_determine)


def test_slider_recompute_does_not_rerun_preference_order() -> None:
    round1 = _round1()
    chair = _chair()
    first = apply_weighted_view(round1, chair, preference_order=SAMPLE_ORDER)
    tweaked = dict(first.weights)
    tweaked[AnalystName.sustainability_analyst] = first.weights[AnalystName.sustainability_analyst] + 0.20
    second = apply_weighted_view(round1, chair, weights=tweaked)
    assert second.weights[AnalystName.sustainability_analyst] > first.weights[AnalystName.sustainability_analyst]
    first_gap = (
        _by_typ(first)[Typology.apartment].weighted_score
        - _by_typ(first)[Typology.duplex].weighted_score
    )
    second_gap = (
        _by_typ(second)[Typology.apartment].weighted_score
        - _by_typ(second)[Typology.duplex].weighted_score
    )
    assert second_gap > first_gap


def test_cannot_pass_ranking_and_sliders_together() -> None:
    with pytest.raises(ValueError, match="not both"):
        apply_weighted_view(
            _round1(),
            _chair(),
            preference_order=SAMPLE_ORDER,
            weights=roc_weights(SAMPLE_ORDER),
        )
