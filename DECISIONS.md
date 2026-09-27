# Decisions log

Decision support only — not legal, financial, or zoning advice.
This file is a running record of build choices. Entries are written when
the decision is made, not reconstructed later.

## [Component 1 / 2026-09-26] Shared contract implemented with Pydantic v2

- **Decision:** Represent the Analyst (Round 1 and Round 2) and Chair JSON contracts as Pydantic v2 models with `extra="forbid"`, plus `parse_analyst_assessment` / `parse_chair_synthesis` helpers that raise `ValidationError` on malformed output.
- **Options considered:** (1) JSON Schema files only; (2) Pydantic models as the source of truth (chosen); (3) typed dicts without runtime enforcement.
- **Rationale:** The roadmap requires a validator, not trust in model formatting. Pydantic gives runtime checks, JSON Schema export later, and a single Python type used by agents, orchestrator, and API.
- **Assumptions made:** Scores are integers 0–10 inclusive (as written in the prompt schema). Round 1 forbids `round_2_notes`; Round 2 uses a subclass that requires that field. Display-name aliases (e.g. "Zoning Analyst") are accepted and normalized to snake_case enum values. Chair models are included in Component 1 so the synthesis shape cannot drift before Component 5.
- **Open questions:** LLM provider/model (checkpoint). Whether scores should later allow halves (7.5) if a provider consistently emits floats.

## [Component 1 / 2026-09-26] Python package layout

- **Decision:** `src/housing_review/schemas/` for contracts, `tests/` for pytest, secrets via `.env` ignored from the first tracked files.
- **Options considered:** A flat scripts folder vs a small installable package.
- **Rationale:** Later components (data layer, agents, API) need a stable import path; an installable package avoids `sys.path` hacks.
- **Assumptions made:** Python 3.11+ is available in the demo environment.
- **Open questions:** Orchestration framework (checkpoint, not chosen here).

## [Component 2 / 2026-09-26] Zoning GIS via current WPRDC slug `zoning`

- **Decision:** Treat CKAN dataset `zoning` + GeoJSON resource `6127f35e-…` as the brief's Pittsburgh Zoning Districts source. The catalog path `/dataset/pittsburgh-zoning` 404s.
- **Options considered:** (1) Stop because the catalog URL 404s; (2) use the live City of Pittsburgh zoning dataset under the new slug (chosen); (3) substitute a different zoning product.
- **Rationale:** Same publisher, same layer (Pittsburgh Zoning Districts), fields inspected on the downloaded file. This is a URL-slug fix, not a different dataset.
- **Assumptions made:** `zon_new` is the district code to join to Title 9; `municode` is the intended section citation.
- **Open questions:** Overlay / height layers not joined yet (catalog says the map alone is insufficient).

## [Component 2 / 2026-09-26] Parcels via County Open Data Feature Service

- **Decision:** Query `gisdata.alleghenycounty.us/.../Parcels/MapServer/0` by PIN or point instead of committing the ~444MB WPRDC GeoJSON. PASDA REST listed on WPRDC was down (“Service not started”).
- **Options considered:** Download full GeoJSON; use parcel centroids (different product); use County Feature Service (chosen).
- **Rationale:** Same parcel-boundary dataset, queryable, fields PIN / MAPBLOCKLOT confirmed on a live record.
- **Assumptions made:** County Open Data layer matches WPRDC/PASDA parcels closely enough for a demo join; PINs are 16-character zero-padded strings in this service.
- **Open questions:** Geometry vs assessment update lag. Working example parcel chosen later (170 Aidan Ct).

## [Component 2 / 2026-09-26] Zoning code text not silently substituted

- **Decision:** Do not scrape-invent use tables. Store eCode360 URLs from GIS (`retrieval_status=url_only`) until a retrievable official text source is approved.
- **Options considered:** (a) `cannot_determine` on code body (chosen for automated layer); (b) labeled generic estimates — rejected; (c) City amendment PDFs as if they were the full code — rejected, incomplete; (d) change site — does not fix retrieval.
- **Rationale:** Working agreement §8: no silent workaround. eCode360 is Cloudflare-blocked; catalog city URL 404s.
- **Assumptions made:** GIS `municode` URLs still point at the current Title 9 host.
- **Open questions:** How to obtain a bot-accessible official copy (manual excerpt, PDF dump you provide, or another endpoint).

## [Component 2 / 2026-09-26] Official eCode360 + Zoning Map + catalog CSV

- **Decision:** Use the user-provided Title 9 URL and City Zoning page as the code host; transcribe Chapter 903 from the live eCode360 page (browser). Join overlay FeatureServers from the official Zoning Map app. Keep the CSV catalog in-repo as the source list for later agents.
- **Options considered:** Stay url-only; scrape 911.02 despite failed page load (rejected); treat overlay GIS as the code (rejected).
- **Rationale:** User directed these official sources. Chapter 903 loaded; 911.02 did not. Overlay list comes from the map the City publishes, which addresses the “map alone is insufficient” caveat without inventing rules.
- **Assumptions made:** GIS `zon_new` like `R2-L` is Use + Density per §903.03. Interior side for R1A is 5 ft in every density table we captured.
- **Open questions:** 911.02 / 912 / 914 still needed before the Zoning Analyst can score non-residential or ADU/senior uses from the use table.

## [Component 2 / 2026-09-26] Demo site: 170 Aidan Ct, Brookline (R2-L)

- **Decision:** Use PIN `0139F00077000000` (170 Aidan Ct, Pittsburgh, PA 15226) as the working demo parcel.
- **Options considered:** RM-M parcel `0094N00127000000`; large R1D-L `0135P00050000000` (~15 acres); this R2-L lot (chosen).
- **Rationale:** Typical residential lot with a matched city address, two-unit zoning so typology trade-offs are real, and a steep-slope overlay so the demo can show a limitation instead of a clean-but-fake site. Tract ID left null until ACS/TIGER.
- **Assumptions made:** Address-layer municipality PITTSBURGH is the right jurisdiction (City_Limits WGS84 queries did not return hits). Neighborhood name Brookline is from PGHWebNeighborhoods intersect.
- **Open questions:** Confirm tract GEOID in Component 2 Demographic slice. ADU/senior scoring still needs §911.02 / Ch. 912.
