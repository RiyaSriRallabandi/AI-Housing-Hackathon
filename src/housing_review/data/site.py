from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.overlays import OverlayHit, overlays_at
from housing_review.data.parcels import ParcelRecord, lookup_parcel, parcel_from_geojson
from housing_review.data.residential import ResidentialDistrictProfile, profile_residential_district
from housing_review.data.zoning_code import ZoningCodeCitation, citations_for_districts
from housing_review.data.zoning_districts import ZoningDistrictHit, ZoningDistrictLayer


class ZoningSiteContext(BaseModel):
    """Everything the Zoning Analyst may ground claims in for one site — GIS + citations, not a verdict."""

    model_config = ConfigDict(extra="forbid")

    site_id: str
    parcel: ParcelRecord
    districts: list[ZoningDistrictHit]
    residential_profile: ResidentialDistrictProfile | None = None
    overlays: list[OverlayHit] = Field(default_factory=list)
    code_citations: list[ZoningCodeCitation]
    coverage_notes: list[str] = Field(default_factory=list)


def load_zoning_site(
    identifier: str,
    *,
    zoning_layer: ZoningDistrictLayer | None = None,
    parcel: ParcelRecord | None = None,
    include_overlays: bool = False,
) -> ZoningSiteContext:
    parcel = parcel or lookup_parcel(identifier)
    layer = zoning_layer or ZoningDistrictLayer.from_cache()
    districts = layer.districts_at(parcel.lon, parcel.lat)
    primary = districts[0] if districts else None
    profile = profile_residential_district(primary.district_code) if primary else None
    overlays = overlays_at(parcel.lon, parcel.lat) if include_overlays else []
    notes = [
        "Decision support only — not legal, financial, or zoning advice.",
        "Base district is from City zoning GIS (also the official Zoning Map app). Overlays listed only when include_overlays=True.",
        "§911.02 Use Table and Chapter 912 accessory rules were not retrieved as structured tables.",
        "Official code host: https://ecode360.com/45474054 (Title 9); City zoning page: https://www.pittsburghpa.gov/Business-Development/City-Planning/Zoning",
    ]
    if any(d.status and d.status != "Approved" for d in districts):
        notes.append("At least one intersecting zoning polygon is not status=Approved.")
    if any(d.district_code == "MTOBOR" for d in districts):
        notes.append("Point intersects Mount Oliver Borough, which is outside City of Pittsburgh zoning.")
    if any(hit.layer_id == "steep_slopes_25pct" for hit in overlays):
        notes.append("Official map Environment layer flags 25%+ slope at this point — screening only, not a geotechnical determination.")
    return ZoningSiteContext(
        site_id=parcel.pin,
        parcel=parcel,
        districts=districts,
        residential_profile=profile,
        overlays=overlays,
        code_citations=citations_for_districts(districts, profile=profile),
        coverage_notes=notes,
    )


def load_zoning_site_from_fixtures(parcel_geojson: Path, zoning_geojson: Path) -> ZoningSiteContext:
    import json

    payload = json.loads(parcel_geojson.read_text())
    parcel = parcel_from_geojson(payload, parcel_geojson.name)
    layer = ZoningDistrictLayer.from_path(zoning_geojson)
    return load_zoning_site(parcel.pin, zoning_layer=layer, parcel=parcel)
