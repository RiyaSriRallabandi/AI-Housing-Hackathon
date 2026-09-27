from __future__ import annotations

import json

from housing_review.agents.chair import compile_limitations, run_chair
from housing_review.agents.summary_guards import EQUITY_REVIEW_TASK
from housing_review.debate import load_demo_round1_contexts, run_round1
from housing_review.schemas.chair import RESPONSIBLE_USE_NOTE
from housing_review.schemas.common import AnalystName, Typology
from housing_review.schemas.debate import AGENT_ORDER

EQ_SUMMARY = (
    "2013-2017 CHAS shows 18.45% of occupied households cost-burdened (>30% of income). "
    "Typology-specific affordability cannot be determined without sale or rent price data."
)


def _payload_from_user(user: str) -> dict:
    start = user.find('{"responsible_use"')
    assert start >= 0
    payload, _end = json.JSONDecoder().raw_decode(user[start:])
    return payload


def _r1_completer():
    def fake(system: str, user: str) -> str:
        if EQUITY_REVIEW_TASK in user:
            return json.dumps({"overreach": False, "violations": []})
        payload = _payload_from_user(user)
        typs = payload["candidate_typologies"]
        equity = "Equity Analyst" in system
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": typology,
                        "score": 5 if equity else 7,
                        "basis": "estimated",
                        "summary": EQ_SUMMARY if equity else f"Comparative note for {typology}.",
                        "cannot_determine": ["Gap A"] if typology == "adu" else [],
                    }
                    for typology in typs
                ]
            }
        )

    return fake


def _round1():
    contexts = load_demo_round1_contexts()
    return run_round1(contexts, completers={name: _r1_completer() for name in AGENT_ORDER})


def test_chair_attaches_round1_scores_and_compiles_limitations() -> None:
    round1 = _round1()
    calls = {"n": 0}

    def chair_ok(system: str, user: str) -> str:
        calls["n"] += 1
        assert "Chair" in system
        assert "winner" not in user.lower() or "Do not" in system
        payload = _payload_from_user(user)
        assert "round_1" in payload
        return json.dumps(
            {
                "typology_comparison": [
                    {
                        "typology": typology,
                        "factual_disputes": [],
                        "value_disputes": [
                            {
                                "issue": "Zoning-style certainty vs Equity tract CHAS.",
                                "agents_involved": ["zoning_analyst", "equity_analyst"],
                                "framing": "Legal permission and distributional facts are different questions.",
                            }
                        ],
                    }
                    for typology in payload["candidate_typologies"]
                ]
            }
        )

    result = run_chair(round1, completer=chair_ok)
    assert calls["n"] == 1
    assert result.site_id == round1.site_id
    assert result.responsible_use_note == RESPONSIBLE_USE_NOTE
    assert len(result.typology_comparison) == len(Typology)
    duplex = next(item for item in result.typology_comparison if item.typology is Typology.duplex)
    assert duplex.scores_by_agent[AnalystName.zoning_analyst] == 7
    assert duplex.scores_by_agent[AnalystName.equity_analyst] == 5
    assert duplex.value_disputes[0].agents_involved
    questions = {(item.raised_by, item.question) for item in result.limitations}
    assert (AnalystName.zoning_analyst, "Gap A") in questions
    adu_gaps = [item for item in result.limitations if item.question == "Gap A"]
    assert len(adu_gaps) == 5


def test_chair_rejects_winner_then_falls_back_without_changing_scores() -> None:
    round1 = _round1()
    calls = {"n": 0}

    def bad_then_incomplete(system: str, user: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"winner": "duplex", "typology_comparison": []})
        return json.dumps(
            {
                "typology_comparison": [
                    {
                        "typology": "duplex",
                        "factual_disputes": [],
                        "value_disputes": [],
                    }
                ]
            }
        )

    result = run_chair(round1, completer=bad_then_incomplete)
    assert calls["n"] == 2
    duplex = next(item for item in result.typology_comparison if item.typology is Typology.duplex)
    assert duplex.scores_by_agent[AnalystName.zoning_analyst] == 7
    apartment = next(item for item in result.typology_comparison if item.typology is Typology.apartment)
    assert apartment.factual_disputes == []
    assert apartment.value_disputes == []


def test_compile_limitations_dedupes_same_agent_note() -> None:
    round1 = _round1()
    limitations = compile_limitations(round1)
    equity_price = [
        item
        for item in limitations
        if item.raised_by is AnalystName.equity_analyst and "price_data" in item.question
    ]
    assert len(equity_price) == 1
