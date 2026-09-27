from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from housing_review.data.demo_site import demo_site_record
from housing_review.data.proforma import ProFormaSiteContext, load_proforma_site_from_path
from housing_review.llm import Completer, complete_json, parse_json_list
from housing_review.schemas import AnalystAssessment, Typology, parse_analyst_assessment

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "pro_forma_analyst_round1.txt"
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "proforma_0139F00077000000.json"
CANDIDATE_TYPOLOGIES = list(Typology)
MAX_SCHEMA_RETRIES = 1


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _compact_context(context: ProFormaSiteContext) -> dict:
    land = context.assessment.fields
    comps = [
        {
            "date": item.sale_date,
            "price": item.price,
            "address": item.address,
            "arms_length": item.likely_arms_length,
        }
        for item in context.sales.comparable_valid_sales[:8]
    ]
    costs = [
        {
            "typology": item["typology"],
            "occupancy_group": item["occupancy_group"],
            "construction_type": item["construction_type"],
            "usd_per_sqft": item["usd_per_sqft"],
            "implied_building_cost_usd_estimated": item.get("implied_building_cost_usd_estimated"),
            "citation": item["citation"],
            "basis": "estimated",
        }
        for item in context.construction_cost
    ]
    return {
        "site_id": context.site_id,
        "assessment": {
            "parid": land.get("PARID"),
            "fair_market_land": land.get("FAIRMARKETLAND"),
            "fair_market_building": land.get("FAIRMARKETBUILDING"),
            "fair_market_total": land.get("FAIRMARKETTOTAL"),
            "lot_area_sf": land.get("LOTAREA"),
            "finished_living_area_sf": land.get("FINISHEDLIVINGAREA"),
            "year_built": land.get("YEARBLT"),
            "use_desc_assessment": land.get("USEDESC"),
            "sale_price_on_record": land.get("SALEPRICE"),
            "sale_desc_on_record": land.get("SALEDESC"),
            "caveat": context.assessment.caveat,
        },
        "parcel_sales": [item.model_dump(mode="json") for item in context.sales.parcel_sales],
        "comparable_valid_sales_zip": comps,
        "construction_cost": costs,
        "coverage_notes": context.coverage_notes,
    }


def _user_prompt(context: ProFormaSiteContext, typologies: list[Typology]) -> str:
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_context": _compact_context(context),
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Assess each listed candidate typology using ONLY site_context. "
        "ICC construction cost claims must be basis estimated. "
        "At most 2 claims per typology. Summaries max 2 sentences. "
        "Return JSON as "
        '{"assessments": [ ... ]}.\n'
        + json.dumps(payload)
    )


def run_pro_forma_analyst(
    context: ProFormaSiteContext,
    *,
    typologies: list[Typology] | None = None,
    completer: Completer | None = None,
) -> list[AnalystAssessment]:
    typologies = typologies or CANDIDATE_TYPOLOGIES
    generate = completer or complete_json
    if len(typologies) > 3:
        combined: list[AnalystAssessment] = []
        for start in range(0, len(typologies), 3):
            combined.extend(
                run_pro_forma_analyst(
                    context,
                    typologies=typologies[start : start + 3],
                    completer=generate,
                )
            )
        return combined
    system = _system_prompt()
    user = _user_prompt(context, typologies)
    last_error: Exception | None = None
    raw = ""
    for _ in range(MAX_SCHEMA_RETRIES + 1):
        raw = generate(system, user)
        try:
            items = parse_json_list(raw)
            assessments = [parse_analyst_assessment(item) for item in items]
            _assert_round1_shape(assessments, context, typologies)
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            user = (
                user
                + "\n\nYour previous output failed schema validation: "
                + str(exc)
                + "\nReturn a JSON object {\"assessments\": [...]} only. "
                "Include every candidate typology. Each claim must use keys "
                "statement, basis, source (optional confidence_note). "
                "agent must be pro_forma_analyst."
            )
            continue
        return assessments
    raise ValueError(f"Pro Forma Analyst output failed schema validation: {last_error}\nRaw: {raw[:1000]}")


def run_pro_forma_analyst_for_demo(*, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_proforma_site_from_path(FIXTURE_PATH)
    if context.site_id != record["pin"]:
        raise ValueError("Pro Forma fixture site_id does not match demo PIN")
    return run_pro_forma_analyst(context, completer=completer)


def _assert_round1_shape(
    assessments: list[AnalystAssessment],
    context: ProFormaSiteContext,
    typologies: list[Typology],
) -> None:
    got = {item.typology for item in assessments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in Pro Forma Analyst output: {missing}")
    for item in assessments:
        if item.agent.value != "pro_forma_analyst":
            raise ValueError("agent must be pro_forma_analyst")
        if item.site_id != context.site_id:
            raise ValueError("site_id must match the parcel PIN")
