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
    payload = [
        {
            "agent": "pro_forma_analyst",
            "site_id": "0139F00077000000",
            "typology": "duplex",
            "score": 5,
            "basis": "estimated",
            "claims": [
                {
                    "statement": "ICC BVD August 2026 R-3 Type VB is $177.63/sf national average.",
                    "basis": "estimated",
                    "source": "ICC Building Valuation Data – AUGUST 2026 occupancy R-3 type VB",
                    "confidence_note": "Not Pittsburgh-specific.",
                }
            ],
            "cannot_determine": ["Financing terms."],
            "summary": "Directional only; construction cost is a national ICC average.",
        }
    ]

    def fake(system: str, user: str) -> str:
        assert "Pro Forma Analyst" in system
        assert "177.63" in user
        return json.dumps({"assessments": payload})

    results = run_pro_forma_analyst(context, typologies=[Typology.duplex], completer=fake)
    assert len(results) == 1
    assert results[0].agent is AnalystName.pro_forma_analyst
    assert results[0].basis.value == "estimated"
    assert results[0].score == 5
