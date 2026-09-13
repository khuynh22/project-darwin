"""Fixed-point simulation time.

The world advances by discrete *events*, but its state is a continuous function
of time: hunger, tax and investment yield accrue as rates and are evaluated
lazily at whatever instant somebody looks. Nothing is stepped through.

Time is stored as an integer count of **ticks**, not a float. A run is only
reproducible if arithmetic on its clock is exact, and floating-point sums drift
once you add a few hundred irregular intervals together. ``BEAT`` gives the
resolution: one beat is the unit the old turn loop called a turn, so tuning
constants expressed in turns port across unchanged.
"""

from __future__ import annotations

from typing import Final

#: Ticks per beat. A beat is the historical "turn" -- tax cycles, contract
#: deadlines and office terms are all still counted in beats, so every number
#: tuned against the turn loop keeps its meaning.
BEAT: Final[int] = 1000

#: Smallest interval an agent may ask to sleep for. Zero would let an agent
#: schedule itself in a loop that never advances the clock.
MIN_WAKE: Final[int] = 1


def beats(n: float) -> int:
    """Convert beats to ticks, rounding to the nearest tick."""
    return round(n * BEAT)


def to_beats(ticks: int) -> float:
    """Convert ticks back to (possibly fractional) beats, for display and rates."""
    return ticks / BEAT


def elapsed_beats(start: int, end: int) -> float:
    """Beats between two instants. Negative spans are a scheduling bug, not data."""
    if end < start:
        raise ValueError(f"clock ran backwards: {start} -> {end}")
    return to_beats(end - start)
