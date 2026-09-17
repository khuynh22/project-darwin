"""The shared world tables, loaded once and validated on import.

Venues, actions, goods and the economic constants live in ``shared/`` as JSON
because the engine and the renderer must agree about them exactly. An action
the backend charges three beats for and the frontend draws at the wrong
building is not a display bug -- it is two different worlds, and a trace
recorded in one cannot be read in the other.

The Pydantic models below are the schema. A malformed row raises here, at
import, so the Oracle refuses to start rather than serving half a world.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


def _find_shared_dir() -> Path:
    override = os.environ.get("DARWIN_SHARED_DIR")
    if override:
        return Path(override)
    # Walk up rather than counting parents: the repo has app/ at depth 3 and
    # the image has it at depth 2, and hardcoding either breaks the other.
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "shared"
        if (candidate / "venues.json").is_file():
            return candidate
    raise RuntimeError("shared/ not found: set DARWIN_SHARED_DIR")


SHARED_DIR = _find_shared_dir()


def load_json(name: str) -> object:
    return json.loads((SHARED_DIR / name).read_text(encoding="utf-8"))


def write_json(name: str, payload: object) -> None:
    path = SHARED_DIR / name
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class ActionRow(BaseModel):
    id: str
    tier: Literal["major", "free"]
    family: str
    venue: str
    beats: float
    emoji: str
    intent: str
    summary: str


class VenueRow(BaseModel):
    id: str
    label: str
    district: Literal["plaza", "civic", "industry", "vice"]
    status: Literal["built", "planned"]
    x: float
    y: float
    actions: list[str]


class GoodRow(BaseModel):
    id: str
    base_price: float


class Economy(BaseModel):
    tax_brackets: list[tuple[float, float]]
    tax_cycle_beats: float
    hunger_penalty_per_beat: float
    walk_units_per_beat: float
    stage_w: float
    stage_h: float


def _load_economy() -> Economy:
    raw = load_json("economy.json")
    assert isinstance(raw, dict)
    brackets = [
        (math.inf if ceiling is None else float(ceiling), float(rate))
        for ceiling, rate in raw["tax_brackets"]
    ]
    return Economy(**{**raw, "tax_brackets": brackets})


def _rows(name: str) -> list[dict]:
    rows = load_json(name)
    assert isinstance(rows, list)
    return rows


VENUES: dict[str, VenueRow] = {
    row["id"]: VenueRow(**row) for row in _rows("venues.json")
}
ACTIONS: dict[str, ActionRow] = {
    row["id"]: ActionRow(**row) for row in _rows("actions.json")
}
GOODS: dict[str, GoodRow] = {row["id"]: GoodRow(**row) for row in _rows("goods.json")}
ECONOMY: Economy = _load_economy()

BUILT_VENUES: dict[str, VenueRow] = {
    vid: row for vid, row in VENUES.items() if row.status == "built"
}


def _validate() -> None:
    owner: dict[str, str] = {}
    for venue in VENUES.values():
        if venue.status == "planned" and venue.actions:
            raise ValueError(f"planned venue {venue.id} lists actions")
        for action_id in venue.actions:
            if action_id not in ACTIONS:
                raise ValueError(f"venue {venue.id} lists unknown action {action_id}")
            if action_id in owner:
                raise ValueError(
                    f"action {action_id} is at {owner[action_id]} and {venue.id}"
                )
            owner[action_id] = venue.id
    missing = set(ACTIONS) - set(owner)
    if missing:
        raise ValueError(f"actions with no venue: {sorted(missing)}")
    for action in ACTIONS.values():
        if action.venue != owner[action.id]:
            raise ValueError(
                f"{action.id} claims {action.venue}, listed at {owner[action.id]}"
            )
        if action.tier == "free" and action.beats != 0.0:
            raise ValueError(f"free action {action.id} must take zero beats")


_validate()

ACTION_VENUE: dict[str, str] = {aid: row.venue for aid, row in ACTIONS.items()}
VENUE_ACTIONS: dict[str, list[str]] = {
    vid: list(row.actions) for vid, row in VENUES.items()
}
MAJOR_ACTIONS: frozenset[str] = frozenset(
    a.id for a in ACTIONS.values() if a.tier == "major"
)
FREE_ACTIONS: frozenset[str] = frozenset(
    a.id for a in ACTIONS.values() if a.tier == "free"
)
ACTION_BEATS: dict[str, float] = {aid: row.beats for aid, row in ACTIONS.items()}
VENUE_POS: dict[str, tuple[float, float]] = {
    vid: (row.x, row.y) for vid, row in VENUES.items()
}

__all__ = [
    "ACTIONS",
    "ACTION_BEATS",
    "ACTION_VENUE",
    "BUILT_VENUES",
    "ECONOMY",
    "FREE_ACTIONS",
    "GOODS",
    "MAJOR_ACTIONS",
    "SHARED_DIR",
    "VENUES",
    "VENUE_ACTIONS",
    "VENUE_POS",
    "ActionRow",
    "Economy",
    "GoodRow",
    "VenueRow",
    "load_json",
    "write_json",
]
