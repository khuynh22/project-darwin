"""Export a Darwin session from the database as a schema-v4 trace.

This is the full-fidelity path: ``turn_snapshots`` supplies per-turn state, so
probes mined from these traces can restore the world exactly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ENV_VERSION
from app.models.agent import Agent
from app.models.deferred import DeferredAction
from app.models.ledger import ThoughtLog, TurnSnapshot
from app.models.registry import Contract, Office
from app.trace.adapters.legacy_jsonl import is_fallback
from app.trace.schema import (
    TRACE_SCHEMA_VERSION,
    AgentManifest,
    DeferredEntry,
    EnvManifest,
    Instrument,
    RunManifest,
    TurnRecord,
    TurnState,
    WorldRecord,
)


async def export_session(
    session: AsyncSession,
    session_id: str,
    *,
    run_id: str | None = None,
    condition: str = "neutral",
    seed: int = 0,
) -> tuple[RunManifest, list[TurnRecord], list[WorldRecord]]:
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
    deferred_rows = (
        await session.execute(
            select(DeferredAction).where(DeferredAction.session_id == session_id)
        )
    ).scalars().all()

    by_key = {(s.turn, s.agent_id): s for s in snapshots}

    # An unresolved deferred row is live for every turn between creation and
    # maturity, so it must be reconstructed per turn rather than read once.
    def _deferred_at(turn: int, agent_id: str) -> list[DeferredEntry]:
        return [
            DeferredEntry(kind=d.kind, amount=d.amount,
                          maturity_turn=d.maturity_turn, target_id=d.target_id)
            for d in deferred_rows
            if d.actor_id == agent_id
            and d.created_turn <= turn < d.maturity_turn
            and not d.resolved
        ]
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
            state=_state(by_key.get((t.turn, t.agent_id)), alive_at.get(t.turn),
                         _deferred_at(t.turn, t.agent_id)),
            instrument=Instrument(tool_call_ok=not is_fallback(t.monologue)),
        )
        for t in thoughts
    ]

    manifest = RunManifest(
        kind="run",
        schema_version=TRACE_SCHEMA_VERSION,
        run_id=run_id or session_id,
        env=EnvManifest(name="darwin", version=ENV_VERSION, seed=seed, actions=20),
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
    contracts = (
        await session.execute(
            select(Contract).where(Contract.session_id == session_id)
        )
    ).scalars().all()
    offices = (
        await session.execute(select(Office).where(Office.session_id == session_id))
    ).scalars().all()

    def _open_at(turn: int) -> list[dict]:
        """Contracts that were open *at that turn*, not merely open now.

        A contract resolved later was still in force earlier, so replaying a
        turn must see it. Reading current status would show a world the agents
        never faced.
        """
        return [
            {
                "contract_id": c.contract_id,
                "proposer": c.proposer_id,
                "counterparty": c.counterparty_id,
                "terms": c.terms,
                "good": (c.terms or {}).get("deliver", {}).get("good"),
                "qty": (c.terms or {}).get("deliver", {}).get("qty"),
                "pay": (c.terms or {}).get("pay"),
                "created_turn": c.created_turn,
                "deadline_turn": c.deadline_turn,
                "status": "open",
            }
            for c in contracts
            if c.created_turn <= turn
            and (c.resolved_turn is None or turn < c.resolved_turn)
        ]

    world = [
        WorldRecord(
            kind="world",
            turn=turn,
            contracts=_open_at(turn),
            offices={o.office: o.holder_id for o in offices},
        )
        for turn in sorted({t.turn for t in thoughts})
    ]
    return manifest, records, world


def _state(
    snap: TurnSnapshot | None,
    alive: list[str] | None,
    deferred: list[DeferredEntry] | None = None,
) -> TurnState:
    if snap is None:
        return TurnState(alive=sorted(alive) if alive else None)
    return TurnState(
        balance=snap.balance,
        trust_score=snap.trust_score,
        inventory=dict(snap.inventory or {}),
        alive=sorted(alive) if alive else None,
        spouse_id=snap.spouse_id,
        steal_count=snap.steal_count,
        allies=list(snap.allies or []),
        enemies=list(snap.enemies or []),
        skip_next_turn=snap.skip_next_turn,
        rest_bonus=snap.rest_bonus,
        share_balance=snap.share_balance,
        will_target=snap.will_target,
        marriage_pending=snap.marriage_pending,
        extortion_pending=snap.extortion_pending,
        bribe_pending=snap.bribe_pending,
        deferred=deferred or [],
    )
