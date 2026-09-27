# AI Housing Hackathon

Decision-support tool for comparing housing typologies on a real Pittsburgh site.

**This is not legal, financial, or zoning advice.** Outputs are scenario comparisons with visible trade-offs, citations, confidence tiers, and explicit gaps. A human decision-maker still has to weigh the result and verify it with the relevant office before acting.

## What this system does

Five independent Analyst agents (zoning, demographics, financial feasibility, equity, sustainability) assess candidate typologies for a site. A Chair agent synthesizes their structured outputs: it does not invent new evidence, and it does not declare a single “correct” product type.

## Current status

Component 1 (shared contract), Component 2 Zoning + Demographic + Pro Forma + Equity data, and Round 1 Zoning, Demographic, Pro Forma, and Equity Analysts are in place. Shared LLM is Groq `openai/gpt-oss-120b`. Working example site: **170 Aidan Ct, Brookline**, Census tract **42003191800**.

## Shared output contract

Every Analyst assessment must validate against `housing_review.schemas.AnalystAssessment`:

| Field | Rule |
|---|---|
| `agent` | One of the five Analysts |
| `site_id` | Non-empty |
| `typology` | `duplex` \| `apartment` \| `townhome` \| `adu` \| `senior_housing` \| `detached_single_family` |
| `score` | Integer 0–10 |
| `basis` | `measured` \| `trend_inferred` \| `estimated` |
| `claims[]` | Each claim has `statement`, `basis`, `source`, optional `confidence_note` |
| `cannot_determine` | Required list; use `[]` if nothing is unanswerable |
| `summary` | Short plain-language synthesis |

Round 2 uses `AnalystAssessmentRound2`, which additionally requires `round_2_notes`. Extra fields are rejected.

The Chair uses `ChairSynthesis` (per-typology scores, factual vs value disputes, compiled limitations, mandatory responsible-use note).

Malformed agent JSON should be rejected and retried, not silently accepted.

## Setup

Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Copy `.env.example` to `.env` and set `GROQ_API_KEY` (console.groq.com, no card). All agents read `LLM_MODEL` from `housing_review.config` (default `openai/gpt-oss-120b`). Do not put model names in agent modules.

## Libraries so far

- Python 3.11+
- Pydantic v2
- Shapely 2 (point-in-polygon on zoning GIS)
- google-genai (Gemini API client, optional fallback)
- groq (default runtime: `openai/gpt-oss-120b`)
- python-dotenv

## Data sources (Zoning slice)

See `data/SOURCE_LOG.md` for URLs, retrieval date (2026-09-26), and per-source gaps. Summary:

- Zoning map: WPRDC City of Pittsburgh zoning GeoJSON (catalog slug `pittsburgh-zoning` now 404s; dataset id is `zoning`).
- Parcels: Allegheny County Open Data Feature Service (WPRDC full file is huge; PASDA REST was down).
- Zoning code: Title 9 on eCode360 (https://ecode360.com/45474054). Residential-relevant Chapters 903, 911 (full §911.02 Use Table), 912, 913, and 914 retrieved 2026-09-26 via browser (Cloudflare blocks naive curl). Files in `data/zoning_corpus/`.
- Official map: Instant App overlays joined by point (steep slope, historic, IZ, ADU overlay query, etc.).

## Data sources (Demographic slice)

- Tract join: Census Geocoder (TIGER Current) at the parcel centroid → GEOID `42003191800`.
- ACS 5-Year and 2020 Decennial via data.census.gov (api.census.gov requires a key). Details in `data/SOURCE_LOG.md`.

## Data sources (Pro Forma slice)

- Assessments and sales: WPRDC (assessed value ≠ market; only SALECODE 0 VALID SALE as comps).
- Construction $/sf: ICC Building Valuation Data – AUGUST 2026, Type VB, national average. Pittsburgh PLI/BBI published no local ICC modifier (2026-09-26 search). Dependent scores are `estimated`.

## Data sources (Equity slice)

- HUD CHAS via ArcGIS `ACS_5YR_ESTIMATES_CHAS_TRACT` for GEOID `42003191800`. Vintage **2013–2017** (older than HUD’s 2018–2022 release). Cost burden, not displacement.

## Limitations (will grow as sources are wired)

- Not legal, financial, or zoning advice.
- Corpus is a deliberate residential subset (Ch. 903, 911, 912, 913, 914), not the full Title 9.
- Overlay slope flag at the demo parcel is screening-level only, not a geotechnical determination.
- ACS tract estimates have margins of error; vacancy by units-in-structure and USPS postal vacancy are not retrieved.
- Construction $/sf is ICC BVD August 2026 (national average, Type VB), not a Pittsburgh bid.
- Equity CHAS for this tract is 2013–2017, older than HUD’s 2018–2022 release.

## License / event

Built during the hackathon window. Challenge track: Track 3.
