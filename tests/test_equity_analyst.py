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
    payload = [
        {
            "agent": "equity_analyst",
            "site_id": "0139F00077000000",
            "typology": "adu",
            "score": 7,
            "basis": "measured",
            "claims": [
                {
                    "statement": "About 18.5% of households were cost-burdened in 2013-2017 CHAS.",
                    "basis": "measured",
                    "source": "CHAS 2013-2017 T8_CB_PCT GEOID 42003191800",
                    "confidence_note": "Older than HUD 2018-2022 CHAS.",
                }
            ],
            "cannot_determine": ["Displacement from this project."],
            "summary": "Affordability mismatch risk, not measured displacement.",
        }
    ]

    def fake(system: str, user: str) -> str:
        assert "Equity Analyst" in system
        assert "2013-2017" in user
        assert "B25070" in user
        return json.dumps({"assessments": payload})

    results = run_equity_analyst(context, typologies=[Typology.adu], completer=fake)
    assert results[0].agent is AnalystName.equity_analyst
    assert results[0].score == 7
