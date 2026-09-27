"""Places every venue on its district ring and writes the coordinates back.

Hand-placing twenty buildings is how two of them end up inside each other, and
how a walk across town quietly stops costing what the design says it costs.
The layout is therefore computed: districts occupy contiguous arcs so the town
reads as neighbourhoods, and walking speed is derived from the finished map so
the longest crossing keeps costing three beats however many buildings exist.

Planned venues are placed too. Reserving their coordinates now is what lets a
content pack turn one on without moving anything already built, so a trace
recorded today still puts pawns where they stood.

Run after editing shared/venues.json:

    python -m scripts.layout_venues
"""

from __future__ import annotations

import math

from app.oracle.world_data import load_json, write_json

#: Stage px across one building. Mirrors VENUE_FOOTPRINT in the renderer.
FOOTPRINT = 78.0

#: Clear space between neighbours. The dial to turn if the first-person walker
#: starts snagging between buildings.
GAP = 60.0

MARGIN = 20.0

LONGEST_CROSSING_BEATS = 3.0
PLAZA_REACH_BEATS = 1.5

SLOT = FOOTPRINT + GAP
INNER_DISTRICTS = ("civic",)
OUTER_DISTRICTS = ("industry", "vice")


def _ring_radius(count: int) -> float:
    if count == 0:
        return 0.0
    return max(SLOT * count / (2.0 * math.pi), SLOT)


def _place(rows: list[dict], radius: float, centre: float) -> None:
    count = len(rows)
    for index, row in enumerate(rows):
        angle = -math.pi / 2.0 + 2.0 * math.pi * index / count
        row["x"] = centre + radius * math.cos(angle)
        row["y"] = centre + radius * math.sin(angle)


def compute_layout(rows: list[dict]) -> tuple[list[dict], float, float, float]:
    by_district = {
        d: [r for r in rows if r["district"] == d]
        for d in ("plaza", "civic", "industry", "vice")
    }

    inner = [r for d in INNER_DISTRICTS for r in by_district[d]]
    outer = [r for d in OUTER_DISTRICTS for r in by_district[d]]

    inner_radius = _ring_radius(len(inner))
    outer_radius = max(_ring_radius(len(outer)), inner_radius + SLOT)
    centre = outer_radius + FOOTPRINT / 2.0 + MARGIN

    for row in by_district["plaza"]:
        row["x"] = centre
        row["y"] = centre
    _place(inner, inner_radius, centre)
    _place(outer, outer_radius, centre)

    longest = max(
        math.dist((a["x"], a["y"]), (b["x"], b["y"])) for a in rows for b in rows
    )
    # Both invariants at once: the far corner costs three beats, and the plaza
    # stays within one and a half of everything. With an odd ring the widest
    # chord is short of the diameter, so the plaza term is the binding one.
    # Rounded up, or the binding term lands exactly on its limit and the
    # rounding applied to the coordinates pushes it a hair over.
    walk = max(longest / LONGEST_CROSSING_BEATS, outer_radius / PLAZA_REACH_BEATS)
    walk = math.ceil(walk * 100.0) / 100.0
    stage = centre * 2.0
    return rows, walk, stage, stage


def main() -> None:
    rows = load_json("venues.json")
    assert isinstance(rows, list)
    rows, walk, stage_w, stage_h = compute_layout(rows)
    for row in rows:
        row["x"] = round(row["x"], 3)
        row["y"] = round(row["y"], 3)
    write_json("venues.json", rows)

    economy = load_json("economy.json")
    assert isinstance(economy, dict)
    economy["walk_units_per_beat"] = round(walk, 4)
    economy["stage_w"] = round(stage_w, 4)
    economy["stage_h"] = round(stage_h, 4)
    write_json("economy.json", economy)

    print(f"placed {len(rows)} venues; stage {stage_w:.0f}px; walk {walk:.1f} units/beat")


if __name__ == "__main__":
    main()
