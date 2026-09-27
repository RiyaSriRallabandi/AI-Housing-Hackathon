from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from housing_review.data.demo_site import demo_site_record
from housing_review.data.sustainability import (
    SustainabilitySiteContext,
    load_sustainability_site_from_path,
)
from housing_review.llm import Completer, complete_json, parse_json_list
from housing_review.schemas import AnalystAssessment, Typology, parse_analyst_assessment

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "sustainability_analyst_round1.txt"
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sustainability_0139F00077000000.json"
CANDIDATE_TYPOLOGIES = list(Typology)
MAX_SCHEMA_RETRIES = 1


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _compact_context(context: SustainabilitySiteContext) -> dict:
    flood = context.flood
    prt = context.prt
    return {
        "site_id": context.site_id,
        "lon": round(context.lon, 6),
        "lat": round(context.lat, 6),
        "flood": {
            "layer_covers_point": flood.layer_covers_point,
            "fld_zone": flood.fld_zone,
            "zone_subtype": flood.zone_subtype,
            "sfha_tf": flood.sfha_tf,
            "in_sfha": flood.in_sfha,
            "source_url": flood.source_url,
            "catalog_url": flood.catalog_url,
            "caveat": flood.caveat,
        },
        "steep_slope_25pct": {
            "flagged": context.steep_slope_25pct.flagged,
            "caveat": context.steep_slope_25pct.caveat,
        },
        "major_transit_buffer": {
            "in_1500ft_major_transit_buffer": context.major_transit_buffer.in_1500ft_major_transit_buffer,
            "note": context.major_transit_buffer.note,
        },
        "prt": {
            "resolved_url": prt.resolved_url,
            "resource_id": prt.resource_id,
            "feed_version": prt.feed_version,
            "unique_within_400m": prt.unique_within_400m,
            "unique_within_800m": prt.unique_within_800m,
            "unique_within_1500ft": prt.unique_within_1500ft,
            "nearest": [
                {
                    "stop_name": item.stop_name,
                    "mode": item.mode,
                    "route_code": item.route_code,
                    "hood": item.hood,
                    "distance_m": item.distance_m,
                    "trips_wd": item.trips_wd,
                    "from_gtfs": item.from_gtfs,
                }
                for item in prt.nearest[:6]
            ],
            "caveat": prt.caveat,
        },
        "carbon": {
            "rule": (
                "Generic typology-level direction only. Higher density generally "
                "lower per-unit carbon and less car-dependency than detached "
                "single-family. No site LCA. basis estimated."
            ),
            "basis": "estimated",
        },
        "coverage_notes": context.coverage_notes,
    }


def _user_prompt(context: SustainabilitySiteContext, typologies: list[Typology]) -> str:
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_context": _compact_context(context),
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Assess each listed candidate typology using ONLY site_context. "
        "Carbon claims must be basis estimated. Transit/flood claims must cite PRT or FEMA_2026. "
        "At most 2 claims per typology. Summaries max 2 sentences. "
        "Return JSON as "
        '{"assessments": [ ... ]}.\n'
        + json.dumps(payload)
    )


def run_sustainability_analyst(
    context: SustainabilitySiteContext,
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
                run_sustainability_analyst(
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
                "agent must be sustainability_analyst."
            )
            continue
        return assessments
    raise ValueError(
        f"Sustainability Analyst output failed schema validation: {last_error}\nRaw: {raw[:1000]}"
    )


def run_sustainability_analyst_for_demo(*, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_sustainability_site_from_path(FIXTURE_PATH)
    if context.site_id != record["pin"]:
        raise ValueError("Sustainability fixture site_id does not match demo PIN")
    return run_sustainability_analyst(context, completer=completer)


def _assert_round1_shape(
    assessments: list[AnalystAssessment],
    context: SustainabilitySiteContext,
    typologies: list[Typology],
) -> None:
    got = {item.typology for item in assessments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in Sustainability Analyst output: {missing}")
    for item in assessments:
        if item.agent.value != "sustainability_analyst":
            raise ValueError("agent must be sustainability_analyst")
        if item.site_id != context.site_id:
            raise ValueError("site_id must match the parcel PIN")
