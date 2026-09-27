from __future__ import annotations

from statistics import median

from housing_review.data.assessments import ASSESSMENTS_DATASET, ASSESSMENTS_RESOURCE_ID
from housing_review.data.proforma import ProFormaSiteContext
from housing_review.data.sales import SALES_DATASET, SALES_RESOURCE_ID
from housing_review.schemas.analyst import Claim
from housing_review.schemas.common import Typology

WHOLE_HOUSE_TYPOLOGIES = {Typology.adu, Typology.apartment, Typology.senior_housing}

INCREMENT_GAP = (
    "FINISHEDLIVINGAREA on the existing building is a size proxy for a full replacement, "
    "not the increment for an ADU or a different multi-unit program."
)
FINANCING_GAP = "Financing terms, interest rates, and developer profit margins are not in the payload."


def _cost_row(context: ProFormaSiteContext, typology: Typology) -> dict:
    for item in context.construction_cost:
        if item.get("typology") == typology.value:
            return item
    raise KeyError(f"No ICC cost row for {typology.value}")


def land_source(context: ProFormaSiteContext) -> str:
    assessment = context.assessment
    parid = assessment.fields.get("PARID") or context.site_id
    return (
        f"WPRDC property assessments PARID {parid} FAIRMARKETLAND; "
        f"{assessment.source_url}; resource {ASSESSMENTS_RESOURCE_ID}; {ASSESSMENTS_DATASET}"
    )


def sales_source(context: ProFormaSiteContext) -> str:
    sales = context.sales
    return (
        f"WPRDC real-estate sales resource {SALES_RESOURCE_ID}; {sales.source_url}; "
        f"{SALES_DATASET}; retrieved {sales.retrieved_on}"
    )


def comps_median(context: ProFormaSiteContext) -> dict | None:
    prices = sorted(
        float(item.price)
        for item in context.sales.comparable_valid_sales
        if item.price is not None
    )
    if not prices:
        return None
    return {"n": len(prices), "median_usd": round(float(median(prices)), 2)}


def deterministic_claims_for_typology(
    typology: Typology,
    context: ProFormaSiteContext,
) -> list[Claim]:
    land = context.assessment.fields
    cost = _cost_row(context, typology)
    parcel_sale = context.sales.parcel_sales[0] if context.sales.parcel_sales else None
    claims = [
        Claim(
            statement=(
                f"Assessed land value is ${land.get('FAIRMARKETLAND')}; "
                f"building ${land.get('FAIRMARKETBUILDING')}; "
                f"total ${land.get('FAIRMARKETTOTAL')}; "
                f"lot {land.get('LOTAREA')} sf; FINISHEDLIVINGAREA={land.get('FINISHEDLIVINGAREA')} sf."
            ),
            basis="measured",
            source=land_source(context),
            confidence_note=context.assessment.caveat,
        ),
        Claim(
            statement=(
                f"ICC {cost.get('table_title')} occupancy {cost.get('occupancy_group')} "
                f"({cost.get('occupancy_label')}), construction type {cost.get('construction_type')}: "
                f"${cost.get('usd_per_sqft')}/sf national average. "
                f"Implied building cost using existing {context.size_proxy_finished_sf} sf proxy: "
                f"${cost.get('implied_building_cost_usd_estimated')} (estimated)."
            ),
            basis="estimated",
            source=cost["citation"],
            confidence_note=(
                "National average, not Pittsburgh-specific. ICC is not an estimating guide and excludes land."
            ),
        ),
    ]
    if parcel_sale:
        claims.append(
            Claim(
                statement=(
                    f"This parcel's recorded transfer is {parcel_sale.sale_desc} "
                    f"on {parcel_sale.sale_date} at ${parcel_sale.price}; "
                    f"likely_arms_length={parcel_sale.likely_arms_length}. "
                    f"{len(context.sales.comparable_valid_sales)} zip-filtered VALID SALE comps were retrieved."
                ),
                basis="measured",
                source=sales_source(context),
                confidence_note=context.sales.caveat,
            )
        )
    stats = comps_median(context)
    if stats:
        claims.append(
            Claim(
                statement=(
                    f"Median price of {stats['n']} zip-filtered VALID SALE comps is "
                    f"${stats['median_usd']} (code-computed sample median, not a market appraisal)."
                ),
                basis="measured",
                source=sales_source(context),
                confidence_note=(
                    "Median of the retrieved VALID SALE sample only. Do not recompute "
                    "medians or averages from a raw comps list."
                ),
            )
        )
    return claims


def facts_pack_for_llm(context: ProFormaSiteContext, typologies: list[Typology]) -> dict:
    land = context.assessment.fields
    costs = []
    for typology in typologies:
        row = _cost_row(context, typology)
        costs.append(
            {
                "typology": row["typology"],
                "occupancy_group": row["occupancy_group"],
                "construction_type": row["construction_type"],
                "usd_per_sqft": row["usd_per_sqft"],
                "implied_building_cost_usd_estimated": row.get("implied_building_cost_usd_estimated"),
                "citation": row["citation"],
                "basis": "estimated",
                "whole_house_proxy": typology in WHOLE_HOUSE_TYPOLOGIES,
            }
        )
    stats = comps_median(context)
    return {
        "assessment": {
            "parid": land.get("PARID"),
            "fair_market_land": land.get("FAIRMARKETLAND"),
            "fair_market_building": land.get("FAIRMARKETBUILDING"),
            "fair_market_total": land.get("FAIRMARKETTOTAL"),
            "lot_area_sf": land.get("LOTAREA"),
            "finished_living_area_sf": land.get("FINISHEDLIVINGAREA"),
            "year_built": land.get("YEARBLT"),
            "use_desc_assessment": land.get("USEDESC"),
            "caveat": context.assessment.caveat,
            "source": land_source(context),
        },
        "parcel_sales": [item.model_dump(mode="json") for item in context.sales.parcel_sales],
        "comparable_valid_sales_zip": {
            "n": stats["n"] if stats else 0,
            "median_usd": stats["median_usd"] if stats else None,
            "note": (
                "Median was computed in code from VALID SALE comps. "
                "Do not calculate a median, mean, or other aggregate from individual sale prices."
            ),
            "source": sales_source(context),
        },
        "sales_source": sales_source(context),
        "construction_cost": costs,
        "size_proxy_finished_sf": context.size_proxy_finished_sf,
    }


def code_side_cannot_determine(typology: Typology) -> list[str]:
    gaps = [FINANCING_GAP]
    if typology in WHOLE_HOUSE_TYPOLOGIES:
        gaps.append(INCREMENT_GAP)
    return gaps
