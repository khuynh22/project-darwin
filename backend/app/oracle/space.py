"""Where an agent is, how long it takes to get elsewhere, and who saw it.

Location used to be decoration: ``frontend/lib/town.ts`` mapped an action to a
venue so the 3-D view had somewhere to put the pawn. Once actions occupy time,
position becomes a constraint with consequences.

Two of those consequences are what this module exists for.

**Travel costs time.** Choosing an action at a distant venue means paying for
the walk, so the cheap action nearby and the lucrative one across town are a
real trade-off rather than an equal choice.

**Presence is evidence.** An agent only witnesses what happens where it stands,
so information asymmetry stops being a configuration flag and becomes a fact
about the world. It also makes an alibi decidable: "I was at the farm" is now a
claim the trace can contradict, which is a deception the judge does not have to
adjudicate.

Coordinates come from ``shared/venues.json``, which the renderer reads too, so
the backend and the renderer cannot disagree about where a venue is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from app.oracle.clock import beats
from app.oracle.world_data import (
    ACTION_VENUE,
    ECONOMY,
    UBIQUITOUS_ACTIONS,
    VENUE_POS,
)

DEFAULT_VENUE: Final[str] = "plaza"

#: Stage units covered per beat of walking. Derived from the generated layout
#: by ``scripts/layout_venues.py`` so the longest crossing keeps costing three
#: beats however many buildings the town grows.
WALK_UNITS_PER_BEAT: Final[float] = ECONOMY.walk_units_per_beat

#: Venues where a conversation cannot be overheard by agents elsewhere. Every
#: venue is private in that sense; the plaza is the one public space, so a claim
#: made there is heard by everyone standing in the town.
PUBLIC_VENUE: Final[str] = "plaza"


def venue_for(action: str) -> str:
    """Where an agent stands after taking *action*. Always a built venue.

    A ubiquitous action's ``ACTION_VENUE`` entry is the ``anywhere`` sentinel,
    which is not a building: returning it would write a venue that is in neither
    ``BUILT_VENUES`` nor ``VENUE_POS`` onto the agent row and into the trace.
    """
    if action in UBIQUITOUS_ACTIONS:
        return DEFAULT_VENUE
    return ACTION_VENUE.get(action, DEFAULT_VENUE)


def travel_ticks(origin: str, destination: str) -> int:
    """Ticks needed to walk between two venues. Same venue costs nothing."""
    if origin == destination:
        return 0
    ox, oy = VENUE_POS.get(origin, VENUE_POS[DEFAULT_VENUE])
    dx, dy = VENUE_POS.get(destination, VENUE_POS[DEFAULT_VENUE])
    distance = math.hypot(dx - ox, dy - oy)
    return beats(distance / WALK_UNITS_PER_BEAT)


@dataclass(frozen=True)
class Placement:
    """Where one agent is over a half-open interval of simulation time.

    ``venue`` is where the agent ends up. While travelling it is nowhere, which
    is deliberate -- an agent in transit witnesses nothing and can be claimed to
    have been anywhere, which is exactly the ambiguity an alibi exploits.
    """

    agent_id: str
    venue: str
    arrives_at: int
    departs_at: int | None = None

    def present_at(self, tick: int) -> bool:
        if tick < self.arrives_at:
            return False
        return self.departs_at is None or tick < self.departs_at


def witnesses(
    placements: list[Placement], *, venue: str, tick: int, actor: str
) -> list[str]:
    """Agents other than ``actor`` standing at ``venue`` at ``tick``.

    An event at the plaza is public; anywhere else only the people there see it.
    """
    seen = {
        p.agent_id
        for p in placements
        if p.venue == venue and p.present_at(tick) and p.agent_id != actor
    }
    return sorted(seen)


def observable_by(
    placements: list[Placement], *, venue: str, tick: int, actor: str
) -> list[str]:
    if venue == PUBLIC_VENUE:
        return sorted({p.agent_id for p in placements if p.agent_id != actor})
    return witnesses(placements, venue=venue, tick=tick, actor=actor)


__all__ = [
    "ACTION_VENUE",
    "DEFAULT_VENUE",
    "PUBLIC_VENUE",
    "Placement",
    "VENUE_POS",
    "observable_by",
    "travel_ticks",
    "venue_for",
    "witnesses",
]
