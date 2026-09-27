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
                "Naive curl/requests to eCode360 hit Cloudflare bot detection; a "
                "browser-rendering fetch on 2026-09-26 retrieved the chapter text."
            ),
            does_not_cover=(
                "Deliberate corpus scope: residential-relevant Chapters 903, 911, 912, 913, "
                "and 914 only — not the full Title 9. Commercial/industrial-only chapters "
                "are out of scope. §903.03.E Very-High Density table lists no minimum lot size."
            ),
            notes=(
                "Browser-retrieved 2026-09-26: Ch. 903 https://ecode360.com/45474194 ; "
                "Ch. 911 (full §911.02 Use Table, every district column) "
                "https://ecode360.com/45476524 ; Ch. 912 incl. §912.08 "
                "https://ecode360.com/45477814 ; Ch. 913 https://ecode360.com/45477960 ; "
                "Ch. 914 https://ecode360.com/45478031 . Files in data/zoning_corpus/. "
                "Use Table column is looked up from the mapped GIS district at query time."
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


def demographic_analyst_sources() -> list[SourceRecord]:
    retrieved = date(2026, 9, 26)
    return [
        SourceRecord(
            agent="demographic_analyst",
            name="American Community Survey 5-Year",
            catalog_url="https://www.census.gov/data/developers/data-sets/acs-5year.html",
            resolved_url="https://data.census.gov/api/access/data/table",
            retrieved_on=retrieved,
            caveat=(
                "Estimates have margins of error — avoid false precision for small areas "
                "(tract-level). api.census.gov returned HTML 'Missing Key' without a Census "
                "API key on 2026-09-26; tables were retrieved from data.census.gov for "
                "GEOID 42003191800."
            ),
            does_not_cover=(
                "Does not measure guaranteed demand. Vacancy is not split by units-in-structure "
                "in the tables retrieved (B25024 is inventory mix). USPS postal vacancy was not "
                "retrieved (Useful, not Core)."
            ),
            notes=(
                "Vintages: ACS 5-Year 2019-2023 (ACSDT5Y2023 B01003, B25002, B25010, B25024, "
                "B11001, B01001) and ACS 5-Year 2014-2018 (ACSDT5Y2018 B01003, B25002, B25010, "
                "B11001). Non-overlapping periods for trajectory."
            ),
        ),
        SourceRecord(
            agent="demographic_analyst",
            name="Decennial Census",
            catalog_url="https://www.census.gov/programs-surveys/decennial-census/data.html",
            resolved_url="https://data.census.gov/api/access/data/table",
            retrieved_on=retrieved,
            caveat=(
                "Limited socioeconomic detail vs. ACS; geography changes complicate time series. "
                "2020 PL 94-171 is a count, not an ACS estimate."
            ),
            does_not_cover=(
                "Household size, family type, and units-in-structure are not in the 2020 PL "
                "tables retrieved (P1, H1 only)."
            ),
            notes="DECENNIALPL2020.P1 and DECENNIALPL2020.H1 for tract 42003191800.",
        ),
        SourceRecord(
            agent="demographic_analyst",
            name="TIGER/Line via Census Geocoder",
            catalog_url="https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html",
            resolved_url="https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
            retrieved_on=retrieved,
            caveat="Boundary vintages must match the statistics being joined.",
            does_not_cover=(
                "Geocoder returns Current TIGER geography for the point; it is not a substitute "
                "for downloading the full TIGER shapefile. Neighborhood-layer tract fields were "
                "not used."
            ),
            notes=(
                "170 Aidan Ct centroid → Census Tract 1918, GEOID 42003191800, "
                "benchmark Public_AR_Current, vintage Current_Current."
            ),
        ),
    ]


def pro_forma_analyst_sources() -> list[SourceRecord]:
    retrieved = date(2026, 9, 26)
    return [
        SourceRecord(
            agent="pro_forma_analyst",
            name="Allegheny County Property Assessments",
            catalog_url="https://data.wprdc.org/dataset/property-assessments",
            resolved_url="https://data.wprdc.org/dataset/property-assessments",
            retrieved_on=retrieved,
            caveat="Assessed value is not market value — do not conflate the two.",
            does_not_cover=(
                "Does not provide construction cost, asking rents, or a guarantee of "
                "resale price. USEDESC is an assessment class (this parcel: TOWNHOUSE), "
                "not a Title 9 zoning use."
            ),
            notes=(
                "CKAN resource 65855e14-549e-4992-b5be-d629afc676fa (API version). "
                "PARID 0139F00077000000 retrieved 2026-09-26: FAIRMARKETLAND 30000, "
                "FAIRMARKETTOTAL 177300, FINISHEDLIVINGAREA 1704, SALECODE 36 QUIT CLAIM."
            ),
        ),
        SourceRecord(
            agent="pro_forma_analyst",
            name="Allegheny County Property Sale Transactions",
            catalog_url="https://data.wprdc.org/dataset/allegheny-county-property-sale-transactions",
            resolved_url="https://data.wprdc.org/dataset/real-estate-sales",
            retrieved_on=retrieved,
            caveat="Filter using sale-validation codes; many transfers are not arm's-length sales.",
            does_not_cover=(
                "Catalog slug allegheny-county-property-sale-transactions 404s; live dataset "
                "id is real-estate-sales. This parcel's 2015 transfer is QUIT CLAIM, not VALID SALE."
            ),
            notes=(
                "Datastore 5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1. Comparables: PROPERTYZIP=15226 "
                "and SALECODE=0 (VALID SALE), sorted SALEDATE desc."
            ),
        ),
        SourceRecord(
            agent="pro_forma_analyst",
            name="ICC Building Valuation Data",
            catalog_url="https://www.iccsafe.org/wp-content/uploads/BVD-BSJ-AUG2026.pdf",
            resolved_url="https://www.iccsafe.org/wp-content/uploads/BVD-BSJ-AUG2026.pdf",
            retrieved_on=retrieved,
            caveat=(
                "National average for permit-fee valuation, not a Pittsburgh bid and not an "
                "estimating guide (ICC's own disclaimer). Excludes land. Every dependent "
                "score is estimated."
            ),
            does_not_cover=(
                "Site-specific contractor pricing, Pittsburgh labor/materials, financing, or "
                "developer margin. City of Pittsburgh PLI/BBI published no local ICC BVD "
                "modifier as of 2026-09-26; PLI fees are $ per $1,000 of stated construction value."
            ),
            notes=(
                "Table: Building Valuation Data – AUGUST 2026. Default construction type VB. "
                "Occupancy: R-3 (duplex/townhome/detached/adu) $177.63/sf; R-2 (apartment) "
                "$159.71/sf; R-4 (senior_housing) $203.38/sf. Next ICC update February 2027."
            ),
        ),
    ]


def equity_analyst_sources() -> list[SourceRecord]:
    retrieved = date(2026, 9, 27)
    return [
        SourceRecord(
            agent="equity_analyst",
            name="HUD CHAS (tract FeatureServer)",
            catalog_url="https://www.huduser.gov/portal/datasets/cp.html",
            resolved_url=(
                "https://services.arcgis.com/VTyQ9soqVukalItT/ArcGIS/rest/services/"
                "ACS_5YR_ESTIMATES_CHAS_TRACT/FeatureServer/1"
            ),
            retrieved_on=retrieved,
            caveat=(
                "Based on multi-year ACS; this layer's date of coverage is 2013-2017, "
                "older than HUD's 2018-2022 CHAS release (announced 2025-12-23). "
                "Does not measure displacement from a specific project."
            ),
            does_not_cover=(
                "HUD User CHAS API (token, no tract geography) and the 2018-2022 national "
                "ZIP download were not used. HUD Income Limits and Location Affordability "
                "Index were not retrieved (Useful)."
            ),
            notes=(
                "GEOID 42003191800 on 2026-09-27: T8_CB_PCT 18.45, T8_CB50_PCT 8.15, "
                "T2_EST1 2330 occupied households. Table 8 HAMFI cost-burden fields."
            ),
        ),
    ]


def sustainability_analyst_sources() -> list[SourceRecord]:
    retrieved = date(2026, 9, 27)
    return [
        SourceRecord(
            agent="sustainability_analyst",
            name="Pittsburgh Regional Transit GTFS (current stops)",
            catalog_url="https://data.wprdc.org/dataset/port-authority-of-allegheny-county-transit-data",
            resolved_url="https://data.wprdc.org/dataset/prt-of-allegheny-county-transit-stops",
            retrieved_on=retrieved,
            caveat="Scheduled service is not the same as realized reliability.",
            does_not_cover=(
                "Catalog slug port-authority-of-allegheny-county-transit-data 404s. "
                "Current GTFS-derived stops are dataset prt-of-allegheny-county-transit-stops "
                "(GeoJSON/datastore resource d6e6ed6e-9220-4a0e-9796-e72d83ce8e7a, "
                "from_gtfs / feed_version). Full trip-level GTFS zips live under gtfs-archive; "
                "on-time performance is not in this layer. Access Across America was not retrieved."
            ),
            notes=(
                "170 Aidan Ct centroid 2026-09-27: nearest unique stop McNeilly Station "
                "(RAIL BLUE,SLVR) ~637 m, 84 weekday scheduled trips; no unique stop within "
                "400 m or 1,500 ft. City PGHWebMajorTransitBuffer miss at this point."
            ),
        ),
        SourceRecord(
            agent="sustainability_analyst",
            name="FEMA National Flood Hazard Layer (City FEMA_2026 overlay)",
            catalog_url="https://www.fema.gov/flood-maps/national-flood-hazard-layer",
            resolved_url=(
                "https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/"
                "FEMA_2026/FeatureServer/0"
            ),
            retrieved_on=retrieved,
            caveat=(
                "Not a substitute for a formal flood determination; map amendments may matter. "
                "A Zone X hit means the layer covers the point (Area of Minimal Flood Hazard), "
                "not that the site is in a Special Flood Hazard Area."
            ),
            does_not_cover=(
                "Survey, LOMA/LOMR, insurance rating, or a lender flood determination. "
                "PA DEP eMapPA and EPA EJScreen (Useful) were not retrieved."
            ),
            notes=(
                "Official Zoning Map FEMA_2026 at the demo centroid: FLD_ZONE=X, "
                "ZONE_SUBTY=AREA OF MINIMAL FLOOD HAZARD, SFHA_TF=F. "
                "PGHWebSlope25 flagged Yes (screening only)."
            ),
        ),
    ]
