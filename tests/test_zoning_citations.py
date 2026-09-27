from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.zoning import run_zoning_analyst
from housing_review.data.corpus import citation_contract_for_district
from housing_review.data.parcels import parcel_from_geojson
from housing_review.data.residential import profile_residential_district
from housing_review.data.site import ZoningSiteContext
from housing_review.data.zoning_code import citations_for_districts
from housing_review.data.zoning_districts import ZoningDistrictHit
from housing_review.data.zoning_facts import DIMENSIONS_SOURCE, deterministic_claims_for_typology
from housing_review.schemas import Typology

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DISTRICTS = ("R2-L", "RM-H")


def _context_for_district(district_code: str) -> ZoningSiteContext:
    payload = json.loads((FIXTURES / "parcel_0139F00077000000.geojson").read_text())
    parcel = parcel_from_geojson(payload, "0139F00077000000")
    hit = ZoningDistrictHit(
        district_code=district_code,
        full_zoning_type=district_code,
        legend_type=None,
        status="Approved",
        code_url="https://ecode360.com/45474054",
        object_id=1,
    )
    from housing_review.data.corpus import lookup_for_mapped_districts

    lookup = lookup_for_mapped_districts([district_code])
    profile = profile_residential_district(district_code)
    return ZoningSiteContext(
        site_id=parcel.pin,
        parcel=parcel,
        districts=[hit],
        residential_profile=profile,
        overlays=[],
        adu_overlay={"in_adu_overlay": False, "hits": [], "layer_url": "https://example.invalid/adu"},
        code_lookup=lookup,
        code_citations=citations_for_districts([hit], profile=profile),
        coverage_notes=["Decision support only — not legal, financial, or zoning advice."],
    )


def _judgment(typology: str, score: int, token: str = "ok") -> dict:
    return {
        "typology": typology,
        "score": score,
        "basis": "estimated",
        "summary": f"Comparative note {token} for {typology}.",
        "cannot_determine": [],
    }


def test_deterministic_claims_generalize_across_districts_and_typologies() -> None:
    report: list[str] = []
    for district in DISTRICTS:
        profile = profile_residential_district(district)
        contract = citation_contract_for_district(district)
        report.append(f"\n{district} min_lot={profile.min_lot_sf if profile else None}")
        for typology in Typology:
            claims = deterministic_claims_for_typology(
                typology,
                district_code=district,
                profile=profile,
                adu_overlay={"in_adu_overlay": False, "layer_url": "https://example.invalid/adu"},
            )
            row = contract[typology.value]
            use_claim = claims[0]
            park_claim = claims[1]
            dim_claim = claims[2]
            assert use_claim.source == row["use_source"]
            assert park_claim.source == row["parking_citation"]
            assert row["parking_minimum"] in park_claim.statement
            if row["parking_maximum"]:
                assert row["parking_maximum"] in park_claim.statement
            assert dim_claim.source == DIMENSIONS_SOURCE
            assert "retrieved 2026-09-26" in dim_claim.source
            assert "ecode360.com/45474194" in dim_claim.source
            if typology is Typology.adu:
                assert claims[3].statement.startswith("Live PGHWebZoningOverlays")
            report.append(
                f"  {typology.value:24} use={use_claim.source!r} "
                f"status={row['statuses']} park={park_claim.statement!r}"
            )
        if district == "R2-L":
            apt = deterministic_claims_for_typology(
                Typology.apartment, district_code=district, profile=profile, adu_overlay=None
            )
            assert "blank" in apt[0].statement
            town = deterministic_claims_for_typology(
                Typology.townhome, district_code=district, profile=profile, adu_overlay=None
            )
            assert "0 per unit" in town[1].statement
            assert "4 per unit" in town[1].statement
        if district == "RM-H":
            apt = deterministic_claims_for_typology(
                Typology.apartment, district_code=district, profile=profile, adu_overlay=None
            )
            assert ": P." in apt[0].statement or "P" in apt[0].statement
            assert profile and profile.min_lot_sf == 1200
    print("\n".join(report))


def test_llm_judgments_do_not_supply_citations() -> None:
    calls = {"n": 0}
    context = _context_for_district("R2-L")

    def fake(system: str, user: str) -> str:
        calls["n"] += 1
        assert "judgments" in user
        assert "deterministic_facts" in user
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        items = [_judgment(slug, 6) for slug in payload["candidate_typologies"]]
        return json.dumps({"judgments": items})

    results = run_zoning_analyst(context, completer=fake)
    assert calls["n"] == 1
    assert len(results) == 6
    contract = citation_contract_for_district("R2-L")
    for item in results:
        row = contract[item.typology.value]
        assert any(c.source == row["use_source"] for c in item.claims)
        assert any(c.source == row["parking_citation"] for c in item.claims)
        assert any(c.source == DIMENSIONS_SOURCE for c in item.claims)


def test_one_call_scores_all_six_together() -> None:
    context = _context_for_district("RM-H")
    seen_batch_sizes: list[int] = []

    def fake(system: str, user: str) -> str:
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        typs = payload["candidate_typologies"]
        seen_batch_sizes.append(len(typs))
        return json.dumps({"judgments": [_judgment(slug, i + 1) for i, slug in enumerate(typs)]})

    results = run_zoning_analyst(context, completer=fake)
    assert seen_batch_sizes == [6]
    assert [item.score for item in results] == [1, 2, 3, 4, 5, 6]


def test_ai_claims_field_is_rejected_then_retried() -> None:
    context = _context_for_district("R2-L")
    calls = {"n": 0}

    def flaky(system: str, user: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"judgments": [{"typology": "duplex", "score": 9, "claims": []}]})
        return json.dumps({"judgments": [_judgment("duplex", 7)]})

    results = run_zoning_analyst(context, typologies=[Typology.duplex], completer=flaky)
    assert calls["n"] == 2
    assert results[0].score == 7
    assert results[0].claims[0].source == "§911.02 Use Table"


def test_second_judgment_failure_falls_back_to_cannot_determine() -> None:
    context = _context_for_district("R2-L")

    def always_bad(system: str, user: str) -> str:
        return json.dumps({"verdict": "best"})

    results = run_zoning_analyst(context, typologies=[Typology.duplex], completer=always_bad)
    assert len(results) == 1
    item = results[0]
    assert item.score == 0
    assert item.typology is Typology.duplex
    assert any("failed to produce valid" in note for note in item.cannot_determine)
    assert item.claims[0].source == "§911.02 Use Table"
    assert item.claims[1].source == "§914.02.A Parking Schedule A"


def test_second_failure_salvages_valid_typologies() -> None:
    context = _context_for_district("R2-L")
    calls = {"n": 0}

    def mixed(system: str, user: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"verdict": "best"})
        return json.dumps(
            {
                "judgments": [
                    _judgment("duplex", 8),
                    {"typology": "townhome", "score": "not-a-score"},
                ]
            }
        )

    results = run_zoning_analyst(
        context,
        typologies=[Typology.duplex, Typology.townhome],
        completer=mixed,
    )
    assert calls["n"] == 2
    by_typ = {item.typology: item for item in results}
    assert by_typ[Typology.duplex].score == 8
    assert "Comparative note" in by_typ[Typology.duplex].summary
    assert by_typ[Typology.townhome].score == 0
    assert any("failed to produce valid" in note for note in by_typ[Typology.townhome].cannot_determine)
    assert by_typ[Typology.townhome].claims[0].source == "§911.02 Use Table"
