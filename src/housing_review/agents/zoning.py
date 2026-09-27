from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from housing_review.data.demo_site import demo_site_record
from housing_review.data.site import ZoningSiteContext, load_zoning_site
from housing_review.llm import Completer, complete_json, parse_json_list
from housing_review.schemas import AnalystAssessment, Typology, parse_analyst_assessment

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "zoning_analyst_round1.txt"
CANDIDATE_TYPOLOGIES = list(Typology)
MAX_SCHEMA_RETRIES = 1


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _compact_site_context(context: ZoningSiteContext) -> dict:
    """Drop geometry and bulky overlay attributes so Groq's 8K TPM free cap is usable."""
    return {
        "site_id": context.site_id,
        "parcel": {
            "pin": context.parcel.pin,
            "map_block_lot": context.parcel.map_block_lot,
            "acreage": context.parcel.acreage,
            "lon": context.parcel.lon,
            "lat": context.parcel.lat,
        },
        "districts": [item.model_dump(mode="json") for item in context.districts],
        "code_lookup": context.code_lookup,
        "adu_overlay": context.adu_overlay,
        "overlays": [{"layer_id": hit.layer_id, "source_url": hit.source_url} for hit in context.overlays],
        "coverage_notes": context.coverage_notes,
    }


def _user_prompt(context: ZoningSiteContext, typologies: list[Typology], demo: dict | None) -> str:
    demo_slim = None
    if demo:
        demo_slim = {
            "address": (demo.get("address") or {}).get("full"),
            "neighborhood": (demo.get("neighborhood") or {}).get("name"),
        }
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_context": _compact_site_context(context),
        "demo_record": demo_slim,
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Assess each listed candidate typology using ONLY site_context. "
        "Look up use permissions in code_lookup.use_permissions_this_column "
        "for this site's mapped district column — do not assume R2-L. "
        "ADU Overlay membership is code_lookup plus adu_overlay.in_adu_overlay "
        "from the live map query. At most 2 claims per typology. "
        "Summaries max 2 sentences. Return JSON as "
        '{"assessments": [ ... ]}.\n'
        + json.dumps(payload)
    )


def run_zoning_analyst(
    context: ZoningSiteContext,
    *,
    typologies: list[Typology] | None = None,
    completer: Completer | None = None,
    demo_record: dict | None = None,
) -> list[AnalystAssessment]:
    """Round 1 Zoning Analyst. Completer is injectable so tests never need a live key."""
    typologies = typologies or CANDIDATE_TYPOLOGIES
    generate = completer or complete_json
    if len(typologies) > 3:
        combined: list[AnalystAssessment] = []
        for start in range(0, len(typologies), 3):
            combined.extend(
                run_zoning_analyst(
                    context,
                    typologies=typologies[start : start + 3],
                    completer=generate,
                    demo_record=demo_record,
                )
            )
        return combined
    system = _system_prompt()
    user = _user_prompt(context, typologies, demo_record)
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
                "Do not use text or citation."
            )
            continue
        return assessments
    raise ValueError(f"Zoning Analyst output failed schema validation: {last_error}\nRaw: {raw[:1000]}")


def run_zoning_analyst_for_demo(*, include_overlays: bool = True, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_zoning_site(record["pin"], include_overlays=include_overlays)
    return run_zoning_analyst(context, completer=completer, demo_record=record)


def _assert_round1_shape(
    assessments: list[AnalystAssessment],
    context: ZoningSiteContext,
    typologies: list[Typology],
) -> None:
    got = {item.typology for item in assessments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in Zoning Analyst output: {missing}")
    for item in assessments:
        if item.agent.value != "zoning_analyst":
            raise ValueError("agent must be zoning_analyst")
        if item.site_id != context.site_id:
            raise ValueError("site_id must match the parcel PIN")
