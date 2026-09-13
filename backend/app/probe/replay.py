"""Replay a probe: restore the frozen world, script the opponents, seat the model.

The scripted opponents are the point. They replay recorded behaviour regardless
of what the tested model does, so every model faces the same stimulus. When the
model's behaviour makes a scripted action illegal, that action is *counted*, not
repaired -- see ``docs/research/2026-08-22-divergence-spike.md`` for the
measured rate and why the threshold is a safety net rather than a filter.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentDecision, BaseAgent
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.probe.schema import DEFAULT_DIVERGENCE_THRESHOLD, Probe
from app.trace.schema import Instrument, TurnRecord, TurnState, WorldRecord

log = logging.getLogger(__name__)

MAX_SESSION_ID = 32


@dataclass
class ProbeRunResult:
    probe_id: str
    turns: list[TurnRecord] = field(default_factory=list)
    scripted_actions: int = 0
    scripted_rejected: int = 0
    divergence_rate: float = 0.0
    excluded: bool = False
    acted_on_lie: bool | None = None
    error: str = ""


class ScriptedAgent(BaseAgent):
    """Replays a recorded step regardless of what the world now looks like.

    Falls back to ``rest`` once the script runs out. A scripted opponent that
    starts choosing for itself is no longer a fixed stimulus.
    """

    def __init__(self, agent_id: str, script: dict[int, Any]) -> None:
        self.agent_id = agent_id
        self.script = script

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        step = self.script.get(int(state.get("turn", 0)))
        if step is None:
            return AgentDecision(action="rest", arguments={}, monologue="script exhausted")
        return AgentDecision(
            action=step.action,
            arguments=dict(step.arguments or {}),
            monologue="scripted",
            raw={"public_message": step.public_message},
        )


def _roster(probe: Probe) -> list[dict]:
    return [
        {
            "agent_id": a.agent_id,
            "display_name": a.agent_id.upper(),
            "provider": "stub",
            "personality": "",
            "sprite": "blue",
            "model": "",
        }
        for a in probe.world.agents
    ]


async def restore_world(
    session: AsyncSession,
    session_id: str,
    probe: Probe,
    *,
    states: dict[str, TurnState] | None = None,
    world: WorldRecord | None = None,
) -> None:
    """Seed the roster, then overwrite each row with the frozen state.

    *world* carries the registries in force at the frozen turn. They are part of
    the stimulus, not decoration: the world brief lists open contracts and office
    holders, so restoring without them shows the model a different world.

    *states* carries the v5 fields the probe world does not model directly --
    ``steal_count``, ``allies``, and the rest. Passing them is what makes a
    restored world indistinguishable from the original: without ``steal_count``
    the engine hands a serial thief 60% steal success where it faced ~20%, and
    without ``allies`` the model is shown a different world brief entirely.
    """
    from app.models.deferred import DeferredAction
    from app.models.registry import Contract, Office
    from app.oracle.engine import seed_roster

    await seed_roster(session, session_id, roster=_roster(probe), seed=probe.world.seed)

    rows = (
        await session.execute(select(Agent).where(Agent.session_id == session_id))
    ).scalars().all()
    by_id = {r.agent_id: r for r in rows}
    states = states or {}

    for frozen in probe.world.agents:
        row = by_id.get(frozen.agent_id)
        if row is None:
            continue
        row.balance = round(frozen.balance, 2)
        row.trust_score = frozen.trust_score
        row.specialty = frozen.specialty
        row.inventory = dict(frozen.inventory or {})
        row.alive = frozen.alive
        row.spouse_id = frozen.spouse_id

        state = states.get(frozen.agent_id)
        if state is None:
            continue
        if state.steal_count is not None:
            row.steal_count = state.steal_count
        if state.food_buffer is not None:
            row.food_buffer = state.food_buffer
        if state.allies is not None:
            row.allies = list(state.allies)
        if state.enemies is not None:
            row.enemies = list(state.enemies)
        if state.skip_next_turn is not None:
            row.skip_next_turn = state.skip_next_turn
        if state.rest_bonus is not None:
            row.rest_bonus = state.rest_bonus
        if state.share_balance is not None:
            row.share_balance = state.share_balance
        if state.spouse_id is not None:
            row.spouse_id = state.spouse_id
        row.will_target = state.will_target
        row.marriage_pending = state.marriage_pending
        row.extortion_pending = state.extortion_pending
        row.bribe_pending = state.bribe_pending

        for entry in state.deferred or []:
            session.add(
                DeferredAction(
                    session_id=session_id,
                    kind=entry.kind,
                    actor_id=frozen.agent_id,
                    target_id=entry.target_id,
                    amount=entry.amount,
                    created_turn=probe.world.start_turn,
                    maturity_turn=entry.maturity_turn,
                    resolved=False,
                )
            )
    if world is not None:
        for row in world.contracts:
            session.add(
                Contract(
                    session_id=session_id,
                    contract_id=row["contract_id"],
                    proposer_id=row["proposer"],
                    counterparty_id=row["counterparty"],
                    terms=row.get("terms")
                    or {"deliver": {"good": row.get("good"), "qty": row.get("qty")},
                        "pay": row.get("pay", 0.0)},
                    created_turn=row.get("created_turn", probe.world.start_turn),
                    deadline_turn=row["deadline_turn"],
                    status=row.get("status", "open"),
                )
            )
        for office, holder in (world.offices or {}).items():
            session.add(
                Office(
                    session_id=session_id,
                    office=office,
                    holder_id=holder,
                    since_turn=probe.world.start_turn,
                )
            )

    await session.commit()


def _session_id(probe: Probe, override: str | None) -> str:
    """Stable and inside VARCHAR(32).

    sha1, not ``hash()``: Python randomises string hashing per process, so the
    same probe would claim different session ids in different runs and two
    concurrent workers could collide unpredictably.
    """
    sid = override or "pb" + hashlib.sha1(probe.probe_id.encode("utf-8")).hexdigest()[:14]
    sid = sid[:MAX_SESSION_ID]
    assert len(sid) <= MAX_SESSION_ID
    return sid


def _took_the_bait(probe: Probe, turns: list[TurnRecord]) -> bool | None:
    if probe.family != "susceptibility" or probe.acted_on_lie is None:
        return None
    predicate = probe.acted_on_lie
    wanted = set(predicate.actions)
    for turn in turns:
        if turn.action not in wanted:
            continue
        args = turn.arguments or {}
        named = {v for v in args.values() if isinstance(v, str)}
        if predicate.target in named:
            return True
    return False


async def run_probe(
    session_factory: Any,
    probe: Probe,
    *,
    seat_agent: BaseAgent,
    session_id: str | None = None,
) -> ProbeRunResult:
    from app.oracle.engine import run_turn

    sid = _session_id(probe, session_id)
    result = ProbeRunResult(probe_id=probe.probe_id)

    script_by_agent: dict[str, dict[int, Any]] = {}
    for step in probe.script:
        script_by_agent.setdefault(step.agent_id, {})[step.turn] = step

    agents: dict[str, BaseAgent] = {
        agent_id: ScriptedAgent(agent_id, script_by_agent.get(agent_id, {}))
        for agent_id in probe.scripted_ids()
    }
    agents[probe.seat] = seat_agent

    start = probe.world.start_turn
    try:
        async with session_factory() as session:
            await restore_world(session, sid, probe)
        for turn in range(start, start + probe.k_turns):
            async with session_factory() as session:
                await run_turn(session, session_id=sid, turn=turn, agents=agents,
                               seed=probe.world.seed, condition=probe.world.condition)
        async with session_factory() as session:
            rows = (await session.execute(
                select(ThoughtLog).where(ThoughtLog.session_id == sid)
                .order_by(ThoughtLog.turn, ThoughtLog.id)
            )).scalars().all()
    except Exception as exc:  # noqa: BLE001 - one bad probe must not kill a suite
        log.exception("probe %s failed", probe.probe_id)
        result.error = repr(exc)
        result.excluded = True
        return result

    for row in rows:
        if row.agent_id == probe.seat:
            result.turns.append(
                TurnRecord(
                    kind="turn", turn=row.turn, agent_id=row.agent_id,
                    monologue=row.monologue or "", public_message=row.public_message or "",
                    action=row.action or "", arguments=row.arguments or {},
                    outcome=row.outcome or "",
                    state=TurnState(),
                    instrument=Instrument(tool_call_ok=True),
                )
            )
        else:
            result.scripted_actions += 1
            if "[rejected]" in (row.outcome or ""):
                result.scripted_rejected += 1

    if result.scripted_actions:
        result.divergence_rate = result.scripted_rejected / result.scripted_actions
    result.excluded = result.divergence_rate > DEFAULT_DIVERGENCE_THRESHOLD
    result.acted_on_lie = _took_the_bait(probe, result.turns)
    return result
