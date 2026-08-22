"""Export a Darwin session from the database as a schema-v4 trace.

This is the full-fidelity path: ``turn_snapshots`` supplies per-turn state, so
probes mined from these traces can restore the world exactly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.ledger import ThoughtLog, TurnSnapshot
from app.trace.adapters.legacy_jsonl import is_fallback
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    Instrument,
    RunManifest,
    TurnRecord,
    TurnState,
)


async def export_session(
    session: AsyncSession,
    session_id: str,
    *,
    run_id: str | None = None,
    condition: str = "neutral",
    seed: int = 0,
) -> tuple[RunManifest, list[TurnRecord]]:
    agents = (
        await session.execute(select(Agent).where(Agent.session_id == session_id))
    ).scalars().all()
    thoughts = (
        await session.execute(
            select(ThoughtLog)
            .where(ThoughtLog.session_id == session_id)
            .order_by(ThoughtLog.turn, ThoughtLog.id)
        )
    ).scalars().all()
    snapshots = (
        await session.execute(
            select(TurnSnapshot).where(TurnSnapshot.session_id == session_id)
        )
    ).scalars().all()

    by_key = {(s.turn, s.agent_id): s for s in snapshots}
    alive_at: dict[int, list[str]] = {}
    for snap in snapshots:
        if snap.alive:
            alive_at.setdefault(snap.turn, []).append(snap.agent_id)

    horizon = max((t.turn for t in thoughts), default=0)
    last_turn: dict[str, int] = {}
    for t in thoughts:
        last_turn[t.agent_id] = max(last_turn.get(t.agent_id, 0), t.turn)

    records = [
        TurnRecord(
            kind="turn",
            turn=t.turn,
            agent_id=t.agent_id,
            monologue=t.monologue or "",
            public_message=t.public_message or "",
            action=t.action or "",
            arguments=t.arguments or {},
            outcome=t.outcome or "",
            state=_state(by_key.get((t.turn, t.agent_id)), alive_at.get(t.turn)),
            instrument=Instrument(tool_call_ok=not is_fallback(t.monologue)),
        )
        for t in thoughts
    ]

    manifest = RunManifest(
        kind="run",
        schema_version=4,
        run_id=run_id or session_id,
        env=EnvManifest(name="darwin", seed=seed, actions=20),
        condition=condition,
        horizon=horizon,
        state_fidelity="full",
        agents=[
            AgentManifest(
                agent_id=a.agent_id,
                model=a.model,
                provider=a.provider,
                specialty=a.specialty,
                persona=a.personality or None,
                turns_alive=a.eliminated_at_turn or last_turn.get(a.agent_id, 0),
                eliminated_at_turn=a.eliminated_at_turn,
                outcome="survived" if a.alive else "eliminated",
            )
            for a in sorted(agents, key=lambda x: x.agent_id)
        ],
    )
    return manifest, records


def _state(snap: TurnSnapshot | None, alive: list[str] | None) -> TurnState:
    if snap is None:
        return TurnState(alive=sorted(alive) if alive else None)
    return TurnState(
        balance=snap.balance,
        trust_score=snap.trust_score,
        inventory=dict(snap.inventory or {}),
        alive=sorted(alive) if alive else None,
        spouse_id=snap.spouse_id,
    )
