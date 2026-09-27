from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict

CATALOG_URL = "https://data.wprdc.org/dataset/port-authority-of-allegheny-county-transit-data"
RESOLVED_DATASET = "https://data.wprdc.org/dataset/prt-of-allegheny-county-transit-stops"
RESOURCE_ID = "d6e6ed6e-9220-4a0e-9796-e72d83ce8e7a"
DATASTORE_URL = "https://data.wprdc.org/api/3/action/datastore_search"
GTFS_ARCHIVE = "https://data.wprdc.org/dataset/gtfs-archive"
PAGE_SIZE = 1000
EARTH_M = 6371000.0


class PrtStop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_id: str
    stop_name: str
    stop_lon: float
    stop_lat: float
    mode: str | None
    route_code: str | None
    hood: str | None
    trips_wd: float | None
    from_gtfs: int | None
    feed_version: str | None
    distance_m: float


class PrtStopSlice(BaseModel):
    """Nearest current-schedule PRT stops, derived from GTFS (from_gtfs flag)."""

    model_config = ConfigDict(extra="forbid")

    catalog_url: str
    resolved_url: str
    resource_id: str
    gtfs_archive_url: str
    feed_version: str | None
    nearest: list[PrtStop]
    unique_within_400m: int
    unique_within_800m: int
    unique_within_1500ft: int
    retrieved_on: str
    caveat: str


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(math.sqrt(a))


def fetch_nearest_prt_stops(
    lon: float,
    lat: float,
    *,
    timeout: int = 60,
    max_distance_m: float = 2000.0,
    keep: int = 8,
    retrieved_on: str = "2026-09-27",
) -> PrtStopSlice:
    records = _datastore_all(timeout=timeout)
    best: dict[str, PrtStop] = {}
    feed_version: str | None = None
    for raw in records:
        if feed_version is None and raw.get("feed_version") is not None:
            feed_version = str(raw.get("feed_version"))
        slon, slat = raw.get("stop_lon"), raw.get("stop_lat")
        if slon is None or slat is None:
            continue
        dist = haversine_m(lon, lat, float(slon), float(slat))
        if dist > max_distance_m:
            continue
        stop_id = str(raw.get("stop_id") or "")
        candidate = PrtStop(
            stop_id=stop_id,
            stop_name=str(raw.get("stop_name") or ""),
            stop_lon=float(slon),
            stop_lat=float(slat),
            mode=raw.get("mode"),
            route_code=raw.get("route_code"),
            hood=raw.get("hood"),
            trips_wd=_num(raw.get("trips_wd")),
            from_gtfs=_int(raw.get("from_gtfs")),
            feed_version=str(raw.get("feed_version")) if raw.get("feed_version") is not None else None,
            distance_m=round(dist, 1),
        )
        if stop_id not in best or candidate.distance_m < best[stop_id].distance_m:
            best[stop_id] = candidate
    ranked = sorted(best.values(), key=lambda item: item.distance_m)
    feet_1500_m = 1500 * 0.3048
    return PrtStopSlice(
        catalog_url=CATALOG_URL,
        resolved_url=RESOLVED_DATASET,
        resource_id=RESOURCE_ID,
        gtfs_archive_url=GTFS_ARCHIVE,
        feed_version=feed_version,
        nearest=ranked[:keep],
        unique_within_400m=sum(1 for item in ranked if item.distance_m <= 400),
        unique_within_800m=sum(1 for item in ranked if item.distance_m <= 800),
        unique_within_1500ft=sum(1 for item in ranked if item.distance_m <= feet_1500_m),
        retrieved_on=retrieved_on,
        caveat=(
            "Scheduled GTFS-derived service is not realized reliability. "
            "Catalog slug port-authority-of-allegheny-county-transit-data 404s; "
            "current stops are published as prt-of-allegheny-county-transit-stops "
            f"(resource {RESOURCE_ID}). Historical zips are on gtfs-archive."
        ),
    )


def _datastore_all(*, timeout: int) -> list[dict]:
    records: list[dict] = []
    offset = 0
    while True:
        params = urllib.parse.urlencode(
            {"resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset}
        )
        req = urllib.request.Request(
            DATASTORE_URL + "?" + params,
            headers={"User-Agent": "housing-review/0.1"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload.get("success"):
            raise LookupError(payload.get("error") or "CKAN datastore_search failed")
        page = payload["result"]["records"] or []
        total = int(payload["result"]["total"])
        records.extend(page)
        offset += len(page)
        if offset >= total or not page:
            break
    return records


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
