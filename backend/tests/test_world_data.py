from __future__ import annotations

import math

from app.oracle import world_data as wd


def test_every_action_belongs_to_exactly_one_built_venue():
    seen: dict[str, str] = {}
    for venue in wd.BUILT_VENUES.values():
        for action_id in venue.actions:
            assert action_id not in seen, f"{action_id} is in {seen.get(action_id)} and {venue.id}"
            seen[action_id] = venue.id
    assert set(seen) == set(wd.ACTIONS)


def test_action_venue_is_the_inverse_of_venue_actions():
    for action_id, venue_id in wd.ACTION_VENUE.items():
        assert action_id in wd.VENUE_ACTIONS[venue_id]


def test_tiers_partition_the_action_set():
    assert wd.MAJOR_ACTIONS | wd.FREE_ACTIONS == set(wd.ACTIONS)
    assert not (wd.MAJOR_ACTIONS & wd.FREE_ACTIONS)


def test_free_actions_take_no_time():
    for action_id in wd.FREE_ACTIONS:
        assert wd.ACTION_BEATS[action_id] == 0.0


def test_planned_venues_carry_no_actions():
    for venue in wd.VENUES.values():
        if venue.status == "planned":
            assert venue.actions == []


def test_top_tax_bracket_is_unbounded():
    ceiling, rate = wd.ECONOMY.tax_brackets[-1]
    assert math.isinf(ceiling)
    assert rate == 0.20


def test_goods_match_the_engine_defaults():
    assert {g: row.base_price for g, row in wd.GOODS.items()} == {
        "ore": 0.30,
        "food": 0.25,
        "tech": 0.50,
    }
