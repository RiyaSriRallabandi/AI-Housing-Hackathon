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


def _compact_code_lookup(lookup: dict | None) -> dict:
    """Send structured citation rows, not raw chapter dumps the model can mine."""
    if not lookup:
        return {}
    return {
        "mapped_districts": lookup.get("mapped_districts"),
        "use_table_column": lookup.get("use_table_column"),
        "use_table_legend": lookup.get("use_table_legend"),
        "typology_title9_names": lookup.get("typology_title9_names"),
        "use_permissions_this_column": lookup.get("use_permissions_this_column"),
        "citation_contract": lookup.get("citation_contract"),
        "chapter_903_density_excerpt": lookup.get("chapter_903_density_excerpt"),
    }


def _compact_site_context(context: ZoningSiteContext) -> dict:
    """Drop geometry and bulky overlay attributes so Groq's 8K TPM free cap is usable."""
    lookup = context.code_lookup or {}
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
        "citation_contract": lookup.get("citation_contract") or {},
        "code_lookup": _compact_code_lookup(lookup),
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
        "JSON typology slugs stay as listed (townhome, not townhouse). "
        "Cite Title 9 names from code_lookup.typology_title9_names "
        "(townhome = Single-Unit Attached Residential). "
        "Copy citation_contract[typology].use_source exactly on the use claim. "
        "Copy citation_contract[typology].parking_citation exactly on the parking "
        "claim and quote parking_minimum and parking_maximum in that statement. "
        "ADU Overlay membership is adu_overlay.in_adu_overlay from the live map query. "
        "At most 2 claims per typology. "
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
            assert_structured_citations(assessments, context.code_lookup or {})
        except (ValidationError, ValueError, TypeError) as exc:
            last_error = exc
            user = (
                user
                + "\n\nYour previous output failed schema validation: "
                + str(exc)
                + "\nReturn a JSON object {\"assessments\": [...]} only. "
                "Include every candidate typology. Each claim must use keys "
                "statement, basis, source (optional confidence_note). "
                "Do not use text or citation. "
                "Copy citation_contract use_source and parking_citation exactly. "
                "Parking statements must include parking_minimum and parking_maximum."
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


def _source_copies_contract(actual: str, required: str) -> bool:
    got = (actual or "").strip()
    need = (required or "").strip()
    return bool(need) and got == need


def assert_structured_citations(assessments: list[AnalystAssessment], lookup: dict) -> None:
    """Use-table and parking claim sources must equal the structured contract strings."""
    contract = lookup.get("citation_contract") or {}
    errors: list[str] = []
    for item in assessments:
        row = contract.get(item.typology.value)
        if not row:
            errors.append(f"{item.typology.value}: missing citation_contract row")
            continue
        use_src = row.get("use_source") or ""
        park_src = row.get("parking_citation") or ""
        pmin = row.get("parking_minimum") or ""
        pmax = row.get("parking_maximum") or ""
        if not any(_source_copies_contract(claim.source, use_src) for claim in item.claims):
            errors.append(
                f"{item.typology.value}: permitted-use claim source must equal {use_src!r}"
            )
        park_ok = False
        for claim in item.claims:
            if not _source_copies_contract(claim.source, park_src):
                continue
            missing = [label for label, value in (("minimum", pmin), ("maximum", pmax)) if value and value not in claim.statement]
            if missing:
                errors.append(
                    f"{item.typology.value}: parking statement missing {missing} from citation_contract"
                )
                continue
            park_ok = True
        if not park_ok:
            errors.append(
                f"{item.typology.value}: parking claim source must equal {park_src!r} "
                "and quote parking_minimum/parking_maximum"
            )
    if errors:
        raise ValueError("Structured citation mismatch:\n" + "\n".join(errors))
