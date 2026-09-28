# Typescape

Typescape is a Track 3 (Housing Typology, Equity & Climate Matchmaker) decision-support tool. It helps a human compare six housing types on a real Pittsburgh lot and see the tradeoffs. It is built for planners, reviewers, and hackathon judges who need cited, comparable scores rather than a single recommended product.

**This is not legal, financial, or zoning advice.** Outputs are scenario comparisons. A person sets which topics matter and still has to verify the result with the relevant office before acting. The tool never picks a winner.

## How it works

Five independent reviews score the same six housing types for one parcel: Zoning, Demographic, Cost and feasibility, Equity, and Sustainability. Each review uses its own facts and citations. They do not negotiate with each other.

A Chair pass then sits beside those scores. It flags factual conflicts (claims that cannot both be true about the site) versus value tradeoffs (legitimate goals that pull in different directions). It does not fuse scores or name a winner.

A weighting layer turns the saved scores into a ranked list using only the weights the user sets. Equal weights are labeled as an equal-weight view. Changing the sliders updates the list from the saved scores. That step never calls a language model.

## Current coverage

Typescape currently covers one Brookline lot:

- Address: 170 Aidan Ct, Pittsburgh, PA 15226
- PIN: `0139F00077000000` (map-block-lot 139-F-77)
- Zoning GIS district: R2-L
- Census tract GEOID: `42003191800`

Coverage is limited by the data gathered so far.

## Run it locally

Python 3.11+. No API keys are required to open the page and rank the Brookline example. The saved Round 1 and Chair files under `data/demo/analysis/0139F00077000000/` are copied into the local cache on first `GET /analysis/0139F00077000000`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn housing_review.api:app --reload --port 8000
```

Open http://127.0.0.1:8000 and search `170 Aidan Ct` or PIN `0139F00077000000`.

`POST /weighted-view/{site_id}` never calls a language model. It only reads the saved analysis and applies weights.

### Live rerun (optional)

A live Round 1 plus Chair run needs keys. Copy `.env.example` to `.env` and set names only:

- `LLM_PROVIDER` (default `groq`)
- `LLM_MODEL` (default `openai/gpt-oss-120b`)
- `GROQ_API_KEY` for Groq
- `GEMINI_API_KEY` (or `LLM_API_KEY`) if you switch the provider to `google_gemini`
- optional: `LLM_MAX_RETRIES`, `LLM_RETRY_BACKOFF_SECONDS`

Do not put model names inside agent modules. Do not commit `.env`.

To force a live run, remove the copied files under `data/cache/analysis/0139F00077000000/` (that directory is gitignored). The committed copies in `data/demo/analysis/` stay in the repo.

## What we would build next

- HUD Fair Market Rents plus HUD Income Limits for Equity, so scores can differ by housing type
- More lots than this one Brookline parcel
- A fresher CHAS vintage than 2013 to 2017 (HUD’s later 2018 to 2022 release)

## Data sources and citations

Retrieval dates below are when this project pulled each source. Geography: parcel PIN and lot polygon for zoning, assessments, and the map; Census tract `42003191800` for ACS, 2020 PL, and CHAS; ZIP 15226 for sale comparables. Years are not aligned across sources. We did not treat a tract figure as a unit rent or a 2013 to 2017 CHAS cell as a 2026 condition.

### Pittsburgh Zoning Code, Title 9 (eCode360)

- URL: https://ecode360.com/45474054
- Retrieved: 2026-09-26 (browser; naive curl is Cloudflare-blocked)
- Chapters used: 903, 911 (including the §911.02 Use Table), 912, 913, 914
- City Zoning page: https://www.pittsburghpa.gov/Business-Development/City-Planning/Zoning

### Zoning district GIS

- Catalog slug `pittsburgh-zoning` 404s; dataset used: https://data.wprdc.org/dataset/zoning
- GeoJSON resource `6127f35e-f36b-4a53-80b3-f4409609e9df` (last_modified 2026-09-23)
- Official map overlays: https://pittsburghpa.maps.arcgis.com/apps/instant/sidebar/index.html?appid=4bb79ea64bf848b3a0560e3856efeccb

### Census ACS 5-year and 2020 PL

- ACS docs: https://www.census.gov/data/developers/data-sets/acs-5year.html
- Retrieved 2026-09-26 for tract `42003191800` via data.census.gov (api.census.gov required a key)
- ACS 5-year tables include 2019-2023 and selected 2014-2018 series
- 2020 PL: DECENNIALPL2020.P1 and .H1 for the same tract
- Tract join: Census Geocoder at the parcel centroid, 2026-09-26, https://geocoding.geo.census.gov/geocoder/geographies/coordinates

### HUD CHAS (Equity)

- Portal: https://www.huduser.gov/portal/datasets/cp.html
- Layer: https://services.arcgis.com/VTyQ9soqVukalItT/ArcGIS/rest/services/ACS_5YR_ESTIMATES_CHAS_TRACT/FeatureServer/1
- Retrieved: 2026-09-27 for tract `42003191800`
- Vintage: 2013 to 2017, older than HUD’s 2018 to 2022 release

### Allegheny County assessments and sales (WPRDC)

- Assessments: https://data.wprdc.org/dataset/property-assessments (resource `65855e14-549e-4992-b5be-d629afc676fa`), retrieved 2026-09-26 for this PIN. Assessed value is not market value. Owner name and mailing fields were not stored.
- Sales: https://data.wprdc.org/dataset/real-estate-sales (resource `5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1`). Comparables use ZIP 15226 and SALECODE 0 (VALID SALE).
- Parcel geometry: County Open Data Feature Service `https://gisdata.alleghenycounty.us/arcgis/rest/services/OPENDATA/Parcels/MapServer/0`

### ICC Building Valuation Data (August 2026)

- URL: https://www.iccsafe.org/wp-content/uploads/BVD-BSJ-AUG2026.pdf
- Retrieved: 2026-09-26. National average, occupancy groups from 2024 IBC, construction type VB. No Pittsburgh local ICC modifier was found.

### PRT stops

- https://data.wprdc.org/dataset/prt-of-allegheny-county-transit-stops
- Retrieved: 2026-09-27, feed version 2606. Scheduled service is not on-time reliability.

### FEMA flood data

- Catalog: https://www.fema.gov/flood-maps/national-flood-hazard-layer
- Official map layer `FEMA_2026`: FeatureServer used on 2026-09-27. Demo point is Zone X / not SFHA. This is a screen, not a flood determination.

More field-level notes: `data/SOURCE_LOG.md`.

## Limitations

- One covered lot.
- Equity scores are flat because CHAS is tract-level and not typology-specific.
- Construction cost is a national estimate, not a Pittsburgh figure.
- The ADU overlay is a map screen.
- Flood data is a screen, not a determination.
- Senior housing is only partly mapped.
- No permitting timelines.
- Scores are comparative, not predictions.

Also: Title 9 corpus is a residential subset (Ch. 903, 911, 912, 913, 914), not the full code. ACS figures have margins of error. Overlay slope at this parcel is screening-level, not a geotechnical determination.

## Libraries, frameworks, and services

Python: Pydantic v2, Shapely 2, FastAPI, Uvicorn, python-dotenv, groq, google-genai. Tests: pytest, httpx.

Front end: Leaflet 1.9.4, SortableJS 1.15.6, OpenStreetMap raster tiles (`{s}.tile.openstreetmap.org`), Google Fonts **Raleway** and **DM Sans**.

## AI tool disclosure

- **Cursor** was the coding assistant in the editor (models selected within Cursor; the exact model list for every session was not recorded).
- **Claude** was used for planning, design decisions, prompt drafting, logo artwork drafts, and interface copy drafts, which were then edited.
- Runtime models for the five analysts and the Chair: Groq `openai/gpt-oss-120b` as the configured default, and Gemini 3.5 Flash-Lite as the fallback used for the saved Brookline run (see `data/demo/analysis/0139F00077000000/README.md`).

## Privacy and integrity

No PII is collected. The demo uses tract-level public statistics and parcel-level public GIS and assessment value fields. County owner name and mailing address were not copied. Every model-facing claim is cited. Code-owned facts (Use Table rows, CHAS figures, ICC $/sf, PRT distance, flood zone) are attached in Python and kept separate from model judgments.

## Build window

All code was written during the hackathon window (Sept 26 to 27, 2026).

## Asset credits (documentation only)

These credits are not shown on the website, except the map’s built-in Leaflet and OpenStreetMap attribution, which stays visible on the map.

- Backdrop photograph: Andrew Rush / Pittsburgh Post-Gazette, from https://www.post-gazette.com/business/money/2022/05/09/pittsburgh-housing-market-interest-rates-prices-bidding-wars-affordability-first-time-home-buyers-investors/stories/202205080048. Used as a backdrop for a non-commercial hackathon prototype. All rights remain with the owner. It will be removed or replaced on request. We do not claim a license we have not confirmed. Swap file: `src/housing_review/web/pittsburgh-housing.jpg` (CSS variable `--site-backdrop-image`).
- Map tiles: OpenStreetMap contributors, https://www.openstreetmap.org/copyright
- Fonts: Raleway and DM Sans, served from Google Fonts
