from __future__ import annotations

import json
from pathlib import Path

from housing_review.agents.judgment import collect_judgments, merge_assessment
from housing_review.data.demo_site import demo_site_record
from housing_review.data.proforma import ProFormaSiteContext, load_proforma_site_from_path
from housing_review.data.proforma_facts import (
    code_side_cannot_determine,
    deterministic_claims_for_typology,
    facts_pack_for_llm,
)
from housing_review.llm import Completer, complete_json
from housing_review.schemas import AnalystAssessment, Typology
from housing_review.schemas.common import AnalystName

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "pro_forma_analyst_round1.txt"
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "proforma_0139F00077000000.json"
CANDIDATE_TYPOLOGIES = list(Typology)


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _user_prompt(context: ProFormaSiteContext, typologies: list[Typology]) -> str:
    payload = {
        "responsible_use": "Decision support only — not legal, financial, or zoning advice.",
        "site_id": context.site_id,
        "deterministic_facts": facts_pack_for_llm(context, typologies),
        "candidate_typologies": [item.value for item in typologies],
    }
    return (
        "Score EVERY candidate typology in one comparative pass using ONLY "
        "deterministic_facts. Do not emit claims. Return JSON as "
        '{"judgments": [ ... ]}.\n'
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
    judgments = collect_judgments(
        generate,
        _system_prompt(),
        _user_prompt(context, typologies),
        typologies,
        agent_label="Pro Forma Analyst",
        claims_kept="Assessment, sales, and ICC cost claims were still attached from code.",
    )
    return [
        merge_assessment(
            agent=AnalystName.pro_forma_analyst,
            site_id=context.site_id,
            judgment=item,
            claims=deterministic_claims_for_typology(item.typology, context),
            extra_gaps=code_side_cannot_determine(item.typology),
        )
        for item in judgments
    ]


def run_pro_forma_analyst_for_demo(*, completer: Completer | None = None) -> list[AnalystAssessment]:
    record = demo_site_record()
    context = load_proforma_site_from_path(FIXTURE_PATH)
    if context.site_id != record["pin"]:
        raise ValueError("Pro Forma fixture site_id does not match demo PIN")
    return run_pro_forma_analyst(context, completer=completer)
