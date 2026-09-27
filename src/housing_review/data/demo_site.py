from __future__ import annotations

import json
from pathlib import Path

from housing_review.data.site import ZoningSiteContext, load_zoning_site

DEMO_SITE_PATH = Path(__file__).resolve().parents[3] / "data" / "demo_site.json"


def demo_site_record() -> dict:
    return json.loads(DEMO_SITE_PATH.read_text())


def demo_site_id() -> str:
    return str(demo_site_record()["site_id"])


def load_demo_zoning_site(*, include_overlays: bool = True) -> ZoningSiteContext:
    """Load the Brookline working demo parcel. Overlay queries need the network."""
    record = demo_site_record()
    ctx = load_zoning_site(record["pin"], include_overlays=include_overlays)
    ctx.coverage_notes.extend(record.get("known_limitations") or [])
    # de-dupe while preserving order
    ctx.coverage_notes = list(dict.fromkeys(ctx.coverage_notes))
    return ctx
