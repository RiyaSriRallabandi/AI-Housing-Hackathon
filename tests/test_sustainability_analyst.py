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

    def fake(system: str, user: str) -> str:
        assert "Sustainability Analyst" in system
        assert "estimated" in user
        assert "MCNEILLY" in user
        assert "FLD_ZONE" in user
        assert "EBEN ST" not in user
        assert '"unique_within_800m"' not in user
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "apartment",
                        "score": 7,
                        "basis": "estimated",
                        "summary": (
                            "Apartment scores higher than detached on per-unit carbon; "
                            "rail is nearby but outside the City 1,500 ft overlay."
                        ),
                        "cannot_determine": [],
                    }
                ]
            }
        )

    results = run_sustainability_analyst(context, typologies=[Typology.apartment], completer=fake)
    assert results[0].agent is AnalystName.sustainability_analyst
    assert results[0].score == 7
    assert results[0].claims[-1].basis.value == "estimated"
    assert "MCNEILLY" in results[0].claims[0].statement.upper() or "McNeilly" in results[0].claims[0].statement
    assert "FEMA_2026" in results[0].claims[1].source or "fema" in results[0].claims[1].source.lower()


def test_sustainability_one_call_all_six() -> None:
    context = load_sustainability_site_from_path(FIXTURES / "sustainability_0139F00077000000.json")
    calls = {"n": 0}

    def fake(system: str, user: str) -> str:
        calls["n"] += 1
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        assert len(payload["candidate_typologies"]) == 6
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": slug,
                        "score": 5,
                        "basis": "estimated",
                        "summary": (
                            f"{slug.replace('_', ' ')} sits relative to the other five "
                            f"on generic carbon versus detached."
                        ),
                        "cannot_determine": [],
                    }
                    for slug in payload["candidate_typologies"]
                ]
            }
        )

    results = run_sustainability_analyst(context, completer=fake)
    assert calls["n"] == 1
    assert len(results) == 6
    assert all(item.claims[-1].basis.value == "estimated" for item in results)


def test_sustainability_retries_identical_summaries() -> None:
    context = load_sustainability_site_from_path(FIXTURES / "sustainability_0139F00077000000.json")
    calls = {"n": 0}
    template = (
        "All typologies share Zone X and a rail stop; higher-density forms score higher "
        "than detached single-family."
    )

    def fake(system: str, user: str) -> str:
        calls["n"] += 1
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        typs = payload["candidate_typologies"]
        if calls["n"] == 1:
            summaries = [template] * len(typs)
        else:
            summaries = [
                f"{slug.replace('_', ' ')} scores relative to the other five on carbon versus detached."
                for slug in typs
            ]
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": slug,
                        "score": 5,
                        "basis": "estimated",
                        "summary": summaries[i],
                        "cannot_determine": [],
                    }
                    for i, slug in enumerate(typs)
                ]
            }
        )

    results = run_sustainability_analyst(context, completer=fake)
    assert calls["n"] == 2
    texts = {item.summary for item in results}
    assert len(texts) == 6
