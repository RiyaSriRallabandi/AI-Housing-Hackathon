from __future__ import annotations

from housing_review.data.chas import CHAS_CATALOG, CHAS_LAYER, CHAS_VINTAGE
from housing_review.data.equity import EquitySiteContext
from housing_review.schemas.analyst import Claim
from housing_review.schemas.common import Typology

DISPLACEMENT_GAP = (
    "CHAS does not measure who would move because of this project (displacement)."
)
PRICE_DATA_TOKEN = "price_data"
PRICE_DATA_GAP = (
    f"{PRICE_DATA_TOKEN}: likely sale/rent of a new unit of this typology is not in the Equity payload."
)
TYPOLOGY_AFFORDABILITY_GAP = (
    "Typology-specific affordability cannot be determined without sale or rent "
    "price data for that housing type."
)


def chas_source(context: EquitySiteContext, field: str) -> str:
    chas = context.chas
    return (
        f"CHAS {chas.vintage} Table 8 {field}, ArcGIS ACS_5YR_ESTIMATES_CHAS_TRACT "
        f"GEOID {chas.geoid}; {chas.source_url}; retrieved {chas.retrieved_on}"
    )


def deterministic_claims_for_typology(
    typology: Typology,
    context: EquitySiteContext,
) -> list[Claim]:
    del typology  # Tract CHAS is site-constant; typology does not change the lookup.
    chas = context.chas
    lag = chas.vintage_note
    return [
        Claim(
            statement=(
                f"{chas.cost_burden_gt_30_pct}% of occupied households were cost-burdened "
                f"(>30% of income) in {CHAS_VINTAGE} CHAS "
                f"({chas.cost_burden_gt_30_count} of {chas.occupied_households} households)."
            ),
            basis="measured",
            source=chas_source(context, "T8_CB_PCT"),
            confidence_note=lag,
        ),
        Claim(
            statement=(
                f"{chas.cost_burden_gt_50_pct}% of occupied households were severely "
                f"cost-burdened (>50% of income) in {CHAS_VINTAGE} CHAS."
            ),
            basis="measured",
            source=chas_source(context, "T8_CB50_PCT"),
            confidence_note=lag,
        ),
        Claim(
            statement=(
                f"{chas.hamfi_le_30_count} occupied households had income ≤30% HAMFI; "
                f"{chas.hamfi_le_30_cost_burden_pct}% of that band were cost-burdened. "
                f"{chas.hamfi_le_50_count} households ≤50% HAMFI; "
                f"{chas.hamfi_le_80_count} households ≤80% HAMFI."
            ),
            basis="measured",
            source=chas_source(context, "T8_LE30_CB_PCT"),
            confidence_note=lag,
        ),
    ]


def facts_pack_for_llm(context: EquitySiteContext) -> dict:
    chas = context.chas
    return {
        "geoid": context.geoid,
        "chas": {
            "vintage": chas.vintage,
            "tract_name": chas.tract_name,
            "occupied_households": chas.occupied_households,
            "cost_burden_gt_30_count": chas.cost_burden_gt_30_count,
            "cost_burden_gt_30_pct": chas.cost_burden_gt_30_pct,
            "cost_burden_gt_50_count": chas.cost_burden_gt_50_count,
            "cost_burden_gt_50_pct": chas.cost_burden_gt_50_pct,
            "hamfi_le_30_count": chas.hamfi_le_30_count,
            "hamfi_le_30_cost_burden_pct": chas.hamfi_le_30_cost_burden_pct,
            "hamfi_le_50_count": chas.hamfi_le_50_count,
            "hamfi_le_80_count": chas.hamfi_le_80_count,
            "source_url": chas.source_url,
            "layer": CHAS_LAYER,
            "catalog_url": CHAS_CATALOG,
            "retrieved_on": chas.retrieved_on,
            "vintage_note": chas.vintage_note,
            "caveat": chas.caveat,
        },
        "citation_templates": {
            "T8_CB_PCT": chas_source(context, "T8_CB_PCT"),
            "T8_CB50_PCT": chas_source(context, "T8_CB50_PCT"),
            "T8_LE30_CB_PCT": chas_source(context, "T8_LE30_CB_PCT"),
        },
    }


def code_side_cannot_determine() -> list[str]:
    return [
        DISPLACEMENT_GAP,
        "Useful HUD Income Limits and Location Affordability Index were not retrieved.",
        PRICE_DATA_GAP,
        TYPOLOGY_AFFORDABILITY_GAP,
    ]
