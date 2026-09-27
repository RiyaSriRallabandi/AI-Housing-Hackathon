from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.sustainability import run_sustainability_analyst
from housing_review.data.catalog import sustainability_analyst_sources
from housing_review.data.sustainability import load_sustainability_site_from_path
from housing_review.schemas import AnalystName, Typology

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_sustainability_fixture_flood_is_zone_x_not_sfha() -> None:
    ctx = load_sustainability_site_from_path(FIXTURES / "sustainability_0139F00077000000.json")
    assert ctx.site_id == "0139F00077000000"
    assert ctx.flood.layer_covers_point is True
    assert ctx.flood.fld_zone == "X"
    assert ctx.flood.in_sfha is False
    assert ctx.steep_slope_25pct.flagged is True
    assert ctx.major_transit_buffer.in_1500ft_major_transit_buffer is False
    assert ctx.prt.unique_within_400m == 0
    assert ctx.prt.unique_within_1500ft == 0
    assert ctx.prt.nearest[0].stop_name == "MCNEILLY STATION"
    assert ctx.prt.nearest[0].mode == "RAIL"


def test_sustainability_sources_log_gtfs_slug_and_fema() -> None:
    records = sustainability_analyst_sources()
    gtfs = next(item for item in records if "GTFS" in item.name)
    fema = next(item for item in records if "FEMA" in item.name)
    assert "404" in gtfs.does_not_cover
    assert "prt-of-allegheny-county-transit-stops" in gtfs.resolved_url
    assert "reliability" in gtfs.caveat.lower()
    assert "flood determination" in fema.caveat.lower()
    assert "Zone X" in fema.caveat


def test_sustainability_analyst_validates_mocked_round1() -> None:
    context = load_sustainability_site_from_path(FIXTURES / "sustainability_0139F00077000000.json")
    payload = [
        {
            "agent": "sustainability_analyst",
            "site_id": "0139F00077000000",
            "typology": "apartment",
            "score": 7,
            "basis": "estimated",
            "claims": [
                {
                    "statement": "Nearest scheduled stop is McNeilly Station (rail) at about 637 m.",
                    "basis": "measured",
                    "source": "WPRDC PRT Transit Stops d6e6ed6e-9220-4a0e-9796-e72d83ce8e7a feed 2606",
                    "confidence_note": "Scheduled, not realized reliability. Outside 1,500 ft overlay.",
                },
                {
                    "statement": "Apartments generally have lower per-unit carbon than detached houses.",
                    "basis": "estimated",
                    "source": "Generic typology-level direction in site_context.carbon; not a site LCA",
                },
            ],
            "cannot_determine": ["On-time performance of route BLUE/SLVR."],
            "summary": "Rail is nearby but outside the City 1,500 ft overlay. Flood map is Zone X, not SFHA.",
        }
    ]

    def fake(system: str, user: str) -> str:
        assert "Sustainability Analyst" in system
        assert "estimated" in user
        assert "MCNEILLY" in user
        assert "FLD_ZONE" in user or "fld_zone" in user
        return json.dumps({"assessments": payload})

    results = run_sustainability_analyst(context, typologies=[Typology.apartment], completer=fake)
    assert results[0].agent is AnalystName.sustainability_analyst
    assert results[0].score == 7
    assert results[0].claims[1].basis.value == "estimated"
