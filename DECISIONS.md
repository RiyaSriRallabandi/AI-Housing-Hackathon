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
