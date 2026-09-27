from __future__ import annotations

import pytest
from pydantic import ValidationError

from housing_review.schemas import ChairSynthesis, parse_chair_synthesis
from housing_review.schemas.chair import RESPONSIBLE_USE_NOTE


def valid_chair_payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "site_id": "parcel-001",
        "typology_comparison": [
            {
                "typology": "duplex",
                "scores_by_agent": {
                    "zoning_analyst": 8,
                    "demographic_analyst": 6,
                    "pro_forma_analyst": 5,
                    "equity_analyst": 4,
                    "sustainability_analyst": 7,
                },
                "factual_disputes": [
                    {
                        "issue": "Comparable sale set used by Pro Forma may not match tract household data vintage.",
                        "agents_involved": ["pro_forma_analyst", "demographic_analyst"],
                        "resolution_needed": "Verify sale-validation codes and ACS vintage with a planner.",
                    }
                ],
                "value_disputes": [
                    {
                        "issue": "Sustainability favors duplex density; Equity flags affordability mismatch risk.",
                        "agents_involved": ["sustainability_analyst", "equity_analyst"],
                        "framing": "Human decision-makers must weigh climate/infrastructure efficiency against who can afford the units.",
                    }
                ],
            }
        ],
        "limitations": [
            {
                "question": "Site-specific construction cost is not available from catalog sources.",
                "raised_by": "pro_forma_analyst",
                "next_step": "Obtain a local contractor estimate or treat cost as a labeled generic estimate.",
            }
        ],
        "responsible_use_note": RESPONSIBLE_USE_NOTE,
    }
    data.update(overrides)
    return data


def test_chair_accepts_canonical_payload() -> None:
    result = parse_chair_synthesis(valid_chair_payload())
    assert isinstance(result, ChairSynthesis)
    assert result.site_id == "parcel-001"
    assert "Decision support only" in result.responsible_use_note
    assert "not legal, financial, or zoning advice" in result.responsible_use_note.lower()
    comparison = result.typology_comparison[0]
    assert comparison.scores_by_agent
    assert comparison.factual_disputes[0].resolution_needed
    assert comparison.value_disputes[0].framing


def test_chair_fills_default_responsible_use_note() -> None:
    payload = valid_chair_payload()
    del payload["responsible_use_note"]
    result = parse_chair_synthesis(payload)
    assert result.responsible_use_note == RESPONSIBLE_USE_NOTE


def test_chair_rejects_unknown_score_key() -> None:
    payload = valid_chair_payload()
    comparison = payload["typology_comparison"][0]
    assert isinstance(comparison, dict)
    scores = comparison["scores_by_agent"]
    assert isinstance(scores, dict)
    scores["best_guess_agent"] = 9
    with pytest.raises(ValidationError):
        parse_chair_synthesis(payload)


def test_chair_rejects_extra_top_level_field() -> None:
    with pytest.raises(ValidationError):
        parse_chair_synthesis(valid_chair_payload(winner="duplex"))
