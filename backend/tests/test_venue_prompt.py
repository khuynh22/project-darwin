from __future__ import annotations

from app.agents.base import render_venue_block


def test_the_current_venue_is_described_in_full():
    block = render_venue_block("bank")

    assert block.startswith("YOU ARE AT: Bank (civic district)")
    assert "invest(" in block
    assert "Tax-exempt while locked" in block


def test_other_venues_are_one_line_each_with_a_walk_cost():
    block = render_venue_block("bank")
    elsewhere = block.split("ELSEWHERE")[1]

    assert "Market" in elsewhere
    assert "trade" in elsewhere
    # Costs are printed, and standing at the bank is not a cost.
    assert "Bank" not in elsewhere
    assert "beats" in block


def test_planned_venues_are_invisible():
    block = render_venue_block("bank")

    for hidden in ("Courthouse", "Registry", "Press", "Tavern", "Farm", "Temple"):
        assert hidden not in block


def test_an_unknown_venue_falls_back_to_the_plaza():
    block = render_venue_block("atlantis")

    assert block.startswith("YOU ARE AT: Plaza")


def test_the_world_brief_carries_the_block():
    from app.agents.base import render_world_brief

    state = {
        "turn": 3,
        "agents": [
            {"agent_id": "red", "display_name": "Red", "balance": 10.0, "alive": True},
        ],
        "_venue": "alley",
    }
    brief = render_world_brief(state, "red")

    assert "YOU ARE AT: Alley" in brief
    assert "steal(" in brief


async def test_the_turn_loop_tells_each_agent_where_it_stands():
    from app.agents.base import AgentDecision, BaseAgent
    from app.models.agent import Agent
    from app.oracle.engine import _decide_one

    class Spy(BaseAgent):
        seen: str | None = None

        async def decide(self, state, agent):
            Spy.seen = state.get("_venue")
            return AgentDecision(action="work", arguments={})

    row = Agent(session_id="s", agent_id="red", display_name="Red", provider="stub",
                personality="x", sprite="red", venue="alley")
    await _decide_one(Spy("red", "spy"), {"turn": 1, "agents": []}, row, [], [])

    assert Spy.seen == "alley"
