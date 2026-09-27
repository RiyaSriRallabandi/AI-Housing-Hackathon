from __future__ import annotations

import json

from housing_review.agents.zoning import run_zoning_analyst
from housing_review.data.site import load_zoning_site_from_fixtures
from housing_review.schemas import AnalystName, Typology

FIXTURES = __import__("pathlib").Path(__file__).resolve().parent / "fixtures"


def _fixture_context():
    return load_zoning_site_from_fixtures(
        FIXTURES / "parcel_0139F00077000000.geojson",
        FIXTURES / "zoning_r2l_sample.geojson",
    )


def _valid_assessment(typology: str, score: int, *, lookup: dict | None = None) -> dict:
    row = ((lookup or {}).get("citation_contract") or {}).get(typology) or {
        "use_source": "§911.02 Use Table",
        "parking_citation": "§914.02.A Parking Schedule A",
        "parking_minimum": "1 per unit",
        "parking_maximum": "2 per unit",
        "statuses": ["P"],
    }
    pmax = row.get("parking_maximum") or ""
    park_stmt = f"Schedule A minimum {row['parking_minimum']}"
    if pmax:
        park_stmt += f", maximum {pmax}"
    return {
        "agent": "zoning_analyst",
        "site_id": "0139F00077000000",
        "typology": typology,
        "score": score,
        "basis": "measured",
        "claims": [
            {
                "statement": f"Use status {row.get('statuses')}.",
                "basis": "measured",
                "source": row["use_source"],
            },
            {
                "statement": park_stmt,
                "basis": "measured",
                "source": row["parking_citation"],
            },
        ],
        "cannot_determine": [
            "Whether a variance would actually be granted.",
        ],
        "summary": "Assessment uses citation_contract sources only. Decision support only.",
    }


def test_config_default_model_is_central(monkeypatch) -> None:
    from housing_review import config

    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert config.LLM_MODEL == "openai/gpt-oss-120b"
    loaded = config.load_llm_config()
    assert loaded.model == "openai/gpt-oss-120b"
    assert loaded.provider == "groq"


def test_config_env_override(monkeypatch) -> None:
    from housing_review.config import load_llm_config

    monkeypatch.setenv("LLM_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("LLM_PROVIDER", "google_gemini")
    assert load_llm_config().model == "gemini-3.5-flash-lite"


def test_zoning_analyst_validates_mocked_round1() -> None:
    context = _fixture_context()
    lookup = context.code_lookup or {}
    typologies = [Typology.duplex, Typology.adu]
    payload = [
        _valid_assessment("duplex", 7, lookup=lookup),
        _valid_assessment("adu", 3, lookup=lookup),
    ]

    def fake_complete(system: str, user: str) -> str:
        assert "Zoning Analyst" in system
        assert "0139F00077000000" in user
        assert "geometry" not in user
        return json.dumps({"assessments": payload})

    results = run_zoning_analyst(context, typologies=typologies, completer=fake_complete)
    assert len(results) == 2
    assert results[0].agent is AnalystName.zoning_analyst
    assert results[0].typology is Typology.duplex
    assert results[0].score == 7


def test_zoning_analyst_retries_on_malformed_json() -> None:
    context = _fixture_context()
    calls = {"n": 0}

    def flaky(system: str, user: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps({"verdict": "best"})
        return json.dumps([_valid_assessment("duplex", 6, lookup=context.code_lookup)])

    results = run_zoning_analyst(
        context,
        typologies=[Typology.duplex],
        completer=flaky,
    )
    assert calls["n"] == 2
    assert results[0].score == 6
