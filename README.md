# AI Housing Hackathon

Decision-support tool for comparing housing typologies on a real Pittsburgh site.

**This is not legal, financial, or zoning advice.** Outputs are scenario comparisons with visible trade-offs, citations, confidence tiers, and explicit gaps. A human decision-maker still has to weigh the result and verify it with the relevant office before acting.

## What this system does

Five independent Analyst agents (zoning, demographics, financial feasibility, equity, sustainability) assess candidate typologies for a site. A Chair agent synthesizes their structured outputs: it does not invent new evidence, and it does not declare a single “correct” product type.

## Current status

Component 1 (shared contract) and Component 2 (Zoning data layer for one agent) are in place. Working example site: **170 Aidan Ct, Brookline** (PIN `0139F00077000000`, **R2-L**). No agents or LLM calls yet. §911.02 Use Table is still a labeled gap.

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

Copy `.env.example` to `.env` when runtime API keys are needed. Never commit `.env`.

## Libraries so far

- Python 3.11+
- Pydantic v2
- Shapely 2 (point-in-polygon on zoning GIS)
- pytest (dev)

## Data sources (Zoning slice)

See `data/SOURCE_LOG.md` for URLs, retrieval date (2026-09-26), and per-source gaps. Summary:

- Zoning map: WPRDC City of Pittsburgh zoning GeoJSON (catalog slug `pittsburgh-zoning` now 404s; dataset id is `zoning`).
- Parcels: Allegheny County Open Data Feature Service (WPRDC full file is huge; PASDA REST was down).
- Zoning code: Title 9 on eCode360 (https://ecode360.com/45474054). Chapter 903 dimensional/use-subdistrict rules retrieved 2026-09-26. **§911.02 Use Table not retrieved.**
- Official map: Instant App overlays joined by point (steep slope, historic, IZ, etc.).

## Limitations (will grow as sources are wired)

- Not legal, financial, or zoning advice.
- Zoning use permissions from §911.02 and accessory/ADU rules from Ch. 912 are **not** in the structured layer yet.
- Overlay slope flag at the demo parcel is screening-level only, not a geotechnical determination.
- Census tract for the demo site is a placeholder until TIGER/ACS is wired.
- Construction cost is not in the hackathon catalog; that gap is still a checkpoint.

## License / event

Built during the hackathon window. Challenge track: Track 3.
