from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from housing_review.data.assessments import AssessmentRecord, fetch_assessment
from housing_review.data.icc_bvd import costs_for_all_typologies
from housing_review.data.sales import SalesSlice, fetch_sales_slice

STRICT = ConfigDict(extra="forbid")


class ProFormaSiteContext(BaseModel):
    """County assessment + validated sales + labeled ICC BVD costs. Not a bid."""

    model_config = STRICT

    site_id: str
    assessment: AssessmentRecord
    sales: SalesSlice
    construction_cost: list[dict]
    size_proxy_finished_sf: int | None
    coverage_notes: list[str] = Field(default_factory=list)


def _notes(assessment: AssessmentRecord, sales: SalesSlice, living_sf: int | None) -> list[str]:
    notes = [
        "Decision support only — not legal, financial, or zoning advice.",
        assessment.caveat,
        sales.caveat,
        "Construction $/sf is ICC Building Valuation Data – AUGUST 2026, occupancy group and Type VB, national average. Not Pittsburgh-specific. No City PLI/BBI local ICC modifier was found on 2026-09-26.",
        "Any claim that multiplies ICC $/sf by floor area is estimated, not measured.",
        "Do not guess financing terms, interest rates, or developer profit margins.",
        "Do not assert demand — that is the Demographic Analyst's role.",
    ]
    if living_sf:
        notes.append(
            f"FINISHEDLIVINGAREA={living_sf} sf is the existing building size on the assessment record, "
            "used only as a size proxy. A different typology would have a different program."
        )
    parcel_sales = sales.parcel_sales
    if parcel_sales and not any(item.likely_arms_length for item in parcel_sales):
        notes.append(
            "This parcel's recorded transfer is not a VALID SALE (arm's-length filter); "
            "do not treat it as a comparable sale price."
        )
    return notes


def load_proforma_site(parid: str, *, zip_code: str | int | None = None) -> ProFormaSiteContext:
    assessment = fetch_assessment(parid)
    zip_code = zip_code or assessment.fields.get("PROPERTYZIP") or "15226"
    sales = fetch_sales_slice(parid, zip_code=zip_code)
    living = assessment.fields.get("FINISHEDLIVINGAREA")
    living_sf = int(living) if living is not None else None
    costs = costs_for_all_typologies()
    if living_sf:
        for item in costs:
            item["size_proxy_finished_sf"] = living_sf
            item["implied_building_cost_usd_estimated"] = round(living_sf * float(item["usd_per_sqft"]), 2)
    return ProFormaSiteContext(
        site_id=parid,
        assessment=assessment,
        sales=sales,
        construction_cost=costs,
        size_proxy_finished_sf=living_sf,
        coverage_notes=_notes(assessment, sales, living_sf),
    )


def load_proforma_site_from_path(path: Path) -> ProFormaSiteContext:
    payload = json.loads(path.read_text())
    return ProFormaSiteContext.model_validate(payload)
