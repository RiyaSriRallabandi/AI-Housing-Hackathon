from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SourceRecord(BaseModel):
    """What we actually used — origin, retrieval date, and what it does not cover."""

    model_config = ConfigDict(extra="forbid")

    agent: str
    name: str
    catalog_url: str
    resolved_url: str
    retrieved_on: date
    caveat: str
    does_not_cover: str
    notes: str = Field(default="")


def zoning_analyst_sources() -> list[SourceRecord]:
    """Core Zoning Analyst sources plus the parcel layer used for site lookup."""
    retrieved = date(2026, 9, 26)
    return [
        SourceRecord(
            agent="zoning_analyst",
            name="Pittsburgh Zoning Districts (GIS)",
            catalog_url="https://data.wprdc.org/dataset/pittsburgh-zoning",
            resolved_url="https://data.wprdc.org/dataset/zoning",
            retrieved_on=retrieved,
            caveat=(
                "The map alone is insufficient — overlays, definitions, and exceptions "
                "in the code text still govern. One feature is Pending; Mount Oliver "
                "Borough is present as MTOBOR and is not City of Pittsburgh zoning."
            ),
            does_not_cover=(
                "Use permissions, dimensional standards, variances, and overlay review "
                "triggers are not in this layer. Catalog slug pittsburgh-zoning 404s; "
                "the same City of Pittsburgh dataset is published as CKAN id `zoning` "
                "(GeoJSON resource 6127f35e-f36b-4a53-80b3-f4409609e9df, last_modified "
                "2026-09-23)."
            ),
            notes=(
                "Inspected fields: zon_new, full_zoning_type, legendtype, municode, status. "
                "1,069 features. municode points at eCode360 section URLs."
            ),
        ),
        SourceRecord(
            agent="zoning_analyst",
            name="Pittsburgh Zoning Code (Title 9)",
            catalog_url="https://pittsburghpa.gov/dcp/zoning-code",
            resolved_url="https://ecode360.com/45474054",
            retrieved_on=retrieved,
            caveat=(
                "Authoritative interpretation belongs to the City. Cite specific sections "
                "and flag ambiguity; never resolve it as a verdict. Catalog URL 404s. "
                "Official host confirmed by the City Zoning page and by the user: "
                "https://ecode360.com/45474054 (Title 9, legislation through 2026-09-16)."
            ),
            does_not_cover=(
                "Section 911.02 Use Table and Chapter 912 accessory rules were not captured "
                "as structured tables (eCode360 section pages are Cloudflare-blocked to curl; "
                "browser retrieval succeeded for Chapter 903). Parking (Ch. 914) not transcribed. "
                "§903.03.E Very-High Density table lists no minimum lot size."
            ),
            notes=(
                "Chapter 903 (https://ecode360.com/45474231) retrieved 2026-09-26 via the "
                "official eCode360 page: use subdistricts R1D/R1A/R2/R3/RM and VL/L/M/H/VH "
                "dimensional tables. City zoning page: "
                "https://www.pittsburghpa.gov/Business-Development/City-Planning/Zoning. "
                "Official map app (overlays): "
                "https://pittsburghpa.maps.arcgis.com/apps/instant/sidebar/index.html?appid=4bb79ea64bf848b3a0560e3856efeccb"
            ),
        ),
        SourceRecord(
            agent="site_lookup",
            name="Allegheny County Parcel Boundaries",
            catalog_url="https://data.wprdc.org/dataset/allegheny-county-parcel-boundaries",
            resolved_url="https://gisdata.alleghenycounty.us/arcgis/rest/services/OPENDATA/Parcels/MapServer/0",
            retrieved_on=retrieved,
            caveat=(
                "Geometry and assessment records may update on different schedules — "
                "validate parcel IDs. WPRDC catalog slug now ends in `boundaries1`."
            ),
            does_not_cover=(
                "Does not include zoning classification, address, or assessed value. "
                "Full WPRDC GeoJSON is ~444MB; PASDA MapServer listed on WPRDC was not "
                "started (HTTP 500) on retrieval date, so lookups use the County Open Data "
                "Feature Service for the same parcel-boundary dataset (fields PIN, "
                "MAPBLOCKLOT, MUNICODE, CALCACREAGE)."
            ),
            notes="Query by PIN or point; do not commit county-wide geometry.",
        ),
    ]
