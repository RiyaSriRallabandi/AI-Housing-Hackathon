from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from housing_review.data.demo_site import demo_site_record
from housing_review.data.equity import EquitySiteContext, load_equity_site_from_path
from housing_review.llm import Completer, complete_json, parse_json_list
from housing_review.schemas import AnalystAssessment, Typology, parse_analyst_assessment

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "equity_analyst_round1.txt"
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "equity_chas_42003191800.json"
CANDIDATE_TYPOLOGIES = list(Typology)
MAX_SCHEMA_RETRIES = 1


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _compact_context(context: EquitySiteContext) -> dict:
    chas = context.chas
    return {
        "site_id": context.site_id,
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
            "vintage_note": chas.vintage_note,
            "caveat": chas.caveat,
        },
        "coverage_notes": context.coverage_notes,
    }


def _user_prompt(context: EquitySiteContext, typologies: list[Typology]) -> str:
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_context": _compact_context(context),
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Assess each listed candidate typology using ONLY site_context. "
        "Cite CHAS 2013-2017, not ACS B25070. "
        "At most 2 claims per typology. Summaries max 2 sentences. "
        "Return JSON as "
        '{"assessments": [ ... ]}.\n'
        + json.dumps(payload)
    )


def run_equity_analyst(
    context: EquitySiteContext,
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
                run_equity_analyst(
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
                "agent must be equity_analyst."
            )
            continue
        return assessments
    raise ValueError(f"Equity Analyst output failed schema validation: {last_error}\nRaw: {raw[:1000]}")


def run_equity_analyst_for_demo(*, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_equity_site_from_path(FIXTURE_PATH)
    if context.site_id != record["pin"]:
        raise ValueError("Equity fixture site_id does not match demo PIN")
    return run_equity_analyst(context, completer=completer)


def _assert_round1_shape(
    assessments: list[AnalystAssessment],
    context: EquitySiteContext,
    typologies: list[Typology],
) -> None:
    got = {item.typology for item in assessments}
    missing = [item for item in typologies if item not in got]
    if missing:
        raise ValueError(f"Missing typologies in Equity Analyst output: {missing}")
    for item in assessments:
        if item.agent.value != "equity_analyst":
            raise ValueError("agent must be equity_analyst")
        if item.site_id != context.site_id:
            raise ValueError("site_id must match the parcel PIN")
