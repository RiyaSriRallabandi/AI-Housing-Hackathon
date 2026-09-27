from __future__ import annotations

import json
import urllib.parse
import urllib.request

from pydantic import BaseModel, ConfigDict

CHAS_LAYER = (
    "https://services.arcgis.com/VTyQ9soqVukalItT/ArcGIS/rest/services/"
    "ACS_5YR_ESTIMATES_CHAS_TRACT/FeatureServer/1"
)
CHAS_CATALOG = "https://www.huduser.gov/portal/datasets/cp.html"
CHAS_VINTAGE = "2013-2017"
CHAS_LATEST_HUD_RELEASE = "2018-2022 (HUD announced 2025-12-23)"
OUT_FIELDS = (
    "GEOID,NAME,STATE,COUNTY,"
    "T2_EST1,T8_CB,T8_CB50,T8_CB_PCT,T8_CB50_PCT,"
    "T8_LE30,T8_LE30_CB,T8_LE30_CB50,T8_LE30_CB_PCT,T8_LE30_CB50_PCT,T8_LE30_PCT,"
    "T8_LE50,T8_LE50_CB,T8_LE50_CB50,T8_LE50_CB_PCT,T8_LE50_CB50_PCT,T8_LE50_PCT,"
    "T8_LE80,T8_LE80_CB,T8_LE80_CB50,T8_LE80_CB_PCT,T8_LE80_CB50_PCT,T8_LE80_PCT,"
    "T8_LE100,T8_LE100_PCT,"
    "T8_GT30_LE50,T8_GT50_LE80,T8_GT80_LE100,T8_GT100,"
    "T8_GT30_LE50_CB,T8_GT50_LE80_CB,T8_GT80_LE100_CB,"
    "T8_GT30_LE50_CB50,T8_GT50_LE80_CB50,T8_GT80_LE100_CB50"
)


class ChasNotFound(LookupError):
    pass


class ChasTractSlice(BaseModel):
    """HUD CHAS Table 8-style cost-burden counts for one census tract."""

    model_config = ConfigDict(extra="forbid")

    geoid: str
    tract_name: str
    vintage: str
    occupied_households: float | None
    cost_burden_gt_30_count: float | None
    cost_burden_gt_30_pct: float | None
    cost_burden_gt_50_count: float | None
    cost_burden_gt_50_pct: float | None
    hamfi_le_30_count: float | None
    hamfi_le_30_cost_burden_pct: float | None
    hamfi_le_50_count: float | None
    hamfi_le_80_count: float | None
    fields: dict
    source_url: str
    catalog_url: str
    retrieved_on: str
    vintage_note: str
    caveat: str


def fetch_chas_tract(geoid: str, *, timeout: int = 60, retrieved_on: str = "2026-09-27") -> ChasTractSlice:
    params = {
        "where": f"GEOID='{geoid}'",
        "outFields": OUT_FIELDS,
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": 1,
    }
    url = CHAS_LAYER + "/query?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("error"):
        raise ChasNotFound(str(payload["error"]))
    features = payload.get("features") or []
    if not features:
        raise ChasNotFound(f"No CHAS tract row for GEOID={geoid!r}")
    raw = features[0].get("attributes") or {}
    vintage_note = (
        f"Layer date of coverage is {CHAS_VINTAGE} ACS/CHAS. HUD's most recent CHAS "
        f"release is {CHAS_LATEST_HUD_RELEASE}. This tract extract is older than that release."
    )
    return ChasTractSlice(
        geoid=str(raw.get("GEOID") or geoid),
        tract_name=str(raw.get("NAME") or ""),
        vintage=CHAS_VINTAGE,
        occupied_households=_num(raw.get("T2_EST1")),
        cost_burden_gt_30_count=_num(raw.get("T8_CB")),
        cost_burden_gt_30_pct=_num(raw.get("T8_CB_PCT")),
        cost_burden_gt_50_count=_num(raw.get("T8_CB50")),
        cost_burden_gt_50_pct=_num(raw.get("T8_CB50_PCT")),
        hamfi_le_30_count=_num(raw.get("T8_LE30")),
        hamfi_le_30_cost_burden_pct=_num(raw.get("T8_LE30_CB_PCT")),
        hamfi_le_50_count=_num(raw.get("T8_LE50")),
        hamfi_le_80_count=_num(raw.get("T8_LE80")),
        fields={key: raw.get(key) for key in raw},
        source_url=CHAS_LAYER,
        catalog_url=CHAS_CATALOG,
        retrieved_on=retrieved_on,
        vintage_note=vintage_note,
        caveat=(
            "CHAS is based on multi-year ACS; this layer lags HUD's current download. "
            "It shows current (vintage-period) cost burden, not displacement from a new building."
        ),
    )


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
