from __future__ import annotations

import json
from pathlib import Path

from housing_review.data.site import ZoningSiteContext, load_zoning_site

DEMO_SITE_PATH = Path(__file__).resolve().parents[3] / "data" / "demo_site.json"
PARCEL_GEOJSON = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "parcel_0139F00077000000.geojson"
)


def demo_site_record() -> dict:
    return json.loads(DEMO_SITE_PATH.read_text())


def demo_site_id() -> str:
    return str(demo_site_record()["site_id"])


def demo_site_map_payload() -> dict:
    record = demo_site_record()
    geo = json.loads(PARCEL_GEOJSON.read_text())
    feature = geo["features"][0]
    pin = str(record["pin"])
    address = record["address"]["full"]
    neighborhood = record["neighborhood"]["name"]
    acres = record["lot_acreage"]
    district = record["zoning_district"]
    return {
        "site_id": pin,
        "address": address,
        "neighborhood": neighborhood,
        "zoning_district": district,
        "lot_acreage": acres,
        "map_block_lot": record["map_block_lot"],
        "geometry": feature["geometry"],
        "map_title": f"Parcel map of {address}",
        "map_description": (
            f"Outline of Allegheny County parcel {pin}, map-block-lot "
            f"{record['map_block_lot']}, about {acres} acres at {address} in "
            f"{neighborhood}. City zoning GIS maps this lot as {district} "
            "(two-unit, low density)."
        ),
    }


def load_demo_zoning_site(*, include_overlays: bool = True) -> ZoningSiteContext:
    """Load the Brookline working demo parcel. Overlay queries need the network."""
    record = demo_site_record()
    ctx = load_zoning_site(record["pin"], include_overlays=include_overlays)
    ctx.coverage_notes.extend(record.get("known_limitations") or [])
    # de-dupe while preserving order
    ctx.coverage_notes = list(dict.fromkeys(ctx.coverage_notes))
    return ctx
