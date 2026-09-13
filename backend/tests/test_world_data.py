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


def test_space_reads_the_shared_table():
    from app.oracle import space

    assert space.ACTION_VENUE is wd.ACTION_VENUE
    assert space.VENUE_POS is wd.VENUE_POS
    assert space.WALK_UNITS_PER_BEAT == wd.ECONOMY.walk_units_per_beat


def test_the_alley_is_further_from_the_bank_than_the_plaza_is():
    from app.oracle.space import travel_ticks

    assert travel_ticks("alley", "bank") > travel_ticks("plaza", "bank")


def test_downstream_modules_read_one_table():
    from app.oracle import accrual, durations, schemas

    assert durations.ACTION_BEATS is wd.ACTION_BEATS
    assert schemas.MAJOR_ACTIONS == wd.MAJOR_ACTIONS
    assert schemas.FREE_ACTIONS == wd.FREE_ACTIONS
    assert schemas.GOODS == tuple(wd.GOODS)
    assert schemas.GOOD_VALUES == {g: r.base_price for g, r in wd.GOODS.items()}
    assert accrual.TAX_BRACKETS == tuple(wd.ECONOMY.tax_brackets)
    assert accrual.TAX_CYCLE_BEATS == wd.ECONOMY.tax_cycle_beats
    assert accrual.HUNGER_PENALTY_PER_BEAT == wd.ECONOMY.hunger_penalty_per_beat


def test_every_action_is_wired_end_to_end():
    from app.agents.stub import DEFAULT_BIAS
    from app.oracle.actions import ACTION_TABLE
    from app.oracle.schemas import ARG_MODELS

    for action_id in wd.ACTIONS:
        assert action_id in ARG_MODELS, f"{action_id} has no argument model"
        assert action_id in ACTION_TABLE, f"{action_id} has no handler"
        assert action_id in DEFAULT_BIAS, f"{action_id} is unreachable from the stub"
    assert set(ARG_MODELS) == set(wd.ACTIONS)
    assert set(DEFAULT_BIAS) == set(wd.ACTIONS)
