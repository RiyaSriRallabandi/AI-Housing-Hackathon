from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.corpus import lookup_for_mapped_districts
from housing_review.data.overlays import OverlayHit, adu_overlay_at, overlays_at
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
    adu_overlay: dict | None = None
    code_lookup: dict | None = None
    code_citations: list[ZoningCodeCitation]
    coverage_notes: list[str] = Field(default_factory=list)


def load_zoning_site(
    identifier: str,
    *,
    zoning_layer: ZoningDistrictLayer | None = None,
    parcel: ParcelRecord | None = None,
    include_overlays: bool = True,
) -> ZoningSiteContext:
    parcel = parcel or lookup_parcel(identifier)
    layer = zoning_layer or ZoningDistrictLayer.from_cache()
    districts = layer.districts_at(parcel.lon, parcel.lat)
    primary = districts[0] if districts else None
    profile = profile_residential_district(primary.district_code) if primary else None
    overlays = overlays_at(parcel.lon, parcel.lat) if include_overlays else []
    adu = adu_overlay_at(parcel.lon, parcel.lat) if include_overlays else None
    lookup = lookup_for_mapped_districts([item.district_code for item in districts])
    notes = [
        "Decision support only — not legal, financial, or zoning advice.",
        "Base district is from City zoning GIS (also the official Zoning Map app).",
        "Use permissions come from the §911.02 column for this site's mapped district, looked up from the full Use Table corpus.",
        "ADU Overlay membership is a live GIS intersect, not a stored fact about this parcel.",
        "Official code host: https://ecode360.com/45474054 (Title 9).",
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
        adu_overlay=adu,
        code_lookup=lookup,
        code_citations=citations_for_districts(districts, profile=profile),
        coverage_notes=notes,
    )


def load_zoning_site_from_fixtures(parcel_geojson: Path, zoning_geojson: Path) -> ZoningSiteContext:
    import json

    payload = json.loads(parcel_geojson.read_text())
    parcel = parcel_from_geojson(payload, parcel_geojson.name)
    layer = ZoningDistrictLayer.from_path(zoning_geojson)
    return load_zoning_site(parcel.pin, zoning_layer=layer, parcel=parcel, include_overlays=False)
