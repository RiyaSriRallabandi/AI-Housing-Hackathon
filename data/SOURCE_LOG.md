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
- **Retrieved:** 2026-09-26 via **browser-rendering fetch** (naive curl/requests is Cloudflare-blocked; the official pages render fully in a real browser).
- **Corpus files:** `data/zoning_corpus/` — general-purpose, all districts, not filtered to one site.
  - Ch. 903 https://ecode360.com/45474194 (`ch903.txt`)
  - Ch. 911 https://ecode360.com/45476524 (`ch911.txt`, `use_table_911_02.json` with every district column)
  - Ch. 912 https://ecode360.com/45477814 including §912.08 ADU Overlay District (`ch912.txt`)
  - Ch. 913 https://ecode360.com/45477960 (`ch913.txt`)
  - Ch. 914 https://ecode360.com/45478031 (`ch914.txt`) — parking schedules rendered usably
- **Scope decision:** residential-relevant chapters only (903, 911, 912, 913, 914). Commercial/industrial-only chapters are out of scope by design, not a silent gap.
- **Runtime lookup:** §911.02 column is selected from the mapped GIS district (e.g. R2-L → column R2). ADU Overlay membership is a live intersect of `PGHWebZoningOverlays` for ADU / Accessory Dwelling labels — not a stored fact about 170 Aidan Ct.
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

**Working demo parcel:** 170 Aidan Ct, Pittsburgh, PA 15226 (Brookline). PIN `0139F00077000000` / `139-F-77`. GIS district **R2-L**. Address from City `Addresses_GeneralUse` (intersects the parcel polygon). Census tract **42003191800** (Tract 1918) from Census Geocoder 2026-09-26.

See `data/demo_site.json`.

## American Community Survey 5-Year (Demographic)

- **Catalog URL (brief):** https://www.census.gov/data/developers/data-sets/acs-5year.html
- **Resolved URL:** https://data.census.gov/api/access/data/table (api.census.gov returned HTML title “Missing Key” without a Census API key on 2026-09-26)
- **Retrieved:** 2026-09-26 for GEOID `42003191800`
- **Tables:** ACSDT5Y2023 B01003, B25002, B25010, B25024, B11001, B01001; ACSDT5Y2018 B01003, B25002, B25010, B11001
- **Catalog caveat:** Estimates have margins of error — avoid false precision at tract scale.
- **What this does NOT cover for this site:** guaranteed demand; vacancy by units-in-structure; USPS postal vacancy (Useful, not retrieved). Population 5,332 ±663 (2019–2023) vs 5,459 ±381 (2014–2018) — change may be insignificant.

## Decennial Census (Demographic)

- **Catalog URL (brief):** https://www.census.gov/programs-surveys/decennial-census/data.html
- **Resolved:** DECENNIALPL2020.P1 and .H1 via data.census.gov for tract 42003191800
- **Retrieved:** 2026-09-26. 2020 population 5,252; 2,590 housing units (154 vacant).
- **Does not cover:** household size, family type, units-in-structure (not in PL 94-171).

## TIGER / Census Geocoder

- **Catalog URL (brief):** https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- **Resolved:** https://geocoding.geo.census.gov/geocoder/geographies/coordinates (Public_AR_Current / Current_Current)
- **Retrieved:** 2026-09-26. Parcel centroid → Census Tract 1918, GEOID 42003191800. Neighborhood-layer tract fields were not used.

## Allegheny County Property Assessments (Pro Forma)

- **Catalog URL (brief):** https://data.wprdc.org/dataset/property-assessments
- **Resolved:** WPRDC datastore resource `65855e14-549e-4992-b5be-d629afc676fa` (API version). Metadata last_etl_update 2026-09-07.
- **Retrieved:** 2026-09-26 for PARID `0139F00077000000`. Fair-market land $30,000; building $147,300; total $177,300. Finished living area 1,704 sf. Assessment USEDESC/STYLEDESC **TOWNHOUSE** (assessment class, not Title 9).
- **Catalog caveat:** Assessed value is not market value.
- **What this does NOT cover:** Construction cost, asking rents, or resale certainty.

## Allegheny County Property Sale Transactions (Pro Forma)

- **Catalog URL (brief):** https://data.wprdc.org/dataset/allegheny-county-property-sale-transactions — **404** on 2026-09-26
- **Resolved URL:** https://data.wprdc.org/dataset/real-estate-sales (datastore `5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1`)
- **Retrieved:** 2026-09-26. Parcel transfer 2015-07-02 $215,000 SALECODE 36 QUIT CLAIM — **not** treated as arm's-length. Comparables: ZIP 15226 and SALECODE 0 (VALID SALE), most recent first.
- **Catalog caveat:** Filter using sale-validation codes; many transfers are not arm's-length sales.

## ICC Building Valuation Data (Pro Forma construction cost)

- **URL:** https://www.iccsafe.org/wp-content/uploads/BVD-BSJ-AUG2026.pdf
- **Table:** Building Valuation Data – AUGUST 2026 (next update February 2027). Occupancy groups from 2024 IBC.
- **Retrieved:** 2026-09-26. Default construction type **VB**. R-3 (one- and two-family) $177.63/sf; R-2 (multiple family) $159.71/sf; R-4 (care/assisted living) $203.38/sf.
- **Pittsburgh local modifier search (2026-09-26):** None found. PLI (successor to Bureau of Building Inspection) 2026 fee schedule uses $6.00 per $1,000 of stated construction value for residential permits — not an ICC BVD regional multiplier. Used the national table unmodified.
- **ICC caveats:** National average; not regional; not an estimating guide; excludes land. Dependent scores are **estimated**.

## HUD CHAS (Equity)

- **Catalog URL (brief):** https://www.huduser.gov/portal/datasets/cp.html
- **Resolved URL:** https://services.arcgis.com/VTyQ9soqVukalItT/ArcGIS/rest/services/ACS_5YR_ESTIMATES_CHAS_TRACT/FeatureServer/1
- **Retrieved:** 2026-09-27 for GEOID `42003191800` (Census Tract 1918).
- **Vintage:** **2013–2017** (layer “Date of Coverage”). HUD’s most recent CHAS release is **2018–2022** (announced 2025-12-23). This extract is older; do not treat it as current-year conditions. HUD USER Dataset Update Schedule lists the **next CHAS update for December 2026**.
- **Figures used:** T2_EST1 occupied households 2,330; T8_CB 430 (18.45%) cost-burdened >30%; T8_CB50 190 (8.15%) >50%; T8_LE30 235 households ≤30% HAMFI of which 74.47% cost-burdened.
- **Catalog caveat:** Based on multi-year ACS; releases lag; tables are complex.
- **What this does NOT cover:** Displacement from a specific new building. HUD Income Limits and Location Affordability Index (Useful) were not retrieved. HUD User CHAS API was not used (token; no tract geography). National 2018–2022 ZIP download was WAF-blocked.

## Pittsburgh Regional Transit GTFS (Sustainability)

- **Catalog URL (brief):** https://data.wprdc.org/dataset/port-authority-of-allegheny-county-transit-data — **404** on 2026-09-27
- **Resolved URL:** https://data.wprdc.org/dataset/prt-of-allegheny-county-transit-stops (CKAN datastore/GeoJSON resource `d6e6ed6e-9220-4a0e-9796-e72d83ce8e7a`). Historical GTFS zips: https://data.wprdc.org/dataset/gtfs-archive
- **Retrieved:** 2026-09-27 for parcel centroid (−80.01047, 40.38137). Feed version **2606** (`from_gtfs=1`).
- **Nearest unique stops:** McNeilly Station (RAIL BLUE,SLVR) 637 m / 646 m (two stop_ids), 84 weekday scheduled trips; nearest bus (route 39) ~801 m. Unique stops within 400 m: **0**; within 800 m: **2**; within 1,500 ft (~457 m): **0**.
- **City overlay:** `PGHWebMajorTransitBuffer` (1,500 ft) did **not** intersect this point. Overlay miss ≠ no transit.
- **Catalog caveat:** Scheduled service is not realized reliability.
- **What this does NOT cover:** On-time performance, rider counts, or Access Across America (Useful).

## FEMA National Flood Hazard Layer (Sustainability)

- **Catalog URL (brief):** https://www.fema.gov/flood-maps/national-flood-hazard-layer
- **Resolved URL:** Official Zoning Map `FEMA_2026` FeatureServer `https://services1.arcgis.com/YZCmUqbcsUpOKfj7/arcgis/rest/services/FEMA_2026/FeatureServer/0`
- **Retrieved:** 2026-09-27 at the demo centroid. **FLD_ZONE=X**, **ZONE_SUBTY=AREA OF MINIMAL FLOOD HAZARD**, **SFHA_TF=F**. The layer **covers** the site; the site is **not** in the Special Flood Hazard Area.
- **Catalog caveat:** Not a substitute for a formal flood determination.
- **Related Useful (wired because it is on the official map):** `PGHWebSlope25` flagged **Yes** — screening only, not a geotechnical survey. PA DEP eMapPA and EPA EJScreen were not retrieved.

