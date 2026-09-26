"""Which tools an agent is offered, and what it falls back to when it offers none."""

from __future__ import annotations

from app.agents.openai_agent import _tools_for_openai, _venue_fallback


def _names(tools: list[dict]) -> set[str]:
    return {t["function"]["name"] for t in tools}


def test_ungated_offers_every_action_except_travel():
    import app.oracle.world_data as wd

    assert _names(_tools_for_openai()) == set(wd.ACTIONS) - {"travel"}


def test_gated_offers_this_venue_plus_travel():
    assert _names(_tools_for_openai("bank", gated=True)) == {
        "invest",
        "lend",
        "audit",
        "will",
        "travel",
    }


def test_gated_at_the_plaza_offers_only_travel():
    assert _names(_tools_for_openai("plaza", gated=True)) == {"travel"}


def test_the_fallback_walks_toward_the_action_it_wanted():
    action, arguments = _venue_fallback("steal", venue="bank")

    assert action == "travel"
    assert arguments == {"venue": "alley"}


def test_the_fallback_from_nowhere_in_particular_still_moves():
    action, arguments = _venue_fallback(None, venue="plaza")

    assert action == "travel"
    assert arguments["venue"] in {"market", "bank", "lounge", "work", "alley", "casino"}
