from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.pro_forma import run_pro_forma_analyst
from housing_review.data.catalog import pro_forma_analyst_sources
from housing_review.data.icc_bvd import cost_for_typology, load_bvd
from housing_review.data.proforma import load_proforma_site_from_path
from housing_review.schemas import AnalystName, Typology

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_icc_bvd_august_2026_type_vb_national() -> None:
    table = load_bvd()
    assert table["table_title"] == "Building Valuation Data – AUGUST 2026"
    assert table["pittsburgh_local_modifier"]["found"] is False
    duplex = cost_for_typology(Typology.duplex)
    assert duplex["occupancy_group"] == "R-3"
    assert duplex["construction_type"] == "VB"
    assert duplex["usd_per_sqft"] == 177.63
    assert duplex["basis"] == "estimated"
    assert "national average" in duplex["citation"].lower()
    apt = cost_for_typology(Typology.apartment)
    assert apt["occupancy_group"] == "R-2"
    assert apt["usd_per_sqft"] == 159.71
    senior = cost_for_typology(Typology.senior_housing)
    assert senior["occupancy_group"] == "R-4"
    assert senior["usd_per_sqft"] == 203.38
    townhome = cost_for_typology(Typology.townhome)
    assert townhome["occupancy_group"] == "R-3"


def test_proforma_fixture_flags_quit_claim_and_land() -> None:
    ctx = load_proforma_site_from_path(FIXTURES / "proforma_0139F00077000000.json")
    assert ctx.site_id == "0139F00077000000"
    assert ctx.assessment.fields["FAIRMARKETLAND"] == 30000
    assert ctx.assessment.fields["USEDESC"] == "TOWNHOUSE"
    assert ctx.sales.parcel_sales[0].likely_arms_length is False
    assert ctx.sales.parcel_sales[0].sale_desc == "QUIT CLAIM"
    assert all(item.likely_arms_length for item in ctx.sales.comparable_valid_sales)
    assert ctx.size_proxy_finished_sf == 1704
    assert any("pittsburgh-specific" in note.lower() for note in ctx.coverage_notes)


def test_pro_forma_sources_log_icc_and_assessments() -> None:
    records = pro_forma_analyst_sources()
    names = {item.name for item in records}
    assert "Allegheny County Property Assessments" in names
    assert "Allegheny County Property Sale Transactions" in names
    assert "ICC Building Valuation Data" in names
    icc = next(item for item in records if "ICC" in item.name)
    assert "August 2026" in icc.notes or "AUGUST 2026" in icc.notes
    assert "modifier" in icc.notes.lower() or "modifier" in icc.does_not_cover.lower()


def test_pro_forma_analyst_validates_mocked_round1() -> None:
    context = load_proforma_site_from_path(FIXTURES / "proforma_0139F00077000000.json")

    def fake(system: str, user: str) -> str:
        assert "Pro Forma Analyst" in system
        assert "177.63" in user
        assert "median_usd" in user
        assert "301000" not in user
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "duplex",
                        "score": 5,
                        "basis": "estimated",
                        "summary": "Directional only; construction cost is a national ICC average.",
                        "cannot_determine": [],
                    }
                ]
            }
        )

    results = run_pro_forma_analyst(context, typologies=[Typology.duplex], completer=fake)
    assert len(results) == 1
    assert results[0].agent is AnalystName.pro_forma_analyst
    assert results[0].score == 5
    icc = next(item for item in results[0].claims if item.basis.value == "estimated")
    assert "177.63" in icc.statement
    assert "Building Valuation Data" in icc.source
    assert any("Financing" in note for note in results[0].cannot_determine)
    assert any("Median price of 8" in c.statement for c in results[0].claims)
    assert any("295500" in c.statement for c in results[0].claims)


def test_pro_forma_adu_keeps_increment_gap_and_estimated_icc() -> None:
    context = load_proforma_site_from_path(FIXTURES / "proforma_0139F00077000000.json")

    def fake(system: str, user: str) -> str:
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "adu",
                        "score": 4,
                        "basis": "estimated",
                        "summary": "Whole-house ICC proxy is not an ADU increment.",
                        "cannot_determine": [],
                    }
                ]
            }
        )

    results = run_pro_forma_analyst(context, typologies=[Typology.adu], completer=fake)
    icc = next(item for item in results[0].claims if "ICC" in item.statement or "occupancy" in item.statement)
    assert icc.basis.value == "estimated"
    assert icc.source == next(
        row["citation"] for row in context.construction_cost if row["typology"] == "adu"
    )
    assert any("FINISHEDLIVINGAREA" in note for note in results[0].cannot_determine)


def test_pro_forma_one_call_all_six() -> None:
    context = load_proforma_site_from_path(FIXTURES / "proforma_0139F00077000000.json")
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
                        "basis": "estimated",
                        "summary": f"note {slug}",
                        "cannot_determine": [],
                    }
                    for i, slug in enumerate(typs)
                ]
            }
        )

    results = run_pro_forma_analyst(context, completer=fake)
    assert calls["n"] == 1
    assert [item.score for item in results] == [1, 2, 3, 4, 5, 6]
    duplex = next(item for item in results if item.typology is Typology.duplex)
    assert duplex.claims[1].source == next(
        row["citation"] for row in context.construction_cost if row["typology"] == "duplex"
    )
    assert duplex.claims[1].basis.value == "estimated"
