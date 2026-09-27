from __future__ import annotations

import json

import pytest

from housing_review.debate import load_demo_round1_contexts, run_round1
from housing_review.debate.round1 import Round1Contexts
from housing_review.schemas.common import AnalystName, Typology
from housing_review.schemas.debate import AGENT_ORDER


def test_demo_round1_zoning_gets_overlay_screen_from_sustainability_fixture() -> None:
    contexts = load_demo_round1_contexts()
    assert contexts.zoning.adu_overlay is not None
    assert contexts.zoning.adu_overlay["in_adu_overlay"] is False
    layers = {hit.layer_id for hit in contexts.zoning.overlays}
    assert "steep_slopes_25pct" in layers
    assert "floodplain_fema_2026" in layers


def _payload_from_user(user: str) -> dict:
    start = user.rfind('{"responsible_use"')
    assert start >= 0
    return json.loads(user[start:])


def _assessment(agent: str, typology: str, token: str) -> dict:
    return {
        "agent": agent,
        "site_id": "0139F00077000000",
        "typology": typology,
        "score": 5,
        "basis": "estimated",
        "claims": [
            {
                "statement": f"{agent} round1 {token} for {typology}",
                "basis": "estimated",
                "source": f"fixture:{agent}",
            }
        ],
        "cannot_determine": ["Peer Analyst claims (Round 1 has no visibility)."],
        "summary": f"Independent {agent} note {token}.",
    }


def _completer(agent: str, token: str, seen_users: list[str]):
    def fake(system: str, user: str) -> str:
        seen_users.append(user)
        payload = _payload_from_user(user)
        typs = payload["candidate_typologies"]
        items = [_assessment(agent, typology, token) for typology in typs]
        return json.dumps({"assessments": items})

    return fake


def test_round1_runs_five_agents_without_peer_transcripts() -> None:
    contexts = load_demo_round1_contexts()
    tokens = {
        AnalystName.zoning_analyst: "ZONESECRET",
        AnalystName.demographic_analyst: "DEMOSECRET",
        AnalystName.pro_forma_analyst: "PROSECRET",
        AnalystName.equity_analyst: "EQSECRET",
        AnalystName.sustainability_analyst: "SUSTSECRET",
    }
    seen: dict[AnalystName, list[str]] = {name: [] for name in AGENT_ORDER}
    completers = {
        name: _completer(name.value, tokens[name], seen[name]) for name in AGENT_ORDER
    }

    result = run_round1(contexts, completers=completers)

    assert result.independent is True
    assert result.round == "1"
    assert result.site_id == "0139F00077000000"
    assert result.agents_in_order == list(AGENT_ORDER)
    by_agent = result.by_agent()
    assert set(by_agent) == set(AGENT_ORDER)
    for name in AGENT_ORDER:
        typs = {item.typology for item in by_agent[name]}
        assert typs == set(Typology)
        assert len(by_agent[name]) == len(Typology)

    # Later agents must not see earlier agents' secret tokens (independence).
    leaked = []
    for index, name in enumerate(AGENT_ORDER):
        blob = "\n".join(seen[name])
        for earlier in AGENT_ORDER[:index]:
            if tokens[earlier] in blob:
                leaked.append((name.value, tokens[earlier]))
    assert leaked == []


def test_round1_rejects_mismatched_site_ids() -> None:
    contexts = load_demo_round1_contexts()
    with pytest.raises(ValueError, match="mismatch"):
        Round1Contexts(
            site_id="other",
            zoning=contexts.zoning,
            demographic=contexts.demographic,
            pro_forma=contexts.pro_forma,
            equity=contexts.equity,
            sustainability=contexts.sustainability,
        )
