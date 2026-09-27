from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.demographic import run_demographic_analyst
from housing_review.data.catalog import demographic_analyst_sources
from housing_review.data.demographics import load_demographic_site_from_path
from housing_review.schemas import AnalystName, Typology

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_demographic_sources_log_acs_and_decennial() -> None:
    records = demographic_analyst_sources()
    names = {item.name for item in records}
    assert "American Community Survey 5-Year" in names
    assert "Decennial Census" in names
    acs = next(item for item in records if "American Community" in item.name)
    assert "margins of error" in acs.caveat.lower() or "margins of error" in acs.caveat
    assert all(item.retrieved_on.isoformat() == "2026-09-26" for item in records)


def test_demographic_fixture_has_moe_and_gaps() -> None:
    ctx = load_demographic_site_from_path(FIXTURES / "demographic_tract_42003191800.json")
    assert ctx.geoid == "42003191800"
    assert ctx.site_id == "0139F00077000000"
    assert ctx.acs_2023.population.value == 5332
    assert ctx.acs_2023.population.moe == 663
    assert ctx.acs_2023.avg_household_size.value == 2.12
    assert ctx.acs_2018.avg_household_size.value == 2.30
    assert ctx.dec_2020.population.value == 5252
    assert any("margins of error" in note.lower() for note in ctx.coverage_notes)
    assert any("USPS" in note for note in ctx.coverage_notes)


def test_demographic_analyst_validates_mocked_round1() -> None:
    context = load_demographic_site_from_path(FIXTURES / "demographic_tract_42003191800.json")
    payload = [
        {
            "agent": "demographic_analyst",
            "site_id": "0139F00077000000",
            "typology": "duplex",
            "score": 6,
            "basis": "trend_inferred",
            "claims": [
                {
                    "statement": "Average household size declined from 2.30 (ACS 2014-2018) to 2.12 (ACS 2019-2023).",
                    "basis": "trend_inferred",
                    "source": "ACS 5-Year B25010_001E, vintages 2014-2018 and 2019-2023",
                    "confidence_note": "MOE is ±0.13 then ±0.20; the decline may not be significant.",
                }
            ],
            "cannot_determine": [
                "Vacancy rate by units-in-structure is not in the retrieved ACS tables.",
                "USPS postal vacancy was not retrieved.",
            ],
            "summary": "Trends suggest smaller household size; this may reflect supply constraints rather than preference. Decision support only.",
        }
    ]

    def fake_complete(system: str, user: str) -> str:
        assert "Demographic Analyst" in system
        assert "42003191800" in user
        assert "there is demand for" not in system.lower() or "never" in system.lower()
        return json.dumps({"assessments": payload})

    results = run_demographic_analyst(context, typologies=[Typology.duplex], completer=fake_complete)
    assert results[0].agent is AnalystName.demographic_analyst
    assert results[0].score == 6
    assert any("USPS" in item for item in results[0].cannot_determine)
