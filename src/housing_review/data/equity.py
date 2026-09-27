from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.chas import ChasTractSlice, fetch_chas_tract

STRICT = ConfigDict(extra="forbid")
DEMO_PIN = "0139F00077000000"
DEMO_GEOID = "42003191800"


class EquitySiteContext(BaseModel):
    """Tract CHAS cost-burden slice for the Equity Analyst. Not a displacement verdict."""

    model_config = STRICT

    site_id: str
    geoid: str
    chas: ChasTractSlice
    coverage_notes: list[str] = Field(default_factory=list)


def _notes(chas: ChasTractSlice) -> list[str]:
    return [
        "Decision support only — not legal, financial, or zoning advice.",
        chas.caveat,
        chas.vintage_note,
        "Frame findings as affordability mismatch risk, not measured displacement. "
        "CHAS does not track who would move because of a specific project.",
        "Do not assume market-rate housing is inherently harmful or subsidized housing "
        "inherently beneficial without grounding in this tract's income/cost-burden figures.",
        "Useful HUD Income Limits and Location Affordability Index were not retrieved.",
    ]


def load_equity_site(geoid: str, *, site_id: str = DEMO_PIN) -> EquitySiteContext:
    chas = fetch_chas_tract(geoid)
    return EquitySiteContext(
        site_id=site_id,
        geoid=chas.geoid,
        chas=chas,
        coverage_notes=_notes(chas),
    )


def load_equity_site_from_path(path: Path) -> EquitySiteContext:
    return EquitySiteContext.model_validate(json.loads(path.read_text()))
