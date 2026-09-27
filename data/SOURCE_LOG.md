# Data source log — written as sources were integrated (Component 2, Zoning)

Decision support only — not legal, financial, or zoning advice.

Retrieval date for this pass: **2026-09-26**.

## Pittsburgh Zoning Districts (GIS)

- **Catalog URL (brief):** https://data.wprdc.org/dataset/pittsburgh-zoning
- **Resolved URL:** https://data.wprdc.org/dataset/zoning (CKAN id `zoning`; catalog slug 404s)
- **File used:** WPRDC GeoJSON resource `6127f35e-f36b-4a53-80b3-f4409609e9df` (last_modified 2026-09-23; 1,069 features, 3.3 MB)
- **Fields actually present:** `zon_new`, `full_zoning_type`, `legendtype`, `municode`, `status`, `OBJECTID`
- **Catalog caveat:** The map alone is insufficient — overlays, definitions, and exceptions in the code text still govern.
- **What this does NOT cover for a site:** permitted/conditional uses, variances, height/setback/parking tables, overlay review. One polygon is `Pending`. `MTOBOR` is Mount Oliver Borough, not City zoning.

## Pittsburgh Zoning Code (Title 9)

- **Catalog URL (brief):** https://pittsburghpa.gov/dcp/zoning-code — **404** on 2026-09-26
- **Resolved URL:** https://ecode360.com/45474054 (Title 9; user-provided). City Zoning page: https://www.pittsburghpa.gov/Business-Development/City-Planning/Zoning (last updated 2026-05-28 in page footer). Catalog URL 404s.
- **Retrieved:** 2026-09-26. eCode360 chrome says legislation through **2026-09-16**.
- **What we actually captured:** Chapter 903 (https://ecode360.com/45474231) — use subdistricts R1D / R1A / R2 / R3 / RM and VL–VH site-development tables. Encoded in `housing_review.data.residential`.
- **Still missing:** §911.02 Use Table (page did not load reliably in browser); Chapter 912 accessory (ADU); Chapter 914 parking. Those stay `cannot_determine`.
- **Caveat:** Authoritative interpretation belongs to the City.

## Official Pittsburgh Zoning Map (user-provided)

- **URL:** https://pittsburghpa.maps.arcgis.com/apps/instant/sidebar/index.html?appid=4bb79ea64bf848b3a0560e3856efeccb
- **Webmap:** `ee49e1c537fc4c458b087356d2104f4c`
- **Base districts:** same `PGHWebZoning` FeatureServer as the WPRDC GeoJSON.
- **Overlays wired for point query:** inclusionary housing, height reduction, Baum Centre, North Side commercial parking, parking reduction, 1500' major transit buffer, historic districts, 25%+ steep slopes, FEMA 2026 floodplain.
- **Fixture note:** parcel `0139F00077000000` (R2-L) intersected the steep-slope screening layer on 2026-09-26 — that is a GIS flag, not a survey.

## Hackathon public data catalog CSV

Copied to `data/public_data_catalog.csv` (user-provided). Core rows match `06_data_sources.md`; extra Core rows (PLI permits, tax delinquency, steep slopes, undermined areas, etc.) are recorded for later agents, not substituted for Zoning Core.

## Allegheny County Parcel Boundaries

- **Catalog URL (brief):** https://data.wprdc.org/dataset/allegheny-county-parcel-boundaries
- **Resolved URL:** CKAN id `allegheny-county-parcel-boundaries1`; query API `https://gisdata.alleghenycounty.us/arcgis/rest/services/OPENDATA/Parcels/MapServer/0` (County Open Data copy of the same parcel-boundary layer). WPRDC-listed PASDA MapServer returned “Service not started” on retrieval date. Full county GeoJSON is ~444 MB and is not stored in git.
- **Fields actually present:** `PIN`, `MAPBLOCKLOT`, `MUNICODE`, `CALCACREAGE`, polygon geometry
- **Catalog caveat:** Geometry and assessment records may update on different schedules — validate parcel IDs.
- **What this does NOT cover:** zoning district, address, assessed value, or whether a transfer was an arm’s-length sale.

## Test fixture / demo site

**Working demo parcel:** 170 Aidan Ct, Pittsburgh, PA 15226 (Brookline). PIN `0139F00077000000` / `139-F-77`. GIS district **R2-L**. Address from City `Addresses_GeneralUse` (intersects the parcel polygon). Tract GEOID is a placeholder until the Demographic layer joins TIGER.

See `data/demo_site.json`.
