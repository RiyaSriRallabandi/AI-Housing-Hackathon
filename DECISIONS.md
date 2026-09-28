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

## [Component 3 / 2026-09-26] Gemini 2.5 Flash as shared runtime model

- **Decision:** All six in-app agents use one config (`housing_review.config` + `LLM_MODEL` / `LLM_PROVIDER` / `GEMINI_API_KEY`). Default model string is `gemini-2.5-flash`. Zoning Analyst is the first caller; it never embeds a model id of its own.
- **Options considered:** Hardcode per agent (rejected); Groq/OpenRouter `:free` fallbacks (kept as later options, not wired yet).
- **Rationale:** User specified Gemini 2.5 Flash. Official model page (fetched 2026-09-26) lists the API code as `gemini-2.5-flash` and stable alias of the same name. Preview `gemini-2.5-flash-preview-09-2025` is marked shut down on that page.
- **Verification:**
  - Model page: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash — code `gemini-2.5-flash`; input 1,048,576 tokens; output 65,536; structured outputs supported. Same docs note 2.5 access may be limited to accounts that already used 2.5; new projects are pointed at 3.5 Flash-Lite or 3.8 Flash. Swap via `LLM_MODEL` if this project cannot call 2.5.
  - Rate limits page: https://ai.google.dev/gemini-api/docs/rate-limits (updated 2026-09-02) — limits are RPM, input TPM, and RPD (RPD resets midnight Pacific). Free tier has no spend cap. **Numeric Free-tier RPM/TPM/RPD are not published as a universal table**; docs say view them in AI Studio and that specified limits are not guaranteed.
  - AI Studio console: `https://aistudio.google.com/rate-limit` redirected to Google sign-in from this environment (2026-09-26). Project-specific quota numbers were **not** readable without an account login. Do not invent RPM/RPD figures.
  - User-reported AI Studio quotas for `gemini-2.5-flash` (2026-09-26): **5 RPM**, **250K TPM**, **20 RPD** (usage shown as 0 / those caps).
- **Assumptions made:** `google-genai` `Client.models.generate_content` with `response_mime_type=application/json` is the runtime path. Calls retry on 429 with 15s backoff. A full five-analyst debate is 11 LLM calls (5+5+1), which fits under 20 RPD if Zoning (and others) batch all typologies in one call each. Do not fire Round 1 agents in parallel (5 RPM).
- **Open questions:** If `gemini-2.5-flash` is unavailable for a new project, set `LLM_MODEL` to a Flash model the console lists as free (docs currently suggest 3.5 Flash-Lite or 3.8 Flash).

## [Component 3 / 2026-09-26] Swap default model after live 404 on 2.5 Flash

- **Decision:** Set shared `LLM_MODEL` to `gemini-3.8-flash` (env + `housing_review.config`). Still one config for all agents.
- **Options considered:** Keep calling `gemini-2.5-flash` (failed); switch via central env (chosen); Groq/OpenRouter (not needed yet).
- **Rationale:** One live `generate_content` on this project's key returned HTTP 404: "This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.8-flash". That matches the model-page warning that 2.5 is limited to prior users.
- **Assumptions made:** Failed 2.5/3.8 calls did not consume RPD (console still 0/20). Retry 503 with backoff.
- **Open questions:** Whether a single batched Zoning Round-1 call stays under 250K TPM.

## [Component 3 / 2026-09-26] Gemini 3.8 Flash free-tier quotas (AI Studio)

- **Decision:** Treat 3.8 Flash limits as **5 RPM, 250K TPM, 20 RPD** (user console: 0 / those caps). Same shape as 2.5 Flash on this project.
- **Options considered:** Assume 2.5 numbers apply without checking (rejected).
- **Rationale:** User read the AI Studio rate-limit panel for Gemini 3.8 Flash Text-out models.
- **Assumptions made:** RPD resets midnight Pacific. One Zoning Round-1 call should be 1 RPD if it succeeds.
- **Open questions:** 503 high-demand vs quota; retry when Google capacity recovers.

## [Component 3 / 2026-09-26] Switch shared runtime from Gemini to Groq

- **Decision:** Default `LLM_PROVIDER=groq` and `LLM_MODEL=openai/gpt-oss-120b` for all six agents. Keep Gemini as an env-switch fallback. Zoning Round 1 sends a compact site JSON (no geometry, overlay attributes stripped) because Groq Free TPM is 8K.
- **Options considered:** Wait out Gemini 3.8 503s (quota unused); OpenRouter `:free`; Groq `openai/gpt-oss-20b` (faster, same 8K TPM); Groq `qwen/qwen3.8-27b`.
- **Rationale:** User-reported AI Studio still 0 RPM / 0 TPM / 0 RPD after 503s — capacity, not quota. Groq Free docs (fetched 2026-09-26): https://console.groq.com/docs/models and https://console.groq.com/docs/rate-limits — `openai/gpt-oss-120b` (and 20b) on Free: **30 RPM, 1K RPD, 8K TPM, 200K TPD**. Llama on Groq is enterprise/Contact Sales, not this free path. 120b chosen over 20b for schema-faithful JSON on zoning.
- **Assumptions made:** User will paste a Groq key from console.groq.com (no card). `response_format=json_object` requires a JSON object, so the prompt asks for `{"assessments": [...]}`. Compact context must stay well under 8K tokens including output.
- **Open questions:** Whether 120b stays under 8K TPM on this compacted Zoning payload; fall back to `openai/gpt-oss-20b` if TPM errors.

## [Component 3 / 2026-09-26] Live Zoning Round 1 on Groq succeeded

- **Decision:** Keep Groq `openai/gpt-oss-120b` as the shared default. Zoning prompt now includes an explicit claim example (`statement` / `basis` / `source`); schema retry asks for `{assessments: [...]}` not a bare array.
- **Rationale:** First live Groq call returned valid JSON object but claims used `text`/`citation` (rejected by extra=forbid). Second call after prompt tightening validated 6 typologies for PIN `0139F00077000000`. Scores stayed low (1–3, `estimated`) because §911.02 / Ch. 912 / Ch. 914 are still `cannot_determine` — that is the intended gap, not a model failure.
- **Assumptions made:** `include_overlays=False` for this live check to stay under 8K TPM. Cache written to `data/cache/zoning_analyst_live_round1.json` (gitignored).
- **Open questions:** Overlay-inclusive call; Round 2 / other analysts on the same Groq model.

## [Component 2 / 2026-09-26] Demographic data layer for tract 42003191800

- **Decision:** Join the demo parcel to Census Tract 1918 (GEOID `42003191800`) via the Census Geocoder (TIGER Current). Pull ACS 5-Year 2019–2023 and 2014–2018 plus 2020 PL 94-171 from `data.census.gov` table API. Do not use neighborhood-layer tract fields.
- **Options considered:** Official `api.census.gov` (HTML “Missing Key” without a Census API key); download full TIGER shapefiles (unnecessary for one point); USPS vacancy (Useful, skipped).
- **Rationale:** Roadmap next step after Zoning C3. Catalog Core sources are ACS 5-Year and Decennial; TIGER is the geographic join. data.census.gov is the same Census tables as the ACS developer API.
- **Assumptions made:** 2014–2018 vs 2019–2023 ACS 5-Year periods do not overlap, so they can be compared as trajectory with MOE caveats. Vacancy-by-structure stays `cannot_determine`.
- **Open questions:** Whether to add a free Census API key later; USPS vacancy if time.

## [Component 3 / 2026-09-26] Demographic Analyst Round 1

- **Decision:** Same shared Groq config and `{assessments: [...]}` JSON contract as Zoning. Prompt copied from `04_system_prompts.md` plus schema example and MOE / USPS / vacancy-by-structure gaps.
- **Options considered:** Wait for a Census API key (rejected; data.census.gov already returned tables).
- **Rationale:** Isolated agent test before debate orchestration (roadmap step 3 for the second analyst).
- **Open questions:** Live Groq schema-validity on this compact tract payload.

## [Component 2 / 2026-09-26] Zoning code corpus via browser fetch (all districts)

- **Decision:** Store full text of Title 9 Chapters **903, 911, 912, 913, and 914** in `data/zoning_corpus/` as a general-purpose corpus. The Zoning Analyst looks up the §911.02 column from whatever GIS district the site maps to. ADU Overlay membership is a live `PGHWebZoningOverlays` intersect for ADU / Accessory Dwelling labels, not a stored fact about 170 Aidan Ct.
- **Options considered:** Keep 911.02/912 as `cannot_determine` after curl Cloudflare blocks (rejected — the pages render in a browser); filter the Use Table to R2-L only (rejected); hardcode Garfield/ADU overlay for the demo parcel (rejected).
- **Rationale:** The gap was fetch method, not missing law. Naive curl/requests hit Cloudflare; browser-rendering retrieval on 2026-09-26 returned complete chapter text including every Use Table district column and §912.08.
- **Scope:** This is a **deliberate** residential-relevant subset (903, 911, 912, 913, 914), not a silent hole. Commercial/industrial-only chapters are out of scope for now.
- **Assumptions made:** GIS codes like `R2-L` join to Use Table column `R2`. Duplicate printed names in the Use Table (second RM/GI) are stored as `RIV-RM` / `RIV-GI` so lookups are unique. The published overlay layer had no ADU-named polygons on retrieval; live queries can still return hits if the layer is updated.
- **Open questions:** Whether a dedicated ADU Overlay FeatureServer exists under another name; user review of live Round 1 scores against the code.

## [Component 3 / 2026-09-26] Brief slug townhome vs Title 9 Single-Unit Attached

- **Decision:** Keep JSON typology as `townhome` (hackathon brief / shared schema). Zoning claims cite Title 9 **Single-Unit Attached Residential**. Accept `townhouse` and the Title 9 name as input aliases only.
- **Options considered:** Rename the schema enum to `townhouse` or `single_unit_attached` (rejected — brief lists townhome); treat townhome as a code term (rejected — Title 9 never uses it).
- **Rationale:** eCode360 §911.02 and the City use-classifications handout define Single-Unit Attached Residential (one unit on its own lot, party wall). The mapping is now explicit in the corpus lookup.
- **Assumptions made:** Duplex → Two-Unit; apartment → Multi-Unit; detached_single_family → Single-Unit Detached.
- **Open questions:** None.

## [Component 2 / 2026-09-26] Pro Forma construction cost from ICC BVD August 2026

- **Decision:** Use ICC **Building Valuation Data – AUGUST 2026** as the labeled generic $/sf source. Default **Type VB**. Occupancy R-3 (duplex, townhome, detached_single_family, adu), R-2 (apartment), R-4 (senior_housing). Every score that depends on this is `estimated`. No Pittsburgh local ICC modifier.
- **Options considered:** Arbitrary $/sf (rejected); `cannot_determine` on all build-cost claims (rejected after user directed ICC BVD); apply a made-up Pittsburgh factor (rejected — none published).
- **Rationale:** User specified ICC BVD and a search of City PLI/BBI. PLI 2026 fees are $ per $1,000 of applicant construction value; they do not publish a BVD square-foot table or regional modifier. ICC states the table is a national average and not an estimating guide.
- **Assumptions made:** Type VB is a reasonable default for typical wood-frame residential when the application does not specify construction type. Existing FINISHEDLIVINGAREA is only a size proxy for implied cost.
- **Open questions:** Live Groq schema-validity on the compact Pro Forma payload.

## [Component 2 / 2026-09-27] Equity CHAS from ArcGIS tract FeatureServer

- **Decision:** Use `ACS_5YR_ESTIMATES_CHAS_TRACT` FeatureServer GEOID `42003191800` as the Core CHAS source. Cite vintage **2013–2017** and note it is older than HUD’s 2018–2022 release. Do not fall back to ACS B25070/B25091.
- **Options considered:** HUD User CHAS API (token; no tract); 2018–2022 national ZIP (WAF-blocked); ACS B25070/B25091 stand-in (held unless this layer failed).
- **Rationale:** The layer returned real Table 8 cost-burden fields for this tract. User directed this URL before any ACS stand-in.
- **Assumptions made:** T2_EST1 is occupied households; T8_CB / T8_CB_PCT are >30% cost burden; T8_CB50 / T8_CB50_PCT are >50%.
- **Open questions:** Live Groq schema-validity; whether a newer tract FeatureServer exists.
- **Future refresh:** HUD USER Dataset Update Schedule lists the next Consolidated Planning/CHAS data for **December 2026** (current posted vintage 2018–2022, released 2025-12-23). That is a known follow-on: swap this tract layer for the newer CHAS when it lands — useful for the submission “what we would build next” note.

## [Component 2 / 2026-09-27] Sustainability Core: PRT stops + FEMA_2026

- **Decision:** Treat WPRDC `prt-of-allegheny-county-transit-stops` (GTFS-derived current stops, feed 2606) as the Core GTFS source. Query City `FEMA_2026` on the official Zoning Map as the retrieved NFHL-style flood layer. Carbon claims stay generic typology-level **estimated** — no invented kg CO2.
- **Options considered:** Stop because catalog slug `port-authority-of-allegheny-county-transit-data` 404s (rejected — same publisher, current PRT product); download `gtfs-archive` zips for every query (rejected for C2; archive logged); treat a 1,500 ft overlay miss as “no transit” (rejected — McNeilly Station is ~637 m).
- **Rationale:** Stops table carries `from_gtfs`, `feed_version`, mode, routes, and weekday scheduled trips. FEMA Zone X at this point is coverage (Area of Minimal Flood Hazard / not SFHA), not a data hole.
- **Assumptions made:** Unique `stop_id` + haversine from parcel centroid is the right access metric for Round 1. Slope screening uses the official-map 25%+ layer already wired for Zoning.
- **Open questions:** Live Groq schema-validity; whether to parse a full GTFS zip for headways beyond `trips_wd`.

## [Component 4 / 2026-09-27] Round 1 debate is independent and sequential

- **Decision:** Component 4 Round 1 calls all five Analysts with only their own site context. No peer assessments are passed. Calls are sequential (zoning → demographic → pro forma → equity → sustainability), not parallel.
- **Options considered:** Parallel threads (rejected on Groq Free 8K TPM / shared rate budget); a single mega-prompt (rejected — would break independence).
- **Rationale:** Roadmap: Round 1 has no visibility into each other's output. Sequential still satisfies independence. Fixture-backed `load_demo_round1_contexts()` keeps tests offline.
- **Assumptions made:** Existing per-agent batching of 3 typologies stays inside each Analyst; the orchestrator does not re-batch. Fixture Round 1 copies steep-slope / FEMA flags and the last live ADU-overlay miss onto Zoning so it is not overlay-blind.
- **Live Groq (2026-09-27, `openai/gpt-oss-120b`):** First pass (10 calls) validated 30 assessments but Zoning read a blank Use Table cell as Chapter 913 and invented parking; ADU treated a null overlay as a fact. Prompts tightened; overlay screen attached. Second pass (11 calls, one schema retry) kept the same directional scores: duplex/townhome/detached high zoning certainty, apartment/ADU low; Pro Forma low/marginal (ICC estimated); Equity CHAS 2013–2017 with displacement in `cannot_determine`; Sustainability McNeilly ~637 m, Zone X, carbon `estimated`. Remaining slip: townhome Zoning *summary* still said “no off-street parking” while claims cited Schedule A without a zero. Transcript is gitignored at `data/cache/round1_live.json`.
- **Open questions:** Round 2 / Chair.

## [Component 3 / 2026-09-27] Zoning citations copied from structured contract

- **Decision:** Permitted-use and parking claim `source` fields must equal `citation_contract` strings (`§911.02 Use Table`, `§914.02.A Parking Schedule A`, or `§912.08` for ADU). Parking statements must quote the structured min and max. Compact prompts no longer include raw Ch. 914/912 dumps.
- **Rationale:** Live Groq invented `§911.04A.69` and omitted Schedule A maxima when mining excerpts. The corpus already had the correct rows for every district/typology.
- **Assumptions made:** Exact string equality on `source` is stricter than “contains,” which is the point. One schema retry still appends the validator error; a second failure still raises (no `cannot_determine` fallback).

## [Component 3 / 2026-09-27] Zoning deterministic facts; one comparative LLM call

- **Decision:** Use-table, Schedule A parking, and Chapter 903 dimensions are built as `Claim`s in code (`zoning_facts.py`) with citations. The Zoning LLM returns only `judgments` (score, basis, summary, cannot_determine). All six typologies are scored in **one** Groq call (~2.8K input tokens, under Free 8K TPM). Other Analysts still batch 3+3. Retry once on judgment-schema failure. A second failure no longer aborts Round 1: valid typologies are salvaged; the rest get score placeholder 0, an explanatory summary, and `cannot_determine` noting two invalid model outputs. Deterministic claims still attach. No citation-validator retry path for Zoning facts.
- **Open questions:** None for this slice.

## [Component 3 / 2026-09-27] Equity and Sustainability: code-owned claims, one call, shared judgment fallback

- **Decision:** Shared `agents/judgment.py` retries once on schema failure, then salvages valid typologies and falls back the rest (`cannot_determine` + score placeholder 0) instead of raising. Equity CHAS Table 8 figures and Sustainability PRT/FEMA/slope/carbon-direction claims are built in code with citations. Each of those two agents scores all six typologies in one call. Demographic and Pro Forma are unchanged in this slice.
- **Rationale:** Tract CHAS and site flood/transit facts do not vary by typology, so 3+3 batching only split comparative scores. Citation restatement was the same failure mode as Zoning.
- **Open questions:** None for this slice.

## [Component 3 / 2026-09-27] Demographic: code-owned ACS claims, one comparative call

- **Decision:** ACS 2019-2023 / 2014-2018 and 2020 PL estimates (table, variable, vintage, MOE) are attached as `Claim`s in `demographic_facts.py`. The Demographic LLM returns only `judgments` and scores all six typologies in one call, using the shared judgment fallback. USPS vacancy and vacancy-by-structure-type stay `cannot_determine`. Household-size change vs combined MOE is a confidence note, not a generated citation.
- **Rationale:** Tract ACS is site-constant; 3+3 batching split demand-fit scores that are meant to be comparative. The model was restating table IDs it already had in the payload.
- **Open questions:** None for this slice.

## [Component 3 / 2026-09-27] Pro Forma: code-owned assessment/ICC claims, one comparative call

- **Decision:** Assessed land, parcel sales, and ICC BVD $/sf (citation copied from `cost_for_typology()`) are attached as `Claim`s in `proforma_facts.py`. ICC rows stay `basis: estimated`. The Pro Forma LLM returns only `judgments` and scores all six typologies in one call, using the shared judgment fallback. ADU/apartment/senior keep the whole-house FINISHEDLIVINGAREA increment in `cannot_determine`. The Round 1 test completer no longer has an `assessments` / `fixture:{agent}` branch — that path existed only so slice 2 could stay green while Pro Forma was still on the old schema.
- **Rationale:** Per-typology ICC figures are as deterministic as Zoning parking rows; the model was rewriting the citation string. One call calibrates feasibility scores across all six typologies.
- **Open questions:** Live Groq Round 1 after all five Analysts are on this design. Round 2 still parked.

## [Component 3 / 2026-09-27] Groq primary; Gemini 3.5 Flash-Lite fallback

- **Decision:** Keep `LLM_PROVIDER=groq` and `LLM_MODEL=openai/gpt-oss-120b` as the shared primary. When Groq Free TPD/TPM is exhausted, switch via env to `google_gemini` / `gemini-3.5-flash-lite`. Do not use `gemini-3.8-flash` (live 503 high-demand on sequential Round 1 calls). Do not re-probe `gemini-2.5-flash` (404 “no longer available to new users” on this key).
- **Options considered:** Stay on 3.8 Flash and retry 503s; keep trying 2.5 Flash; treat model swap as the main quality lever.
- **Rationale:** Citations are code-owned on all five Analysts, so model strength matters less than stopping overstated judgment. Live Groq (2026-09-27) and Gemini 3.5 Flash-Lite both produced valid Round 1 JSON; 3.8 Flash failed mid-run; 2.5 Flash is permanently unavailable here. The Equity semantic overreach guard (concept check + claims-backed LLM review) is what blocks typology-affordability claims CHAS cannot support — not which Flash id is selected.
- **Assumptions made:** Groq TPD resets daily; Gemini fallback is an env override, not automatic failover. Extra Equity review call counts against the active provider’s quota.
- **Open questions:** Round 2 still parked.

## [Component 3 / 2026-09-27] Equity: no typology-affordability claims without prices

- **Decision:** When `price_data` is unknown, Equity summaries may restate tract CHAS cost-burden percentages and must say typology-specific affordability cannot be determined. Reject any summary that links a typology to affordability, cost-burden risk, mismatch, means, or similar — by concept, not two banned words — then run a separate LLM review against the cited CHAS claims asking whether the summary implies unsupported typology affordability. `cannot_determine` always includes the typology-affordability / `price_data` gaps.
- **Rationale:** Live Gemini 3.5 Flash-Lite still wrote “affordability-mismatch risk” after the keyword guard banned only “affordable/unaffordable.”
- **Open questions:** None for this slice.

## [Component 3 / 2026-09-27] Equity scores are tract-constant (flat-5)

- **Decision:** Identical Equity scores across the six typologies are expected. The Analyst only has tract-level CHAS cost-burden facts, which do not vary by housing type, so it cannot rank one product over another. Future work: HUD Fair Market Rents as a typology-mapped rent benchmark, plus HUD Income Limits so existing residents' ability to pay at that benchmark can be stated. Senior housing would remain unmapped to both sources.
- **Rationale:** Live Round 1 after the affordability guard produced 5/5/5/5/5/5. That is a data limitation, not a scoring bug.

## [Component 4 / 2026-09-27] Round 2 built, live-tested, and removed

- **Decision:** Do not run a cross-examination round. The pipeline is independent Round 1 → Chair → human weighting sliders. Round 2 was implemented and live-tested (Groq TPD exhausted; finished on `gemini-3.5-flash-lite`), then deleted uncommitted rather than reverted.
- **Rationale:** The five Analysts measure different, often orthogonal things (legal permission, financial return, distributional fairness, sustainability, demographics). Disagreement is usually the finding, not a misunderstanding. Live Round 2 notes mostly declined to change scores because each agent's objective does not depend on the others' — Pro Forma naming Zoning's apartment use-table barrier without moving its cost score is the honest pattern. Resolving that is the human's job via Component 6 sliders on cached Round 1 scores, not agent-to-agent negotiation.
- **Open questions:** None for this slice. Weighting sliders are Component 6.

## [Component 5 / 2026-09-27] Chair reads Round 1 only

- **Decision:** The Chair receives all five independent Round 1 assessments. `scores_by_agent` and the limitations panel are compiled in code (no fused ranking, no winner). The LLM only classifies per-typology **factual disputes** (possible data-reading discrepancy; flag for verification) vs **value disputes** (real trade-off between legitimate objectives). Schema retry once, then empty dispute lists with scores still attached. Classification is about statements, not score spread: incompatible claims about the same site attribute (e.g. Use Table permitted vs not) are factual even when the agents also have different missions; a score gap alone is a value dispute.
- **Adversarial check (not committed):** A copy of Round 1 cache with Sustainability's apartment Use Table claim flipped to "permitted (P)" against Zoning's "blank — not permitted." First Chair run labeled only a value dispute. After the prompt rule above, the same input produced a zoning vs sustainability **factual_dispute** (verify Use Table P vs blank) plus a separate **value_dispute** (permission vs carbon/density). Duplex (uncorrupted) stayed value-only.
- **Open questions:** None for this slice.

## [Component 6 / 2026-09-27] Human-weighted view over cached scores

- **Decision:** Ranking after Chair is a pure function (`apply_agent_weights`) of cached Round 1 scores, Chair disputes/limitations, and five user weights. No LLM. Default is equal 20% shares, labeled **equal-weight view**, not the answer. Weights are relative and normalized to sum to 1. Output per typology: weighted score, unique rank (ties keep Round 1 order), per-agent contribution (`weight × score`), that typology's `cannot_determine` by agent, and Chair factual/value disputes. If Equity scores are identical across typologies and its weight is positive, attach a precision note that raising Equity does not differentiate typologies.
- **Naming:** This is a user-weighted view. Do not call it consensus or the answer.
- **Exploration:** The first reveal converts a 1st–5th analyst preference into shares with rank-order centroid (`roc_weights`: \(w_k = \frac{1}{n}\sum_{i=k}^{n} 1/i\)). Later slider edits pass shares directly. Both call `apply_weighted_view` → `apply_agent_weights`. There is one ranking function.
- **API:** `GET /analysis/{site_id}` returns cached Round 1 + Chair or runs them once and writes `data/cache/analysis/{site_id}/`. A second GET never calls the LLM. `POST /weighted-view/{site_id}` only reads that cache and `apply_weighted_view`. Uncached sites other than the Brookline demo PIN return 404 instead of inventing a live GIS/LLM run. The Typescape page is served from `/`. Ranker move controls have visible text plus `aria-label`s; the parcel map uses a real `aria-label`.
- **Chrome:** One Pittsburgh housing photo plus `rgb(35 35 35 / 0.88)` scrim is a fixed site backdrop on every view. White was only a page wash; lists and the Help dialog stay opaque paper so ranking stays scannable. Primary actions use gold with ink text so they do not vanish into the scrim.
- **Open questions:** None for this slice.





