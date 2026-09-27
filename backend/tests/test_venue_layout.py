from __future__ import annotations

import itertools
import math

from app.oracle import world_data as wd
from app.oracle.clock import BEAT
from scripts.layout_venues import FOOTPRINT, LONGEST_CROSSING_BEATS, PLAZA_REACH_BEATS

TOL = 1e-6


def _beats(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.dist(a, b) / wd.ECONOMY.walk_units_per_beat


def test_no_two_venues_overlap():
    for left, right in itertools.combinations(wd.VENUES.values(), 2):
        gap = math.dist((left.x, left.y), (right.x, right.y))
        assert gap >= FOOTPRINT, f"{left.id} and {right.id} are {gap:.1f} apart"


def test_plaza_is_within_reach_of_everything():
    plaza = wd.VENUE_POS["plaza"]
    for venue in wd.VENUES.values():
        assert _beats(plaza, (venue.x, venue.y)) <= PLAZA_REACH_BEATS + TOL, venue.id


def test_longest_crossing_costs_no_more_than_three_beats():
    worst = max(
        _beats((a.x, a.y), (b.x, b.y))
        for a, b in itertools.combinations(wd.VENUES.values(), 2)
    )
    assert worst <= LONGEST_CROSSING_BEATS + TOL


def test_every_venue_sits_inside_the_stage():
    for venue in wd.VENUES.values():
        assert 0.0 <= venue.x <= wd.ECONOMY.stage_w, venue.id
        assert 0.0 <= venue.y <= wd.ECONOMY.stage_h, venue.id


def test_layout_is_idempotent():
    from scripts.layout_venues import compute_layout

    rows = [v.model_dump() for v in wd.VENUES.values()]
    again, walk, stage_w, stage_h = compute_layout(rows)
    for before, after in zip(wd.VENUES.values(), again):
        assert math.isclose(before.x, after["x"], abs_tol=1e-3)
        assert math.isclose(before.y, after["y"], abs_tol=1e-3)
    assert math.isclose(walk, wd.ECONOMY.walk_units_per_beat, abs_tol=1e-3)
    assert math.isclose(stage_w, wd.ECONOMY.stage_w, abs_tol=1e-3)
    assert math.isclose(stage_h, wd.ECONOMY.stage_h, abs_tol=1e-3)


def test_a_walk_across_the_ring_is_measured_in_whole_ticks():
    # travel_ticks rounds to ticks; a neighbouring venue must still cost more
    # than nothing, or distance stops being a constraint at all.
    from app.oracle.space import travel_ticks

    assert travel_ticks("plaza", "market") > 0
    assert travel_ticks("market", "market") == 0
    assert BEAT == 1000
