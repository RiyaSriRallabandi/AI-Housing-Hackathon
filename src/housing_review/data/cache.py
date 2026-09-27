from __future__ import annotations

import json
import urllib.request
from pathlib import Path

WPRDC_ZONING_GEOJSON = (
    "https://data.wprdc.org/dataset/01773197-baba-4f5e-aa77-ae87a04afafc/"
    "resource/6127f35e-f36b-4a53-80b3-f4409609e9df/download/zoning.geojson"
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_PATH = REPO_ROOT / "data" / "cache" / "pittsburgh_zoning_districts.geojson"


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path, *, timeout: int = 120) -> Path:
    ensure_dir(dest)
    req = urllib.request.Request(url, headers={"User-Agent": "housing-review/0.1 (hackathon decision-support)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())
    return dest


def load_geojson(path: Path) -> dict:
    with path.open() as handle:
        data = json.load(handle)
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"{path} is not a GeoJSON FeatureCollection")
    return data


def cached_zoning_geojson(*, download_if_missing: bool = True) -> Path:
    if CACHE_PATH.exists():
        return CACHE_PATH
    if not download_if_missing:
        raise FileNotFoundError(f"Zoning cache missing: {CACHE_PATH}")
    ensure_dir(CACHE_PATH)
    return download_file(WPRDC_ZONING_GEOJSON, CACHE_PATH)
