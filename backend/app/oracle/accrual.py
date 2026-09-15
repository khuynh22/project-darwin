"""The economy as a rate rather than a cycle.

The turn loop charged tax and checked hunger every ten turns, so nothing at all
happened for nine turns and then a cliff arrived. That is easy to game and hard
to reason about once agents no longer share a cadence: an agent that slept
through the cycle boundary would pay nothing.

Here the same pressures are continuous. Over ten beats a constant balance pays
exactly what the old ten-turn cycle charged, so every constant tuned against the
turn loop keeps its meaning -- but the pressure is now proportional to time
lived, which is what makes sleeping a real decision instead of a free hiding
place.

Accrual is settled on **whole-beat boundaries**, never on the raw event
interval. If it were charged per event, an agent's tax bill would depend on how
often the other agents happened to wake, and the economy would run faster in a
chatty world than a quiet one. Settling on a fixed grid makes the result
independent of how time was chopped into events.

One deliberate divergence from the turn loop: a continuous drain compounds
within the cycle. The old loop took 15% of $10.00 in one stroke ($1.50); ten
beats of per-beat drain take $1.00, because each beat is charged against an
already-reduced balance that falls into a lower bracket partway through.
Effective take is therefore below the nominal bracket rate, by more at higher
balances. This is the correct continuous reading of the same schedule, but it is
a real ~33% reduction in tax pressure at $10 and any comparison against a
turn-loop run has to account for it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.oracle.clock import BEAT
from app.oracle.world_data import ECONOMY

#: Beats that one unit of food sustains an agent for. Matches the old ten-turn
#: hunger cycle: one food per ten turns, or the penalty.
FOOD_BEATS_PER_UNIT: float = 10.0

#: Charged per beat spent with an empty stomach. Ten beats of starvation costs
#: $1.00, the old cycle's hunger penalty.
HUNGER_PENALTY_PER_BEAT: float = ECONOMY.hunger_penalty_per_beat

#: Beats the old tax cycle spanned. Bracket rates are divided by this to become
#: per-beat rates.
TAX_CYCLE_BEATS: float = ECONOMY.tax_cycle_beats

TAX_BRACKETS: tuple[tuple[float, float], ...] = tuple(ECONOMY.tax_brackets)


def tax_rate(balance: float) -> float:
    """Marginal bracket rate for a balance, as the turn loop defined it."""
    for ceiling, rate in TAX_BRACKETS:
        if balance < ceiling:
            return rate
    return TAX_BRACKETS[-1][1]


@dataclass
class Wallet:
    """The slice of an agent's state that changes on its own over time."""

    balance: float
    food: int = 0
    food_buffer: float = 0.0
    tax_paid: float = 0.0
    hunger_paid: float = 0.0
    starved_beats: float = 0.0
    tax_exempt: bool = False


@dataclass
class AccrualResult:
    beats_settled: int = 0
    tax: float = 0.0
    hunger: float = 0.0
    food_eaten: int = 0
    events: list[str] = field(default_factory=list)


def _settle_one_beat(wallet: Wallet, result: AccrualResult) -> None:
    if wallet.food_buffer < 1.0 / FOOD_BEATS_PER_UNIT and wallet.food > 0:
        wallet.food -= 1
        wallet.food_buffer += 1.0
        result.food_eaten += 1
        result.events.append("ate")

    drain = 1.0 / FOOD_BEATS_PER_UNIT
    if wallet.food_buffer >= drain:
        wallet.food_buffer = round(wallet.food_buffer - drain, 6)
    else:
        wallet.food_buffer = 0.0
        wallet.starved_beats += 1.0
        penalty = HUNGER_PENALTY_PER_BEAT
        wallet.balance = round(wallet.balance - penalty, 2)
        wallet.hunger_paid = round(wallet.hunger_paid + penalty, 2)
        result.hunger = round(result.hunger + penalty, 2)

    if not wallet.tax_exempt and wallet.balance > 0:
        due = round(wallet.balance * tax_rate(wallet.balance) / TAX_CYCLE_BEATS, 4)
        if due > 0:
            wallet.balance = round(wallet.balance - due, 2)
            wallet.tax_paid = round(wallet.tax_paid + due, 2)
            result.tax = round(result.tax + due, 4)


def accrue(wallet: Wallet, *, from_tick: int, to_tick: int) -> AccrualResult:
    """Advance one agent's wallet across an interval, beat by whole beat.

    Ticks inside a partial beat are carried, not dropped: the next call picks up
    from the same grid, so a run settles the same total however finely it was
    sliced.
    """
    if to_tick < from_tick:
        raise ValueError(f"clock ran backwards: {from_tick} -> {to_tick}")

    result = AccrualResult()
    first = from_tick // BEAT + 1
    last = to_tick // BEAT
    for _ in range(first, last + 1):
        _settle_one_beat(wallet, result)
        result.beats_settled += 1
    return result


__all__ = [
    "AccrualResult",
    "FOOD_BEATS_PER_UNIT",
    "HUNGER_PENALTY_PER_BEAT",
    "TAX_BRACKETS",
    "Wallet",
    "accrue",
    "tax_rate",
]
