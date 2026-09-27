from __future__ import annotations

import json
from pathlib import Path

import pytest

from housing_review.agents.equity import run_equity_analyst
from housing_review.agents.judgment import AgentJudgment
from housing_review.agents.summary_guards import (
    EQUITY_REVIEW_TASK,
    assert_equity_summaries_respect_unknown_price,
    review_equity_summaries_against_claims,
)
from housing_review.data.catalog import equity_analyst_sources
from housing_review.data.equity import load_equity_site_from_path
from housing_review.data.equity_facts import PRICE_DATA_TOKEN, TYPOLOGY_AFFORDABILITY_GAP
from housing_review.schemas import AnalystName, Typology
from housing_review.schemas.common import ConfidenceBasis

FIXTURES = Path(__file__).resolve().parent / "fixtures"

OK_SUMMARY = (
    "2013-2017 CHAS shows 18.45% of occupied households cost-burdened (>30% of income) "
    "and 8.15% severely cost-burdened (>50%). Typology-specific affordability cannot "
    "be determined without sale or rent price data."
)


def _judgment_payload(typology: str, summary: str) -> dict:
    return {
        "judgments": [
            {
                "typology": typology,
                "score": 7,
                "basis": "estimated",
                "summary": summary,
                "cannot_determine": [PRICE_DATA_TOKEN],
            }
        ]
    }


def _review_ok() -> str:
    return json.dumps({"overreach": False, "violations": []})


def _is_review(user: str) -> bool:
    return EQUITY_REVIEW_TASK in user


def test_chas_fixture_is_2013_2017_not_latest_hud() -> None:
    ctx = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")
    assert ctx.geoid == "42003191800"
    assert ctx.chas.vintage == "2013-2017"
    assert ctx.chas.cost_burden_gt_30_pct == 18.45
    assert ctx.chas.cost_burden_gt_50_pct == 8.15
    assert "2018-2022" in ctx.chas.vintage_note
    assert any("displacement" in note.lower() for note in ctx.coverage_notes)


def test_equity_sources_log_chas_vintage() -> None:
    records = equity_analyst_sources()
    assert any("CHAS" in item.name for item in records)
    chas = next(item for item in records if "CHAS" in item.name)
    assert "2013-2017" in chas.caveat
    assert "2018-2022" in chas.caveat


def test_equity_analyst_validates_mocked_round1() -> None:
    context = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")

    def fake(system: str, user: str) -> str:
        assert "Equity Analyst" in system or EQUITY_REVIEW_TASK in user
        if _is_review(user):
            return _review_ok()
        assert "2013-2017" in user
        assert "B25070" in system
        assert "deterministic_facts" in user
        return json.dumps(_judgment_payload("adu", OK_SUMMARY))

    results = run_equity_analyst(context, typologies=[Typology.adu], completer=fake)
    assert results[0].agent is AnalystName.equity_analyst
    assert results[0].score == 7
    assert "18.45" in results[0].claims[0].statement
    assert "T8_CB_PCT" in results[0].claims[0].source
    assert any("displacement" in note.lower() for note in results[0].cannot_determine)
    assert any("price_data" in note for note in results[0].cannot_determine)
    assert TYPOLOGY_AFFORDABILITY_GAP in results[0].cannot_determine


def test_equity_concept_guard_rejects_mismatch_phrasing() -> None:
    item = AgentJudgment(
        typology=Typology.duplex,
        score=5,
        basis=ConfidenceBasis.estimated,
        summary=(
            "This typology presents moderate affordability-mismatch risk relative "
            "to tract cost burdens."
        ),
        cannot_determine=[PRICE_DATA_TOKEN],
    )
    with pytest.raises(ValueError, match="typology-specific affordability"):
        assert_equity_summaries_respect_unknown_price([item], [PRICE_DATA_TOKEN])


def test_equity_concept_guard_allows_tract_chas_and_unknown_price() -> None:
    item = AgentJudgment(
        typology=Typology.townhome,
        score=5,
        basis=ConfidenceBasis.estimated,
        summary=OK_SUMMARY,
        cannot_determine=[PRICE_DATA_TOKEN],
    )
    assert_equity_summaries_respect_unknown_price([item], [PRICE_DATA_TOKEN])


def test_equity_rejects_affordable_summary_when_price_data_unknown() -> None:
    """Keyword dodge: 'affordability-mismatch risk' must still retry."""
    context = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")
    calls = {"n": 0}

    def fake(system: str, user: str) -> str:
        if _is_review(user):
            return _review_ok()
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps(
                _judgment_payload(
                    "duplex",
                    "Duplexes present moderate affordability-mismatch risk for current residents.",
                )
            )
        return json.dumps(_judgment_payload("duplex", OK_SUMMARY))

    results = run_equity_analyst(context, typologies=[Typology.duplex], completer=fake)
    assert calls["n"] == 2
    assert results[0].score == 7
    assert "mismatch" not in results[0].summary.lower()
    assert "affordable" not in results[0].summary.lower()
    assert "cannot be determined" in results[0].summary.lower()
    assert any("price_data" in note for note in results[0].cannot_determine)


def test_equity_semantic_review_retries_when_concept_check_misses() -> None:
    context = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")
    calls = {"judgments": 0, "reviews": 0}

    def fake(system: str, user: str) -> str:
        if _is_review(user):
            calls["reviews"] += 1
            if calls["reviews"] == 1:
                return json.dumps(
                    {
                        "overreach": True,
                        "violations": [
                            {
                                "typology": "duplex",
                                "reason": "Implies duplex would ease household housing-cost pressure.",
                            }
                        ],
                    }
                )
            return _review_ok()
        calls["judgments"] += 1
        sneaky = (
            "Tract CHAS shows 18.45% of occupied households cost-burdened. "
            "Duplex would ease pressure on local households given those figures."
        )
        if calls["judgments"] == 1:
            return json.dumps(_judgment_payload("duplex", sneaky))
        return json.dumps(_judgment_payload("duplex", OK_SUMMARY))

    results = run_equity_analyst(context, typologies=[Typology.duplex], completer=fake)
    assert calls["judgments"] == 2
    assert calls["reviews"] == 2
    assert "ease pressure" not in results[0].summary.lower()


def test_equity_semantic_review_function_flags_overreach() -> None:
    item = AgentJudgment(
        typology=Typology.apartment,
        score=6,
        basis=ConfidenceBasis.estimated,
        summary=OK_SUMMARY,
        cannot_determine=[PRICE_DATA_TOKEN],
    )

    def fake(system: str, user: str) -> str:
        assert EQUITY_REVIEW_TASK in user
        return json.dumps(
            {
                "overreach": True,
                "violations": [
                    {"typology": "apartment", "reason": "Implies apartment rents fit the tract."}
                ],
            }
        )

    with pytest.raises(ValueError, match="semantic review"):
        review_equity_summaries_against_claims(fake, [item], {Typology.apartment: []})


def test_equity_one_call_and_fallback() -> None:
    context = load_equity_site_from_path(FIXTURES / "equity_chas_42003191800.json")
    calls = {"n": 0}

    def fake(system: str, user: str) -> str:
        if _is_review(user):
            return _review_ok()
        calls["n"] += 1
        start = user.find('{"responsible_use"')
        payload, _ = json.JSONDecoder().raw_decode(user[start:])
        assert len(payload["candidate_typologies"]) == 6
        if calls["n"] == 1:
            return json.dumps({"verdict": "nope"})
        return json.dumps(
            {
                "judgments": [
                    {
                        "typology": "duplex",
                        "score": 6,
                        "basis": "estimated",
                        "summary": "ok duplex",
                        "cannot_determine": [],
                    },
                    {"typology": "apartment", "score": "bad"},
                ]
            }
        )

    results = run_equity_analyst(context, completer=fake)
    assert calls["n"] == 2
    by_typ = {item.typology: item for item in results}
    assert by_typ[Typology.duplex].score == 6
    assert by_typ[Typology.apartment].score == 0
    assert any("failed to produce valid" in note for note in by_typ[Typology.apartment].cannot_determine)
    assert "T8_CB_PCT" in by_typ[Typology.apartment].claims[0].source
