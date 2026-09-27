from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from housing_review.schemas import (
    AnalystAssessment,
    AnalystAssessmentRound2,
    AnalystName,
    ConfidenceBasis,
    Typology,
    parse_analyst_assessment,
)


def valid_payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "agent": "zoning_analyst",
        "site_id": "parcel-001",
        "typology": "duplex",
        "score": 7,
        "basis": "measured",
        "claims": [
            {
                "statement": "Duplexes are permitted in this district.",
                "basis": "measured",
                "source": "Pittsburgh Zoning Code §911.02",
                "confidence_note": "Confirm overlay applicability with City Planning.",
            }
        ],
        "cannot_determine": [],
        "summary": "As-of-right path looks relatively clear for a duplex, subject to dimensional checks.",
    }
    data.update(overrides)
    return data


def test_round1_accepts_canonical_payload() -> None:
    result = parse_analyst_assessment(valid_payload())
    assert isinstance(result, AnalystAssessment)
    assert not isinstance(result, AnalystAssessmentRound2)
    assert result.agent is AnalystName.zoning_analyst
    assert result.typology is Typology.duplex
    assert result.score == 7
    assert result.basis is ConfidenceBasis.measured
    assert result.cannot_determine == []
    assert result.claims[0].source.startswith("Pittsburgh Zoning Code")


def test_round1_accepts_json_string_and_display_names() -> None:
    payload = valid_payload(agent="Zoning Analyst", typology="ADU")
    result = parse_analyst_assessment(json.dumps(payload))
    assert result.agent is AnalystName.zoning_analyst
    assert result.typology is Typology.adu


def test_missing_cannot_determine_is_rejected() -> None:
    payload = valid_payload()
    del payload["cannot_determine"]
    with pytest.raises(ValidationError):
        parse_analyst_assessment(payload)


def test_extra_field_is_rejected() -> None:
    payload = valid_payload(verdict="best option")
    with pytest.raises(ValidationError):
        parse_analyst_assessment(payload)


def test_round1_rejects_round2_notes() -> None:
    payload = valid_payload(round_2_notes="no change")
    with pytest.raises(ValidationError):
        parse_analyst_assessment(payload, round_2=False)


def test_round2_requires_notes() -> None:
    with pytest.raises(ValidationError):
        parse_analyst_assessment(valid_payload(), round_2=True)

    result = parse_analyst_assessment(
        valid_payload(round_2_notes="No change based on other analysts' findings."),
        round_2=True,
    )
    assert isinstance(result, AnalystAssessmentRound2)
    assert "No change" in result.round_2_notes


def test_score_bounds() -> None:
    parse_analyst_assessment(valid_payload(score=0))
    parse_analyst_assessment(valid_payload(score=10))
    with pytest.raises(ValidationError):
        parse_analyst_assessment(valid_payload(score=-1))
    with pytest.raises(ValidationError):
        parse_analyst_assessment(valid_payload(score=11))


def test_claim_requires_source() -> None:
    payload = valid_payload(
        claims=[{"statement": "Allowed.", "basis": "measured"}]
    )
    with pytest.raises(ValidationError):
        parse_analyst_assessment(payload)


def test_townhome_aliases_match_brief_and_title9() -> None:
    assert parse_analyst_assessment(valid_payload(typology="townhome")).typology is Typology.townhome
    assert parse_analyst_assessment(valid_payload(typology="townhouse")).typology is Typology.townhome
    assert (
        parse_analyst_assessment(valid_payload(typology="Single-Unit Attached Residential")).typology
        is Typology.townhome
    )


def test_unknown_typology_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_analyst_assessment(valid_payload(typology="skyscraper"))


def test_empty_summary_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_analyst_assessment(valid_payload(summary="   "))
