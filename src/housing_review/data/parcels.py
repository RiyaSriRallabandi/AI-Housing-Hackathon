from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict
from shapely.geometry import shape

PARCEL_QUERY_URL = (
    "https://gisdata.alleghenycounty.us/arcgis/rest/services/OPENDATA/Parcels/MapServer/0/query"
)


class ParcelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: str
    map_block_lot: str | None
    muni_code: int | None
    acreage: float | None
    lon: float
    lat: float
    geometry: dict
    source: str = PARCEL_QUERY_URL


class ParcelNotFound(LookupError):
    pass


def lookup_parcel(identifier: str, *, timeout: int = 60) -> ParcelRecord:
    """Look up a parcel by PIN (e.g. 0139F00077000000) or map-block-lot (e.g. 139-F-77)."""
    where = _where_clause(identifier)
    params = {
        "where": where,
        "outFields": "PIN,MAPBLOCKLOT,MUNICODE,CALCACREAGE,OBJECTID",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    url = PARCEL_QUERY_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return parcel_from_geojson(payload, identifier)


def parcel_from_geojson(payload: dict, identifier: str) -> ParcelRecord:
    features = payload.get("features") or []
    if not features:
        raise ParcelNotFound(f"No parcel found for {identifier!r}")
    feature = features[0]
    props = feature.get("properties") or {}
    geom = feature.get("geometry")
    if not geom:
        raise ParcelNotFound(f"Parcel {identifier!r} has no geometry")
    centroid = shape(geom).centroid
    return ParcelRecord(
        pin=str(props.get("PIN") or identifier),
        map_block_lot=props.get("MAPBLOCKLOT"),
        muni_code=props.get("MUNICODE"),
        acreage=props.get("CALCACREAGE"),
        lon=float(centroid.x),
        lat=float(centroid.y),
        geometry=geom,
    )


def lookup_parcel_at(lon: float, lat: float, *, timeout: int = 60) -> ParcelRecord:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "PIN,MAPBLOCKLOT,MUNICODE,CALCACREAGE,OBJECTID",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
    }
    url = PARCEL_QUERY_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return parcel_from_geojson(payload, f"point({lon},{lat})")


def _where_clause(identifier: str) -> str:
    raw = identifier.strip().upper()
    if re.fullmatch(r"\d+[A-Z]-\d+", raw):
        return f"MAPBLOCKLOT='{raw}'"
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    if re.fullmatch(r"\d{4}[A-Z]\d+", compact):
        pin = compact.ljust(16, "0")
        return f"PIN='{pin}'"
    if re.fullmatch(r"\d+[A-Z]\d+", compact):
        # e.g. 139F77 → 139-F-77
        match = re.fullmatch(r"(\d+)([A-Z])(\d+)", compact)
        assert match is not None
        mbl = f"{int(match.group(1))}-{match.group(2)}-{int(match.group(3))}"
        return f"MAPBLOCKLOT='{mbl}'"
    raise ValueError(f"Unrecognized parcel identifier: {identifier!r}")
