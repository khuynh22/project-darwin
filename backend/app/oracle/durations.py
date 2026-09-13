"""How long an action occupies the agent that took it.

An instantaneous action cannot be interrupted, cannot be witnessed in progress,
and costs nothing to choose -- which is why the turn loop could not represent
labour, exposure, or the advantage of deciding quickly. Giving actions duration
makes all three measurable.

Two costs are charged, and they are different things:

**Action duration** is world-facing. It is how long the agent is busy and
therefore absent: a six-beat shift at the mine is six beats during which it can
be robbed and cannot answer.

**Deliberation cost** is cognition-facing. It is derived from the tokens the
model actually spent, so an agent that reasons at length genuinely acts later
than one that answers immediately, and can be beaten to a scarce good by it.
Tokens are used rather than measured latency on purpose: wall-clock latency is
mostly provider queueing and rate limiting, which is infrastructure noise, and
including it would make a trace unreplayable for no gain in realism.
"""

from __future__ import annotations

from app.oracle.clock import BEAT, beats

# ACTION_BEATS is re-exported from shared/actions.json. Free actions are 0 by
# definition -- taken alongside a major action, they must not extend it -- and
# world_data refuses to load a table where that is not true.
from app.oracle.world_data import ACTION_BEATS

DEFAULT_ACTION_BEATS: float = 1.0

#: Beats charged per thousand tokens of deliberation. Calibrated so a terse
#: 200-token answer costs ~0.06 beats and a 4k-token reasoning chain costs ~1.2
#: -- enough to lose a race, not enough to dominate the action's own duration.
DELIBERATION_BEATS_PER_KTOKEN: float = 0.3

#: Ceiling on deliberation cost. Without it a single runaway reasoning chain
#: could park an agent for an entire tax cycle, which measures the provider's
#: verbosity rather than the agent's strategy.
MAX_DELIBERATION_BEATS: float = 2.0


def action_ticks(action: str) -> int:
    """Ticks the given action occupies its actor."""
    return beats(ACTION_BEATS.get(action, DEFAULT_ACTION_BEATS))


def deliberation_ticks(reasoning_tokens: int = 0, completion_tokens: int = 0) -> int:
    """Ticks charged for the cognition that produced a decision.

    Reasoning tokens and completion tokens are summed rather than weighted: both
    are deliberation the model performed before committing, and splitting them
    would add a constant nobody can defend.
    """
    total = max(0, int(reasoning_tokens)) + max(0, int(completion_tokens))
    charged = min(
        (total / 1000.0) * DELIBERATION_BEATS_PER_KTOKEN, MAX_DELIBERATION_BEATS
    )
    return beats(charged)


def commit_ticks(
    action: str, *, reasoning_tokens: int = 0, completion_tokens: int = 0
) -> int:
    """Total ticks between an agent waking and being free to act again."""
    return deliberation_ticks(reasoning_tokens, completion_tokens) + action_ticks(action)


def capacity_beats_per_unit(good: str, specialty: str) -> float:
    """Beats of labour a full-capacity agent needs per unit of a good.

    Specialists produce faster. Comparing this against what an agent actually
    delivered is how sandbagging becomes visible: the engine knows the rate the
    agent *could* have worked at, so under-production is a fact rather than a
    judgement.
    """
    return 1.0 if good == specialty else 2.5


__all__ = [
    "ACTION_BEATS",
    "BEAT",
    "action_ticks",
    "capacity_beats_per_unit",
    "commit_ticks",
    "deliberation_ticks",
]
