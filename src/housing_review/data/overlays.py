from __future__ import annotations

import json
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict

# Layers shown on the City's official Zoning Map Instant App (webmap ee49e1c537fc4c458b087356d2104f4c).
OFFICIAL_ZONING_MAP_APP = (
    "https://pittsburghpa.maps.arcgis.com/apps/instant/sidebar/index.html"
    "?appid=4bb79ea64bf848b3a0560e3856efeccb"
)

OVERLAY_LAYERS: list[tuple[str, str]] = [
    (
        "inclusionary_housing",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/InclusionaryHousingOverlayDistrict/FeatureServer/0",
    ),
    (
        "height_reduction_zone",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/HeightReductionZone_ZoningOverlay/FeatureServer/0",
    ),
    (
        "baum_centre_overlay",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebBaumCentreOverlay/FeatureServer/0",
    ),
    (
        "north_side_commercial_parking",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWEBNorthSideCommercialParkingOverlay/FeatureServer/0",
    ),
    (
        "parking_reduction",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebParkingReductionOverlay/FeatureServer/0",
    ),
    (
        "major_transit_buffer",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebMajorTransitBuffer/FeatureServer/0",
    ),
    (
        "historic_districts",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebCHDHistoricDistricts/FeatureServer/0",
    ),
    (
        "steep_slopes_25pct",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebSlope25/FeatureServer/0",
    ),
    (
        "floodplain_fema_2026",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/FEMA_2026/FeatureServer/0",
    ),
    (
        "zoning_overlays_combined",
        "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebZoningOverlays/FeatureServer/0",
    ),
]

ADU_OVERLAY_LAYER = (
    "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/PGHWebZoningOverlays/FeatureServer/0"
)


class OverlayHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: str
    source_url: str
    attributes: dict
    official_map: str = OFFICIAL_ZONING_MAP_APP


def overlays_at(lon: float, lat: float, *, timeout: int = 30) -> list[OverlayHit]:
    hits: list[OverlayHit] = []
    for layer_id, base in OVERLAY_LAYERS:
        params = {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": 5,
        }
        url = base + "/query?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("error"):
            continue
        for feature in payload.get("features") or []:
            attrs = feature.get("attributes") or {}
            hits.append(OverlayHit(layer_id=layer_id, source_url=base, attributes=attrs))
    return hits


def _query_features(base: str, lon: float, lat: float, *, where: str = "1=1", timeout: int = 30) -> list[dict]:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "where": where,
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": 25,
    }
    url = base + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("error"):
        return []
    return [feature.get("attributes") or {} for feature in payload.get("features") or []]


def adu_overlay_at(lon: float, lat: float, *, timeout: int = 30) -> dict:
    """Live point-in-polygon check for an Accessory Dwelling Unit overlay.

    §912.08 defines the ADU Overlay as coincidental with the Zoning District Map.
    This is a per-query GIS check, not a stored fact about any demo parcel.
    """
    where = (
        "overlay LIKE '%ADU%' OR overlay LIKE '%Accessory Dwelling%' "
        "OR criteria LIKE '%ADU%' OR criteria LIKE '%Accessory Dwelling%'"
    )
    attrs = _query_features(ADU_OVERLAY_LAYER, lon, lat, where=where, timeout=timeout)
    return {
        "in_adu_overlay": bool(attrs),
        "layer_url": ADU_OVERLAY_LAYER,
        "official_map": OFFICIAL_ZONING_MAP_APP,
        "query": where,
        "hits": attrs,
        "note": (
            "Live intersect against PGHWebZoningOverlays for ADU / Accessory Dwelling "
            "labels. A false result means no matching overlay polygon at this point "
            "in the published layer, not a hardcoded site conclusion."
        ),
    }
