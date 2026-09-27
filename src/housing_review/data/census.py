from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
CENSUS_TABLE_URL = "https://data.census.gov/api/access/data/table"
USER_AGENT = "housing-review/0.1 (hackathon decision-support)"

ACS_2023_TABLES = (
    "ACSDT5Y2023.B01003",
    "ACSDT5Y2023.B25002",
    "ACSDT5Y2023.B25010",
    "ACSDT5Y2023.B25024",
    "ACSDT5Y2023.B11001",
    "ACSDT5Y2023.B01001",
)
ACS_2018_TABLES = (
    "ACSDT5Y2018.B01003",
    "ACSDT5Y2018.B25002",
    "ACSDT5Y2018.B25010",
    "ACSDT5Y2018.B11001",
)
DEC_2020_TABLES = ("DECENNIALPL2020.P1", "DECENNIALPL2020.H1")


def _get_json(url: str, *, timeout: int = 60) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def geocode_tract(lon: float, lat: float) -> dict[str, str]:
    """Resolve a point to a Census tract via the TIGER-backed Census Geocoder."""
    url = GEOCODER_URL + "?" + urllib.parse.urlencode(
        {
            "x": lon,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }
    )
    payload = _get_json(url)
    tracts = payload["result"]["geographies"].get("Census Tracts") or []
    if not tracts:
        raise LookupError(f"No Census tract at lon={lon} lat={lat}")
    tract = tracts[0]
    return {
        "geoid": str(tract["GEOID"]),
        "state": str(tract["STATE"]),
        "county": str(tract["COUNTY"]),
        "tract": str(tract["TRACT"]),
        "name": str(tract["NAME"]),
        "source_url": url,
    }


def fetch_census_table(table_id: str, geoid: str) -> dict[str, Any]:
    """One-tract table from data.census.gov (no Census API key). api.census.gov now requires a key."""
    url = CENSUS_TABLE_URL + "?" + urllib.parse.urlencode({"g": f"1400000US{geoid}", "id": table_id})
    payload = _get_json(url)
    rows = payload["response"]["data"]
    if not rows or len(rows) < 2:
        raise LookupError(f"No rows for {table_id} GEOID {geoid}")
    return dict(zip(rows[0], rows[1], strict=False))


def fetch_demographic_tables(geoid: str) -> dict[str, dict[str, Any]]:
    tables = {}
    for table_id in (*ACS_2023_TABLES, *ACS_2018_TABLES, *DEC_2020_TABLES):
        tables[table_id] = fetch_census_table(table_id, geoid)
    return tables
