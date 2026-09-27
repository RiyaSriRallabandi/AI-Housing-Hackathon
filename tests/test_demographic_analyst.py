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

    def fake_complete(system: str, user: str) -> str:
        assert "Demographic Analyst" in system
        assert "42003191800" in user
        assert "there is demand for" not in system.lower() or "never" in system.lower()
        assert "deterministic_facts" in user
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "duplex",
                        "score": 6,
                        "basis": "trend_inferred",
                        "summary": "Trends suggest smaller household size; this may reflect supply constraints rather than preference.",
                        "cannot_determine": [],
                    }
                ]
            }
        )

    results = run_demographic_analyst(context, typologies=[Typology.duplex], completer=fake_complete)
    assert results[0].agent is AnalystName.demographic_analyst
    assert results[0].score == 6
    assert any("USPS" in item for item in results[0].cannot_determine)
    assert "B25010" in results[0].claims[0].source


def test_demographic_one_call_all_six() -> None:
    context = load_demographic_site_from_path(FIXTURES / "demographic_tract_42003191800.json")
    calls = {"n": 0}

    def fake(system: str, user: str) -> str:
        calls["n"] += 1
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        typs = payload["candidate_typologies"]
        assert len(typs) == 6
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": slug,
                        "score": i + 1,
                        "basis": "trend_inferred",
                        "summary": f"note {slug}",
                        "cannot_determine": [],
                    }
                    for i, slug in enumerate(typs)
                ]
            }
        )

    results = run_demographic_analyst(context, completer=fake)
    assert calls["n"] == 1
    assert [item.score for item in results] == [1, 2, 3, 4, 5, 6]
