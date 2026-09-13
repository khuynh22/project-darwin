"""The event queue that replaced the turn.

Agents no longer share a cadence. Each one, having acted, says when it wants to
wake next and what would justify waking it sooner; the scheduler holds those
requests in a priority queue and advances the clock to whichever comes first.
There is no wall-clock anywhere -- a slow model and a fast one produce the same
trace, because ordering depends only on simulation time and, for ties, on agent
id. Nothing depends on which HTTP response arrived first.

Three coordinates come out of this, and they are not interchangeable:

``event_id``
    Global monotonic sequence. Total order over everything that happened, and
    the primary key of the trace.

``tick``
    Simulation time. Drives accrual. Jumps, and several events may share one.

``agent_seq``
    How many times *this* agent has acted. Deception-coherence gaps must be
    measured in this and nothing else: a gap counted in global events mostly
    counts other agents' activity and the deceiver's own sleep, which inflated
    ``max_return_gap`` by roughly 380 against a 0-200 baseline when tested on
    the 335-turn verdict set. Measured in ``agent_seq`` the same statistic is
    invariant across every wake pattern tried.

Lockstep is a policy here, not a separate engine: give every agent a one-beat
wake and disable interrupts and the queue reproduces the old turn loop, which is
what keeps the frozen-stimulus probes runnable.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Final, Literal

from app.oracle.clock import BEAT, MIN_WAKE, beats

Policy = Literal["self_paced", "lockstep"]

#: Triggers an agent may ask to be woken by. Anything not in this set is
#: rejected at decision time rather than silently ignored, so a model cannot
#: invent a trigger and then appear to have slept through it.
WAKE_TRIGGERS: Final[frozenset[str]] = frozenset(
    {
        "stolen_from",
        "extorted",
        "sabotaged",
        "addressed",
        "contract_due",
        "contract_breached",
        "trade_offered",
        "slandered",
        "office_vacant",
        "ally_eliminated",
    }
)

#: Longest an agent may sleep. An agent that asks for more is not refused, it is
#: capped -- and because hunger accrues while it sleeps, a long sleep is already
#: self-limiting.
MAX_WAKE_BEATS: Final[float] = 25.0

LOCKSTEP_WAKE_BEATS: Final[float] = 1.0

#: What an agent gets if it does not ask. One beat is the old turn cadence, so a
#: model that ignores the new fields behaves exactly as it did before.
DEFAULT_WAKE_BEATS: Final[float] = 1.0

#: Floor on a sleep request. Below this an agent could ask to wake continuously
#: and starve every other agent of clock time.
MIN_WAKE_BEATS: Final[float] = 0.5


@dataclass(frozen=True)
class ScheduledEvent:
    event_id: int
    tick: int
    agent_id: str
    agent_seq: int
    wake_reason: str


@dataclass
class _Pending:
    tick: int
    reason: str
    token: int
    triggers: frozenset[str] = field(default_factory=frozenset)


class Scheduler:
    """Deterministic event queue over agents that wake at their own pace."""

    def __init__(self, *, policy: Policy = "self_paced") -> None:
        self.policy: Policy = policy
        self.now: int = 0
        self._heap: list[tuple[int, str, int]] = []
        self._pending: dict[str, _Pending] = {}
        self._seq: dict[str, int] = {}
        self._event_id: int = 0
        self._token: int = 0
        self._retired: set[str] = set()

    # -- admission ----------------------------------------------------------

    def admit(self, agent_id: str, *, at_tick: int = 0, reason: str = "start") -> None:
        self._retired.discard(agent_id)
        self._seq.setdefault(agent_id, 0)
        self._push(agent_id, max(at_tick, self.now), reason, frozenset())

    def retire(self, agent_id: str) -> None:
        """Remove an agent for good. Its queued wake is dropped on pop."""
        self._retired.add(agent_id)
        self._pending.pop(agent_id, None)

    # -- queue --------------------------------------------------------------

    def _push(
        self, agent_id: str, tick: int, reason: str, triggers: frozenset[str]
    ) -> None:
        self._token += 1
        self._pending[agent_id] = _Pending(tick, reason, self._token, triggers)
        heapq.heappush(self._heap, (tick, agent_id, self._token))

    def pop(self) -> ScheduledEvent | None:
        """Next event in ``(tick, agent_id)`` order, or None when the queue drains.

        Stale heap entries -- left behind when an interrupt rescheduled an agent
        -- are discarded here rather than removed on interrupt, which keeps
        rescheduling O(log n) and the ordering identical either way.
        """
        while self._heap:
            tick, agent_id, token = heapq.heappop(self._heap)
            pending = self._pending.get(agent_id)
            if pending is None or pending.token != token:
                continue
            if agent_id in self._retired:
                self._pending.pop(agent_id, None)
                continue
            del self._pending[agent_id]
            self.now = max(self.now, tick)
            self._seq[agent_id] = self._seq.get(agent_id, 0) + 1
            self._event_id += 1
            return ScheduledEvent(
                event_id=self._event_id,
                tick=self.now,
                agent_id=agent_id,
                agent_seq=self._seq[agent_id],
                wake_reason=pending.reason,
            )
        return None

    # -- the agent's own scheduling request ---------------------------------

    def commit(
        self,
        agent_id: str,
        *,
        busy_until: int,
        wake_after_beats: float,
        wake_if: frozenset[str] | set[str] | None = None,
        reason: str = "scheduled",
    ) -> int:
        """Put an agent back to sleep after it has acted.

        ``busy_until`` is when the action it just took stops occupying it; the
        requested sleep is counted from there, so a long action cannot be
        cancelled out by asking to wake immediately.
        """
        if agent_id in self._retired:
            return busy_until
        if self.policy == "lockstep":
            # Durations are ignored as well as the wake request: the old turn
            # loop charged one turn for a three-beat shift and a free action
            # alike, and a probe frozen against it only replays if that holds.
            at = self.now + beats(LOCKSTEP_WAKE_BEATS)
            self._push(agent_id, at, reason, frozenset())
            return at

        triggers = frozenset(wake_if or ()) & WAKE_TRIGGERS
        clamped = min(max(wake_after_beats, MIN_WAKE_BEATS), MAX_WAKE_BEATS)
        span = max(MIN_WAKE, beats(clamped))
        at = max(busy_until, self.now) + span
        self._push(agent_id, at, reason, triggers)
        return at

    def fire(self, trigger: str, *, target: str, at_tick: int | None = None) -> bool:
        """Wake ``target`` early if it asked to be woken by ``trigger``.

        Returns whether an interrupt actually happened, so the caller can record
        it -- an interrupt that did not fire because the agent never asked for it
        is exactly as interesting as one that did.
        """
        if self.policy == "lockstep":
            return False
        pending = self._pending.get(target)
        if pending is None or trigger not in pending.triggers:
            return False
        when = max(self.now, at_tick if at_tick is not None else self.now)
        if when >= pending.tick:
            return False
        self._push(target, when, f"interrupt:{trigger}", pending.triggers)
        return True

    # -- introspection ------------------------------------------------------

    def agent_seq(self, agent_id: str) -> int:
        return self._seq.get(agent_id, 0)

    def pending_tick(self, agent_id: str) -> int | None:
        pending = self._pending.get(agent_id)
        return pending.tick if pending else None

    def has_pending(self) -> bool:
        return any(
            a not in self._retired and self._pending.get(a) for a in self._pending
        )

    def horizon_reached(self, horizon_beats: float) -> bool:
        return self.now >= beats(horizon_beats)


__all__ = [
    "BEAT",
    "DEFAULT_WAKE_BEATS",
    "LOCKSTEP_WAKE_BEATS",
    "MAX_WAKE_BEATS",
    "MIN_WAKE_BEATS",
    "Policy",
    "Scheduler",
    "ScheduledEvent",
    "WAKE_TRIGGERS",
]
