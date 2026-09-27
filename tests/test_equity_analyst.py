from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.equity import run_equity_analyst
from housing_review.data.catalog import equity_analyst_sources
from housing_review.data.equity import load_equity_site_from_path
from housing_review.schemas import AnalystName, Typology

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_chas_fixture_is_2013_2017_not_latest_hud() -> None:
    ctx = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")
    assert ctx.geoid == "42003191800"
    assert ctx.chas.vintage == "2013-2017"
    assert ctx.chas.cost_burden_gt_30_pct == 18.45
    assert ctx.chas.cost_burden_gt_50_pct == 8.15
    assert "2018-2022" in ctx.chas.vintage_note
    assert any("displacement" in note.lower() for note in ctx.coverage_notes)


def test_equity_sources_log_chas_vintage() -> None:
    records = equity_analyst_sources()
    assert any("CHAS" in item.name for item in records)
    chas = next(item for item in records if "CHAS" in item.name)
    assert "2013-2017" in chas.caveat
    assert "2018-2022" in chas.caveat


def test_equity_analyst_validates_mocked_round1() -> None:
    context = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")

    def fake(system: str, user: str) -> str:
        assert "Equity Analyst" in system
        assert "2013-2017" in user
        assert "B25070" in system
        assert "deterministic_facts" in user
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "adu",
                        "score": 7,
                        "basis": "measured",
                        "summary": "Affordability mismatch risk, not measured displacement.",
                        "cannot_determine": [],
                    }
                ]
            }
        )

    results = run_equity_analyst(context, typologies=[Typology.adu], completer=fake)
    assert results[0].agent is AnalystName.equity_analyst
    assert results[0].score == 7
    assert "18.45" in results[0].claims[0].statement
    assert "T8_CB_PCT" in results[0].claims[0].source
    assert any("displacement" in note.lower() for note in results[0].cannot_determine)


def test_equity_one_call_and_fallback() -> None:
    context = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")
    calls = {"n": 0}

    def fake(system: str, user: str) -> str:
        calls["n"] += 1
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        assert len(payload["candidate_typologies"]) == 6
        if calls["n"] == 1:
            return json.dumps({"verdict": "nope"})
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "duplex",
                        "score": 6,
                        "basis": "estimated",
                        "summary": "ok duplex",
                        "cannot_determine": [],
                    },
                    {"typology": "apartment", "score": "bad"},
                ]
            }
        )

    results = run_equity_analyst(context, completer=fake)
    assert calls["n"] == 2
    by_typ = {item.typology: item for item in results}
    assert by_typ[Typology.duplex].score == 6
    assert by_typ[Typology.apartment].score == 0
    assert any("failed to produce valid" in note for note in by_typ[Typology.apartment].cannot_determine)
    assert "T8_CB_PCT" in by_typ[Typology.apartment].claims[0].source
