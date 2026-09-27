# AI Housing Hackathon

Decision-support tool for comparing housing typologies on a real Pittsburgh site.

**This is not legal, financial, or zoning advice.** Outputs are scenario comparisons with visible trade-offs, citations, confidence tiers, and explicit gaps. A human decision-maker still has to weigh the result and verify it with the relevant office before acting.

## What this system does

Five independent Analyst agents (zoning, demographics, financial feasibility, equity, sustainability) assess candidate typologies for a site. A Chair agent synthesizes their structured outputs: it does not invent new evidence, and it does not declare a single “correct” product type.

## Current status

Component 1 — shared data contract — is in place. No agents, data fetches, or UI yet.

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
- pytest (dev)

## Limitations (will grow as sources are wired)

- No site assessment pipeline yet.
- No live data. Source coverage, retrieval dates, and per-site caveats will be logged as the data layer is built.
- Construction cost is not in the hackathon catalog; that gap will be handled as a checkpoint, not guessed away.

## License / event

Built during the hackathon window. Challenge track: Track 3.
