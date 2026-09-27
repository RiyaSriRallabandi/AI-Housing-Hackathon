from __future__ import annotations

import json
from pathlib import Path

import pytest

from housing_review.agents.zoning import assert_structured_citations, run_zoning_analyst
from housing_review.data.corpus import citation_contract_for_district, lookup_for_mapped_districts
from housing_review.data.parcels import parcel_from_geojson
from housing_review.data.residential import profile_residential_district
from housing_review.data.site import ZoningSiteContext
from housing_review.data.zoning_code import citations_for_districts
from housing_review.data.zoning_districts import ZoningDistrictHit
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
    lookup = lookup_for_mapped_districts([district_code])
    profile = profile_residential_district(district_code)
    return ZoningSiteContext(
        site_id=parcel.pin,
        parcel=parcel,
        districts=[hit],
        residential_profile=profile,
        overlays=[],
        adu_overlay={"in_adu_overlay": False, "hits": []},
        code_lookup=lookup,
        code_citations=citations_for_districts([hit], profile=profile),
        coverage_notes=["Decision support only — not legal, financial, or zoning advice."],
    )


def _assessment_from_contract(typology: str, row: dict, *, site_id: str = "0139F00077000000") -> dict:
    pmax = row.get("parking_maximum") or ""
    statement = f"Schedule A minimum {row['parking_minimum']}"
    if pmax:
        statement += f", maximum {pmax}"
    return {
        "agent": "zoning_analyst",
        "site_id": site_id,
        "typology": typology,
        "score": 5,
        "basis": "measured",
        "claims": [
            {
                "statement": f"{row['use_names']} status {row['statuses']}",
                "basis": "measured",
                "source": row["use_source"],
            },
            {
                "statement": statement,
                "basis": "measured",
                "source": row["parking_citation"],
            },
        ],
        "cannot_determine": [],
        "summary": "Copied citation_contract fields.",
    }


def _copying_completer(context: ZoningSiteContext):
    def fake(system: str, user: str) -> str:
        start = user.rfind('{"responsible_use"')
        payload = json.loads(user[start:])
        contract = payload["site_context"]["citation_contract"]
        typs = payload["candidate_typologies"]
        items = [_assessment_from_contract(slug, contract[slug], site_id=context.site_id) for slug in typs]
        return json.dumps({"assessments": items})

    return fake


def test_citation_contract_differs_by_district_status_not_by_source() -> None:
    r2 = citation_contract_for_district("R2-L")
    rm = citation_contract_for_district("RM-H")
    for slug in Typology:
        assert r2[slug.value]["use_source"] == rm[slug.value]["use_source"]
        assert r2[slug.value]["parking_citation"] == rm[slug.value]["parking_citation"]
        assert r2[slug.value]["parking_minimum"] == rm[slug.value]["parking_minimum"]
        assert r2[slug.value]["parking_maximum"] == rm[slug.value]["parking_maximum"]
    assert any("blank" in status for status in r2["apartment"]["statuses"])
    assert rm["apartment"]["statuses"][0] == "P"


def test_copying_agent_matches_contract_for_all_typologies_and_districts() -> None:
    report: list[str] = []
    for district in DISTRICTS:
        context = _context_for_district(district)
        contract = context.code_lookup["citation_contract"]
        results = run_zoning_analyst(context, completer=_copying_completer(context))
        assert {item.typology for item in results} == set(Typology)
        assert_structured_citations(results, context.code_lookup)
        report.append(f"\n{district} column={context.code_lookup['use_table_column']}")
        for item in results:
            row = contract[item.typology.value]
            use_claim = next(c for c in item.claims if c.source == row["use_source"])
            park_claim = next(c for c in item.claims if c.source == row["parking_citation"])
            report.append(
                f"  {item.typology.value:24} use_src={use_claim.source!r} "
                f"park_src={park_claim.source!r} "
                f"min={row['parking_minimum']!r} max={row['parking_maximum']!r} "
                f"status={row['statuses']}"
            )
    print("\n".join(report))
    assert len(results) == len(Typology)


def test_invented_use_table_section_is_rejected() -> None:
    context = _context_for_district("RM-H")
    row = context.code_lookup["citation_contract"]["townhome"]
    bad = _assessment_from_contract("townhome", row)
    bad["claims"][0]["source"] = "§911.04A.69 Use Table"

    def fake(system: str, user: str) -> str:
        return json.dumps({"assessments": [bad]})

    with pytest.raises(ValueError, match="permitted-use claim source"):
        run_zoning_analyst(context, typologies=[Typology.townhome], completer=fake)


def test_parking_claim_without_maximum_is_rejected() -> None:
    context = _context_for_district("R2-L")
    row = context.code_lookup["citation_contract"]["townhome"]
    bad = _assessment_from_contract("townhome", row)
    bad["claims"][1]["statement"] = f"Schedule A minimum {row['parking_minimum']}"

    def fake(system: str, user: str) -> str:
        return json.dumps({"assessments": [bad]})

    with pytest.raises(ValueError, match="parking statement missing"):
        run_zoning_analyst(context, typologies=[Typology.townhome], completer=fake)
