from __future__ import annotations

import json
from pathlib import Path

from housing_review.schemas import Typology

BVD_PATH = Path(__file__).resolve().parents[3] / "data" / "icc_bvd_august_2026.json"


def load_bvd() -> dict:
    return json.loads(BVD_PATH.read_text())


def cost_for_typology(typology: Typology | str, *, construction_type: str | None = None) -> dict:
    """National ICC BVD $/sf for one brief typology. Always estimated, never measured."""
    table = load_bvd()
    slug = typology.value if isinstance(typology, Typology) else typology
    occupancy = table["occupancy_for_typology"][slug]
    ctype = construction_type or table["default_construction_type"]
    row = table["square_foot_costs_usd"][occupancy]
    usd = row[ctype]
    modifier = table["pittsburgh_local_modifier"]
    return {
        "typology": slug,
        "table_title": table["table_title"],
        "source_url": table["source_url"],
        "retrieved_on": table["retrieved_on"],
        "occupancy_group": occupancy,
        "occupancy_label": row["label"],
        "construction_type": ctype,
        "usd_per_sqft": usd,
        "pittsburgh_local_modifier_found": modifier["found"],
        "regional_adjustment": None if not modifier["found"] else modifier,
        "basis": "estimated",
        "citation": (
            f"{table['table_title']} ({table['source_url']}); occupancy {occupancy} "
            f"({row['label']}), construction type {ctype}; ${usd:.2f}/sf national average. "
            "Not Pittsburgh-specific. ICC: not an estimating guide; excludes land."
        ),
        "national_average_note": table["national_average_note"],
        "not_an_estimating_guide": table["not_an_estimating_guide"],
        "pittsburgh_modifier_note": modifier["note"],
    }


def costs_for_all_typologies() -> list[dict]:
    return [cost_for_typology(item) for item in Typology]
