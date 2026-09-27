from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from housing_review.data.cache import cached_zoning_geojson, load_geojson


class ZoningDistrictHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    district_code: str
    full_zoning_type: str | None
    legend_type: str | None
    status: str | None
    code_url: str | None = Field(description="eCode360 (or other) URL from the GIS municode field")
    object_id: int | None = None
    source_layer: str = "Pittsburgh Zoning Districts (WPRDC GeoJSON)"


class ZoningDistrictLayer:
    """Point-in-polygon lookup against the City zoning district map."""

    def __init__(self, geojson: dict) -> None:
        self._geoms = []
        self._hits: list[ZoningDistrictHit] = []
        for feature in geojson.get("features") or []:
            props = feature.get("properties") or {}
            geom = feature.get("geometry")
            if not geom:
                continue
            code = props.get("zon_new")
            if not code:
                continue
            self._geoms.append(shape(geom))
            self._hits.append(
                ZoningDistrictHit(
                    district_code=str(code).strip(),
                    full_zoning_type=_clean(props.get("full_zoning_type")),
                    legend_type=_clean(props.get("legendtype")),
                    status=_clean(props.get("status")),
                    code_url=_clean(props.get("municode")),
                    object_id=props.get("OBJECTID"),
                )
            )
        self._tree = STRtree(self._geoms)

    @classmethod
    def from_path(cls, path: Path) -> ZoningDistrictLayer:
        return cls(load_geojson(path))

    @classmethod
    def from_cache(cls, *, download_if_missing: bool = True) -> ZoningDistrictLayer:
        return cls.from_path(cached_zoning_geojson(download_if_missing=download_if_missing))

    def districts_at(self, lon: float, lat: float) -> list[ZoningDistrictHit]:
        point = Point(lon, lat)
        hits: list[ZoningDistrictHit] = []
        for index in map(int, self._tree.query(point)):
            geom = self._geoms[index]
            if geom.covers(point):
                hits.append(self._hits[index])
        hits.sort(key=lambda h: (h.status != "Approved", h.district_code))
        return hits


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
