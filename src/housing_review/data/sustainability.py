from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.overlays import OVERLAY_URLS, query_named_overlay
from housing_review.data.prt_stops import PrtStopSlice, fetch_nearest_prt_stops

STRICT = ConfigDict(extra="forbid")
DEMO_PIN = "0139F00077000000"
FEMA_CATALOG = "https://www.fema.gov/flood-maps/national-flood-hazard-layer"
FEMA_LAYER = OVERLAY_URLS["floodplain_fema_2026"]
SLOPE_LAYER = OVERLAY_URLS["steep_slopes_25pct"]
TRANSIT_BUFFER_LAYER = OVERLAY_URLS["major_transit_buffer"]


class FloodScreen(BaseModel):
    model_config = STRICT

    layer_covers_point: bool
    fld_zone: str | None
    zone_subtype: str | None
    sfha_tf: str | None
    in_sfha: bool | None
    attributes: dict
    source_url: str
    catalog_url: str
    caveat: str


class SlopeScreen(BaseModel):
    model_config = STRICT

    flagged: bool
    attributes: dict
    source_url: str
    caveat: str


class TransitBufferScreen(BaseModel):
    model_config = STRICT

    in_1500ft_major_transit_buffer: bool
    source_url: str
    note: str


class SustainabilitySiteContext(BaseModel):
    """Transit + flood/slope screening for the Sustainability Analyst. Not a flood determination."""

    model_config = STRICT

    site_id: str
    lon: float
    lat: float
    flood: FloodScreen
    steep_slope_25pct: SlopeScreen
    major_transit_buffer: TransitBufferScreen
    prt: PrtStopSlice
    coverage_notes: list[str] = Field(default_factory=list)


def load_sustainability_site(
    lon: float,
    lat: float,
    *,
    site_id: str = DEMO_PIN,
    prt: PrtStopSlice | None = None,
    timeout: int = 60,
) -> SustainabilitySiteContext:
    flood_hits = query_named_overlay("floodplain_fema_2026", lon, lat, timeout=timeout)
    slope_hits = query_named_overlay("steep_slopes_25pct", lon, lat, timeout=timeout)
    buffer_hits = query_named_overlay("major_transit_buffer", lon, lat, timeout=timeout)
    flood_attrs = flood_hits[0] if flood_hits else {}
    sfha_raw = str(flood_attrs.get("SFHA_TF") or "").upper()
    in_sfha: bool | None
    if not flood_hits:
        in_sfha = None
    elif sfha_raw in {"T", "TRUE", "Y", "YES"}:
        in_sfha = True
    elif sfha_raw in {"F", "FALSE", "N", "NO"}:
        in_sfha = False
    else:
        in_sfha = None
    flood = FloodScreen(
        layer_covers_point=bool(flood_hits),
        fld_zone=flood_attrs.get("FLD_ZONE") or flood_attrs.get("ZONE"),
        zone_subtype=flood_attrs.get("ZONE_SUBTY"),
        sfha_tf=flood_attrs.get("SFHA_TF"),
        in_sfha=in_sfha,
        attributes={key: flood_attrs.get(key) for key in ("FLD_ZONE", "ZONE_SUBTY", "SFHA_TF", "STATIC_BFE", "DFIRM_ID") if flood_attrs},
        source_url=FEMA_LAYER,
        catalog_url=FEMA_CATALOG,
        caveat=(
            "City FEMA_2026 overlay is the retrieved NFHL-style layer on the official Zoning Map. "
            "Not a substitute for a formal flood determination. Zone X coverage is still a map "
            "designation; SFHA_TF=F means not in the Special Flood Hazard Area."
        ),
    )
    slope = SlopeScreen(
        flagged=bool(slope_hits),
        attributes=slope_hits[0] if slope_hits else {},
        source_url=SLOPE_LAYER,
        caveat=(
            "25%+ slope overlay is screening-level only (Useful catalog row; also on the official map). "
            "Not a geotechnical survey."
        ),
    )
    buffer = TransitBufferScreen(
        in_1500ft_major_transit_buffer=bool(buffer_hits),
        source_url=TRANSIT_BUFFER_LAYER,
        note=(
            "City 1,500 ft major-transit buffer is a zoning overlay, not a walk-distance to the "
            "nearest PRT stop. A miss here can still have nearby scheduled service."
        ),
    )
    prt = prt or fetch_nearest_prt_stops(lon, lat, timeout=timeout)
    return SustainabilitySiteContext(
        site_id=site_id,
        lon=lon,
        lat=lat,
        flood=flood,
        steep_slope_25pct=slope,
        major_transit_buffer=buffer,
        prt=prt,
        coverage_notes=_notes(flood, slope, prt),
    )


def load_sustainability_site_from_path(path: Path) -> SustainabilitySiteContext:
    return SustainabilitySiteContext.model_validate(json.loads(path.read_text()))


def _notes(flood: FloodScreen, slope: SlopeScreen, prt: PrtStopSlice) -> list[str]:
    return [
        "Decision support only — not legal, financial, or zoning advice.",
        flood.caveat,
        slope.caveat,
        prt.caveat,
        "Carbon / per-unit infrastructure claims must be generic typology-level direction only, "
        "basis estimated — not a site LCA or measured emissions.",
        "Do not treat the 1,500 ft major-transit overlay as the only transit measure; cite PRT stops.",
        "PA DEP eMapPA and EPA EJScreen (Useful) were not retrieved.",
    ]
