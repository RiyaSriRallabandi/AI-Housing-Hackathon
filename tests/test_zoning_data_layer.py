from __future__ import annotations

from pathlib import Path

from housing_review.data.catalog import zoning_analyst_sources
from housing_review.data.parcels import _where_clause, parcel_from_geojson
from housing_review.data.site import load_zoning_site_from_fixtures
from housing_review.data.zoning_districts import ZoningDistrictLayer

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_source_log_has_retrieval_dates_and_gaps() -> None:
    records = zoning_analyst_sources()
    names = {r.name for r in records}
    assert "Pittsburgh Zoning Districts (GIS)" in names
    assert "Pittsburgh Zoning Code (Title 9)" in names
    assert "Allegheny County Parcel Boundaries" in names
    code = next(r for r in records if "Zoning Code" in r.name)
    assert "Cloudflare" in code.notes or "Cloudflare" in code.caveat
    assert "911.02" in code.notes or "911" in code.notes
    assert "ecode360.com/45474054" in code.notes or "ecode360.com/45474054" in code.resolved_url
    assert all(r.retrieved_on.isoformat() == "2026-09-26" for r in records)


def test_parcel_where_clause() -> None:
    assert _where_clause("0139F00077000000") == "PIN='0139F00077000000'"
    assert _where_clause("139-F-77") == "MAPBLOCKLOT='139-F-77'"


def test_r2l_fixture_contains_sample_parcel_centroid() -> None:
    layer = ZoningDistrictLayer.from_path(FIXTURES / "zoning_r2l_sample.geojson")
    parcel = parcel_from_geojson(
        __import__("json").loads((FIXTURES / "parcel_0139F00077000000.geojson").read_text()),
        "0139F00077000000",
    )
    hits = layer.districts_at(parcel.lon, parcel.lat)
    assert len(hits) == 1
    assert hits[0].district_code == "R2-L"
    assert hits[0].code_url and "ecode360.com" in hits[0].code_url


def test_site_context_from_fixtures_does_not_invent_code_text() -> None:
    ctx = load_zoning_site_from_fixtures(
        FIXTURES / "parcel_0139F00077000000.geojson",
        FIXTURES / "zoning_r2l_sample.geojson",
    )
    assert ctx.site_id == "0139F00077000000"
    assert ctx.districts[0].district_code == "R2-L"
    assert ctx.residential_profile is not None
    assert ctx.residential_profile.use_subdistrict == "R2"
    assert ctx.residential_profile.min_lot_sf == 3000
    assert ctx.code_citations[0].retrieval_status == "retrieved_browser"
    assert ctx.code_lookup is not None
    assert ctx.code_lookup["use_table_column"] == "R2"
    two = next(
        row for row in ctx.code_lookup["use_permissions_this_column"] if row["use"].startswith("Two-Unit")
    )
    assert two["status"] == "P"
    multi = next(
        row for row in ctx.code_lookup["use_permissions_this_column"] if row["use"].startswith("Multi-Unit")
    )
    assert "blank" in multi["status"] or multi["status"] == ""
    assert any("not legal" in note.lower() for note in ctx.coverage_notes)


def test_residential_profile_r2_l() -> None:
    from housing_review.data.residential import profile_residential_district

    profile = profile_residential_district("R2-L")
    assert profile is not None
    assert profile.use_label == "Two-Unit Residential"
    assert profile.min_lot_sf == 3000
    assert "40 ft" in profile.standards["max_height"]


def test_demo_site_is_brookline_r2l() -> None:
    from housing_review.data.demo_site import demo_site_record

    record = demo_site_record()
    assert record["pin"] == "0139F00077000000"
    assert record["zoning_district"] == "R2-L"
    assert record["address"]["municipality"] == "PITTSBURGH"
    assert "170" in record["address"]["full"]
    assert record["placeholders"]["census_tract_geoid"] == "42003191800"
    assert any("not legal" in item.lower() for item in record["known_limitations"])


def test_vh_has_no_invented_lot_size() -> None:
    from housing_review.data.residential import profile_residential_district

    profile = profile_residential_district("RM-VH")
    assert profile is not None
    assert profile.min_lot_sf is None
    assert any("minimum lot size" in n.lower() for n in profile.notes)


def test_use_table_lookup_is_district_dynamic() -> None:
    from housing_review.data.corpus import permissions_for_district, use_table_column_key

    assert use_table_column_key("R2-L") == "R2"
    assert use_table_column_key("RM-H") == "RM"
    assert use_table_column_key("NDO") == "NDO"
    r2_two = next(row for row in permissions_for_district("R2-L") if row["use"].startswith("Two-Unit"))
    r1d_two = next(row for row in permissions_for_district("R1D-L") if row["use"].startswith("Two-Unit"))
    r2_multi = next(row for row in permissions_for_district("R2-L") if row["use"].startswith("Multi-Unit"))
    rm_multi = next(row for row in permissions_for_district("RM-H") if row["use"].startswith("Multi-Unit"))
    assert r2_two["status"] == "P"
    assert "blank" in r1d_two["status"]
    assert "blank" in r2_multi["status"]
    assert rm_multi["status"] == "P"


def test_parking_excerpt_is_schedule_a_not_toc() -> None:
    from housing_review.data.corpus import parking_schedule_residential_excerpt

    excerpt = parking_schedule_residential_excerpt()
    assert "Single-Unit, Detached" in excerpt
    assert "1 per unit" in excerpt
    assert "Two-Unit" in excerpt
    assert "Off-Street Parking Exemption" not in excerpt


def test_brief_typology_maps_to_title9_names() -> None:
    from housing_review.data.corpus import TYPOLOGY_TITLE9, lookup_for_mapped_districts

    names = lookup_for_mapped_districts(["R2-L"])["typology_title9_names"]
    assert names["townhome"]["title9_use"] == "Single-Unit Attached Residential"
    assert "townhouse" not in names["townhome"]["title9_use"].lower()
    assert names["duplex"]["title9_use"] == "Two-Unit Residential"
    assert names["apartment"]["title9_use"] == "Multi-Unit Residential"
    assert names["detached_single_family"]["title9_use"] == "Single-Unit Detached Residential"
    assert TYPOLOGY_TITLE9["adu"]["title9_use"].startswith("Accessory")
