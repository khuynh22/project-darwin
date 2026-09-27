"""A gated stub only proposes what the building it stands in offers."""

from __future__ import annotations

import random

from app.agents.stub import DEFAULT_BIAS, StubAgent
from app.models.agent import Agent
from app.oracle.world_data import actions_at


def _agent() -> Agent:
    return Agent(
        session_id="s",
        agent_id="red",
        display_name="Red",
        provider="stub",
        personality="x",
        sprite="red",
        balance=10.0,
        venue="plaza",
    )


def _state(venue: str) -> dict:
    return {
        "turn": 1,
        "agents": [{"agent_id": "red", "balance": 10.0, "alive": True}],
        "_venue": venue,
        "_venue_gating": True,
    }


def test_travel_has_a_bias_weight():
    assert DEFAULT_BIAS["travel"] > 0


def test_a_gated_stub_at_the_plaza_can_only_travel():
    from app.oracle.world_data import BUILT_VENUES

    stub = StubAgent(agent_id="red", model="stub")
    for seed in range(50):
        decision = stub._pick_major(_state("plaza"), _agent(), random.Random(seed))
        assert decision.action == "travel"
        assert decision.arguments["venue"] in BUILT_VENUES
        assert decision.arguments["venue"] != "plaza"


def test_a_gated_stub_in_the_bank_stays_inside_the_bank_menu():
    stub = StubAgent(agent_id="red", model="stub")
    allowed = set(actions_at("bank", gated=True))
    for seed in range(50):
        decision = stub._pick_major(_state("bank"), _agent(), random.Random(seed))
        assert decision.action in allowed


def test_a_gated_stub_at_the_market_with_nothing_to_settle_stays_on_menu():
    """sign_contract/fulfil_contract's "nothing to do" branches must not fall
    back to a literal "work" -- the Market does not offer it."""
    stub = StubAgent(agent_id="red", model="stub")
    allowed = set(actions_at("market", gated=True))
    assert "work" not in allowed
    for seed in range(50):
        decision = stub._pick_major(_state("market"), _agent(), random.Random(seed))
        assert decision.action in allowed


def test_an_ungated_stub_is_unchanged():
    stub = StubAgent(agent_id="red", model="stub")
    state = {
        "turn": 1,
        "agents": [{"agent_id": "red", "balance": 10.0, "alive": True}],
        "_venue": "plaza",
    }
    seen = {
        stub._pick_major(state, _agent(), random.Random(seed)).action
        for seed in range(200)
    }
    assert "travel" not in seen
    assert len(seen) > 3
