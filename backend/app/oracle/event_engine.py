"""The event loop that replaced ``run_turn``.

``run_events`` advances one session by popping the next scheduled agent, letting
the world accrue for however long has passed, applying that agent's decision,
and putting it back to sleep for as long as it asked. There is no round and no
barrier: agents act at whatever cadence they choose, and a slow deliberator
genuinely acts later than a quick one because the tokens it spent are charged as
simulation time.

Determinism comes from three places and nothing else. Ordering is
``(tick, agent_id)``, never arrival order. The per-event RNG is seeded from
``(seed, event_id)``, so a draw depends on position rather than on how many
draws came before it. Wall-clock latency is never read. A run therefore replays
identically whether its models answered in 0.8 seconds or twelve.

``policy="lockstep"`` gives every agent a one-beat wake and disables interrupts,
which reproduces the old turn loop -- that is how the frozen-stimulus probes
stay runnable against an engine that no longer has turns.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentDecision, BaseAgent
from app.config import CLI_SESSION_ID, get_settings
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.accrual import Wallet, accrue
from app.oracle.clock import BEAT, to_beats
from app.oracle.durations import commit_ticks, deliberation_ticks
from app.oracle.engine import (
    _agent_history,
    _apply_decision,
    _decide_one,
    _world_state,
)
from app.oracle.scheduler import Policy, ScheduledEvent, Scheduler
from app.oracle.space import (
    DEFAULT_VENUE,
    Placement,
    observable_by,
    travel_ticks,
    venue_for,
)
from app.oracle.world_data import BUILT_VENUES, actions_at
from app.trace.recorder import record_event
from app.trace.schema import EventRecord, TurnState

log = logging.getLogger(__name__)

#: Which action inflicted on whom raises which interrupt. An agent that asked to
#: be woken when robbed is woken the instant it is robbed, rather than finding
#: out on its own schedule -- which is the whole reason reaction time exists.
INTERRUPT_FOR: dict[str, str] = {
    "steal": "stolen_from",
    "extort": "extorted",
    "sabotage": "sabotaged",
    "slander": "slandered",
    "trade": "trade_offered",
    "propose_deal": "addressed",
    "bribe": "addressed",
    "gaslight": "addressed",
    "sign_contract": "contract_due",
}


@dataclass
class EventOutcome:
    event: ScheduledEvent
    action: str
    outcome: str
    venue: str
    busy_ticks: int
    deliberation_ticks: int
    travel_ticks: int
    from_venue: str
    wake_after: float
    wake_if: list[str]
    interrupted: list[str] = field(default_factory=list)


@dataclass
class EventRunResult:
    events: list[EventOutcome] = field(default_factory=list)
    eliminated: list[str] = field(default_factory=list)
    final_tick: int = 0

    @property
    def beats(self) -> float:
        return to_beats(self.final_tick)

    def moves_by(self, agent_id: str) -> int:
        return sum(1 for e in self.events if e.event.agent_id == agent_id)


def _target_of(decision: AgentDecision) -> str | None:
    args = decision.arguments or {}
    for key in ("target", "target_id", "counterparty"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return None


async def _settle(
    session: AsyncSession,
    session_id: str,
    settled_at: dict[str, int],
    to_tick: int,
) -> list[str]:
    """Advance every living agent's wallet to ``to_tick``.

    Everyone accrues, including agents that are asleep -- that is what makes
    sleeping a decision with a price rather than a way to sit out the economy.
    Returns agents whose balance reached zero and who are therefore eliminated.
    """
    rows = (
        (
            await session.execute(
                select(Agent)
                .where(Agent.session_id == session_id, Agent.alive.is_(True))
                .order_by(Agent.agent_id)
            )
        )
        .scalars()
        .all()
    )
    died: list[str] = []
    for db_agent in rows:
        from_tick = settled_at.get(db_agent.agent_id, 0)
        if to_tick <= from_tick:
            continue
        wallet = Wallet(
            balance=db_agent.balance,
            food=int((db_agent.inventory or {}).get("food", 0)),
            food_buffer=float(db_agent.food_buffer or 0.0),
        )
        accrue(wallet, from_tick=from_tick, to_tick=to_tick)
        inventory = dict(db_agent.inventory or {})
        inventory["food"] = wallet.food
        db_agent.inventory = inventory
        db_agent.balance = round(wallet.balance, 2)
        db_agent.food_buffer = wallet.food_buffer
        settled_at[db_agent.agent_id] = to_tick
        if db_agent.balance <= 0:
            db_agent.alive = False
            died.append(db_agent.agent_id)
    await session.flush()
    return died


def _placements(at_venue: dict[str, str], tick: int) -> list[Placement]:
    """Everyone's last known venue, as of now.

    Approximate on purpose: an agent in transit is recorded at the venue it is
    heading to rather than nowhere, so a witness list is never empty merely
    because someone was mid-walk. Tightening this needs per-agent arrival ticks
    on the scheduler, not here.
    """
    return [Placement(agent_id, venue, arrives_at=0) for agent_id, venue in at_venue.items()]


async def run_events(
    session: AsyncSession,
    *,
    session_id: str = CLI_SESSION_ID,
    agents: dict[str, BaseAgent],
    horizon_beats: float,
    policy: Policy = "self_paced",
    balance_visibility: str = "fuzzy",
    seed: int = 0,
    condition: str = "neutral",
    venue_gating: bool = False,
    max_events: int | None = None,
) -> EventRunResult:
    """Run one session forward until ``horizon_beats`` of simulation time pass."""
    settings = get_settings()
    scheduler = Scheduler(policy=policy)
    result = EventRunResult()
    settled_at: dict[str, int] = {}
    at_venue: dict[str, str] = {}

    alive = (
        (
            await session.execute(
                select(Agent)
                .where(Agent.session_id == session_id, Agent.alive.is_(True))
                .order_by(Agent.agent_id)
            )
        )
        .scalars()
        .all()
    )
    for db_agent in alive:
        scheduler.admit(db_agent.agent_id)
        at_venue[db_agent.agent_id] = (
            db_agent.venue if db_agent.venue in BUILT_VENUES else DEFAULT_VENUE
        )

    while not scheduler.horizon_reached(horizon_beats):
        if max_events is not None and len(result.events) >= max_events:
            break
        event = scheduler.pop()
        if event is None:
            break

        for dead in await _settle(session, session_id, settled_at, event.tick):
            scheduler.retire(dead)
            if dead not in result.eliminated:
                result.eliminated.append(dead)

        db_agent = (
            await session.execute(
                select(Agent).where(
                    Agent.session_id == session_id,
                    Agent.agent_id == event.agent_id,
                )
            )
        ).scalar_one_or_none()
        if db_agent is None or not db_agent.alive:
            scheduler.retire(event.agent_id)
            continue

        state = await _world_state(session, session_id, event.agent_seq)
        state["_balance_visibility"] = balance_visibility
        state["_seed"] = seed
        state["_condition"] = condition
        state["_tick"] = event.tick
        state["_wake_reason"] = event.wake_reason
        state["_venue"] = at_venue.get(event.agent_id, DEFAULT_VENUE)
        state["_venue_gating"] = venue_gating
        history = await _agent_history(session, session_id, event.agent_id)

        try:
            decision = await _decide_one(
                agents[event.agent_id], state, db_agent, history, []
            )
        except Exception as exc:  # noqa: BLE001
            log.error("agent %s decide() failed: %r", event.agent_id, exc)
            db_agent.consecutive_errors += 1
            db_agent.last_error = str(exc)[:512]
            if db_agent.consecutive_errors >= settings.error_threshold:
                db_agent.alive = False
                scheduler.retire(event.agent_id)
                result.eliminated.append(event.agent_id)
            continue
        db_agent.consecutive_errors = 0

        rng = random.Random(f"{seed}:{event.event_id}")
        here = at_venue.get(event.agent_id, DEFAULT_VENUE)
        gate_rejected = venue_gating and decision.action not in actions_at(
            here, gated=True
        )
        if gate_rejected:
            outcome = f"{decision.action} not available here [rejected]"
        else:
            outcome = await _apply_decision(
                session,
                session_id=session_id,
                turn=event.agent_seq,
                agent=db_agent,
                decision=decision,
                rng=rng,
            )

        if decision.free_action:
            free_ok = not venue_gating or decision.free_action in actions_at(
                here, gated=True
            )
            if free_ok:
                free = AgentDecision(
                    action=decision.free_action, arguments=decision.free_arguments
                )
                await _apply_decision(
                    session,
                    session_id=session_id,
                    turn=event.agent_seq,
                    agent=db_agent,
                    decision=free,
                    rng=rng,
                )

        if venue_gating:
            from_venue = here
            moved = decision.action == "travel" and outcome.endswith(" [ok]")
            venue = decision.arguments.get("venue", here) if moved else here
            travel = travel_ticks(from_venue, venue)
        else:
            venue = venue_for(decision.action)
            from_venue = at_venue.get(event.agent_id, venue)
            travel = travel_ticks(from_venue, venue)
        at_venue[event.agent_id] = venue
        db_agent.venue = venue
        think = deliberation_ticks(decision.reasoning_tokens, decision.completion_tokens)
        busy = travel + commit_ticks(
            decision.action,
            reasoning_tokens=decision.reasoning_tokens,
            completion_tokens=decision.completion_tokens,
        )

        interrupted: list[str] = []
        # A handler that refuses still wakes the target on purpose: a caught
        # thief is news to its victim. A gate refusal is different -- no handler
        # ran, so waking the target would buy it an unscheduled LLM call and a
        # wake_reason asserting a theft the engine never attempted.
        trigger = None if gate_rejected else INTERRUPT_FOR.get(decision.action)
        target = _target_of(decision)
        if trigger and target and scheduler.fire(trigger, target=target, at_tick=event.tick):
            interrupted.append(target)

        session.add(
            ThoughtLog(
                session_id=session_id,
                turn=event.agent_seq,
                agent_id=event.agent_id,
                monologue=decision.monologue,
                public_message=(decision.arguments or {}).get("public_message", ""),
                action=decision.action,
                arguments=decision.arguments or {},
                outcome=outcome,
            )
        )
        await session.flush()

        await record_event(
            session,
            session_id,
            EventRecord(
                kind="event",
                event_id=event.event_id,
                tick=event.tick,
                agent_seq=event.agent_seq,
                agent_id=event.agent_id,
                wake_reason=event.wake_reason,
                monologue=decision.monologue,
                public_message=(decision.arguments or {}).get("public_message", ""),
                action=decision.action,
                arguments=decision.arguments or {},
                outcome=outcome,
                venue=venue,
                witnesses=observable_by(
                    _placements(at_venue, event.tick), venue=venue, tick=event.tick,
                    actor=event.agent_id,
                ),
                busy_ticks=busy,
                deliberation_ticks=think,
                travel_ticks=travel,
                wake_after=decision.wake_after,
                wake_if=list(decision.wake_if),
                state=TurnState(
                    balance=db_agent.balance,
                    trust_score=db_agent.trust_score,
                    inventory=dict(db_agent.inventory or {}),
                    spouse_id=db_agent.spouse_id,
                    steal_count=db_agent.steal_count,
                    food_buffer=db_agent.food_buffer,
                    venue=venue,
                    allies=list(db_agent.allies or []),
                    enemies=list(db_agent.enemies or []),
                ),
            ),
            seed=seed,
            condition=condition,
            venue_gating=venue_gating,
        )

        result.events.append(
            EventOutcome(
                event=event,
                action=decision.action,
                outcome=outcome,
                venue=venue,
                busy_ticks=busy,
                deliberation_ticks=think,
                travel_ticks=travel,
                from_venue=from_venue,
                wake_after=decision.wake_after,
                wake_if=list(decision.wake_if),
                interrupted=interrupted,
            )
        )

        scheduler.commit(
            event.agent_id,
            busy_until=event.tick + busy,
            wake_after_beats=decision.wake_after,
            wake_if=set(decision.wake_if),
        )

    result.final_tick = scheduler.now
    for dead in await _settle(session, session_id, settled_at, scheduler.now):
        if dead not in result.eliminated:
            result.eliminated.append(dead)
    await session.commit()
    return result


__all__ = ["BEAT", "EventOutcome", "EventRunResult", "INTERRUPT_FOR", "run_events"]
