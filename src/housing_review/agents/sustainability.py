from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.judgment import collect_judgments, merge_assessment
from housing_review.agents.summary_guards import assert_sustainability_summaries_are_comparative
from housing_review.data.demo_site import demo_site_record
from housing_review.data.sustainability import (
    SustainabilitySiteContext,
    load_sustainability_site_from_path,
)
from housing_review.data.sustainability_facts import (
    code_side_cannot_determine,
    deterministic_claims_for_typology,
    facts_pack_for_llm,
)
from housing_review.llm import Completer, complete_json
from housing_review.schemas import AnalystAssessment, Typology
from housing_review.schemas.common import AnalystName

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "sustainability_analyst_round1.txt"
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sustainability_0139F00077000000.json"
CANDIDATE_TYPOLOGIES = list(Typology)


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _user_prompt(context: SustainabilitySiteContext, typologies: list[Typology]) -> str:
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_id": context.site_id,
        "attached_claims": facts_pack_for_llm(context, typologies),
        "code_side_cannot_determine": code_side_cannot_determine(),
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Score EVERY candidate typology in one comparative pass using ONLY "
        "attached_claims (the cited claim statements). Do not use any other "
        "numbers. Do not emit claims. Return JSON as "
        '{"judgments": [ ... ]}.\n'
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
    extra = code_side_cannot_determine()
    judgments = collect_judgments(
        generate,
        _system_prompt(),
        _user_prompt(context, typologies),
        typologies,
        agent_label="Sustainability Analyst",
        claims_kept="Transit, flood, and generic carbon claims were still attached from code.",
        check=assert_sustainability_summaries_are_comparative,
    )
    return [
        merge_assessment(
            agent=AnalystName.sustainability_analyst,
            site_id=context.site_id,
            judgment=item,
            claims=deterministic_claims_for_typology(item.typology, context),
            extra_gaps=extra,
        )
        for item in judgments
    ]


def run_sustainability_analyst_for_demo(*, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_sustainability_site_from_path(FIXTURE_PATH)
    if context.site_id != record["pin"]:
        raise ValueError("Sustainability fixture site_id does not match demo PIN")
    return run_sustainability_analyst(context, completer=completer)
