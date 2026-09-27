"""No venue resolver may hand back something that is not a building.

``shared/actions.json`` carries a reserved non-venue value (``anywhere``) for
ubiquitous actions, and every consumer downstream -- the agent row, ``VENUE_POS``,
the trace's ``TurnState.venue``, the renderer's venue-keyed maps -- assumes a
built venue id. The sentinel leaking through ``venue_for`` is what corrupted the
agent row, so the rule gets a test of its own rather than living in the head of
whoever writes the next resolver.

The matching TypeScript half is ``frontend/lib/town.test.ts``.
"""

from __future__ import annotations

from app.oracle import world_data as wd
from app.oracle.space import DEFAULT_VENUE, venue_for


def test_venue_for_resolves_every_action_to_a_built_venue():
    for action_id in wd.ACTIONS:
        assert venue_for(action_id) in wd.BUILT_VENUES, action_id


def test_venue_for_resolves_an_unknown_action_to_a_built_venue():
    assert venue_for("teleport_sideways") in wd.BUILT_VENUES
    assert venue_for("") in wd.BUILT_VENUES


def test_a_ubiquitous_action_lands_at_the_default_venue():
    assert wd.UBIQUITOUS_ACTIONS
    for action_id in wd.UBIQUITOUS_ACTIONS:
        assert wd.ACTION_VENUE[action_id] == wd.ANYWHERE
        assert venue_for(action_id) == DEFAULT_VENUE


def test_every_built_venue_has_a_position():
    for venue_id in wd.BUILT_VENUES:
        assert venue_id in wd.VENUE_POS
