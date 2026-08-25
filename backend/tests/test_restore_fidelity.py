"""Restoring a frozen turn must be indistinguishable from having lived it.

Matching database columns proves the *engine* agrees. Matching the rendered
world brief proves **the model sees the same world**, which is what a probe
actually depends on -- and only the second one catches an ``allies`` omission.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import render_world_brief
from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.agent import Agent
from app.oracle.engine import _world_state, run_turn, seed_roster
from app.probe.replay import restore_world
from app.probe.schema import AgentState, Probe, ProbeWorld
from app.trace.adapters.darwin_db import export_session
from app.trace.schema import TurnState

# Identity and bookkeeping, not world state: these describe *which* agent this
# is or how the run went, and restoring them would be meaningless or wrong.
RESTORE_EXEMPT = {
    "session_id", "agent_id", "display_name", "provider", "model", "personality",
    "sprite", "created_at", "consecutive_errors", "last_error", "eliminated_at_turn",
    # Carried on ProbeWorld/AgentState rather than TurnState.
    "specialty", "balance", "trust_score", "alive",
}

TURNS = 8
SID = "fidelity"


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(4)
    ]


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


async def _live_run(factory, session_id=SID, turns=TURNS, seed=21):
    async with factory() as session:
        await seed_roster(session, session_id, _roster(), seed=seed)
        agents = build_agents(roster=_roster())
        for turn in range(1, turns + 1):
            await run_turn(session, session_id=session_id, turn=turn,
                           agents=agents, seed=seed)


def _probe_from_state(turn: int, records, manifest) -> Probe:
    """Build a probe that freezes the world exactly as the trace recorded it."""
    at_turn = {r.agent_id: r for r in records if r.turn == turn}
    specialties = {a.agent_id: a.specialty for a in manifest.agents}
    agents = []
    for agent_id, record in sorted(at_turn.items()):
        st = record.state
        agents.append(AgentState(
            agent_id=agent_id,
            balance=st.balance if st.balance is not None else 10.0,
            trust_score=st.trust_score if st.trust_score is not None else 50.0,
            specialty=specialties.get(agent_id) or "ore",
            inventory=dict(st.inventory or {}),
            alive=True,
            spouse_id=st.spouse_id,
        ))
    return Probe(
        probe_id=f"fidelity-t{turn}", family="propensity", seat=agents[0].agent_id,
        difficulty=2, k_turns=1,
        world=ProbeWorld(start_turn=turn, seed=21, condition="neutral", agents=agents),
    )


async def _restore(factory, turn, records, manifest, session_id="restored"):
    probe = _probe_from_state(turn, records, manifest)
    # Carry the v5 fields the probe world does not model directly.
    state_by_agent = {r.agent_id: r.state for r in records if r.turn == turn}
    async with factory() as session:
        await restore_world(session, session_id, probe, states=state_by_agent)
    return probe


async def test_restored_world_matches_every_agent_column():
    factory, engine = await _factory()
    await _live_run(factory)
    async with factory() as session:
        manifest, records, _ = await export_session(session, SID, seed=21)
        original = (await session.execute(
            select(Agent).where(Agent.session_id == SID)
        )).scalars().all()
        original_by_id = {a.agent_id: a for a in original}

    await _restore(factory, TURNS, records, manifest)
    async with factory() as session:
        restored = (await session.execute(
            select(Agent).where(Agent.session_id == "restored")
        )).scalars().all()
    await engine.dispose()

    columns = [c for c in Agent.__table__.columns.keys() if c not in RESTORE_EXEMPT]
    for row in restored:
        source = original_by_id[row.agent_id]
        for column in columns:
            assert getattr(row, column) == getattr(source, column), (
                f"{row.agent_id}.{column}: restored {getattr(row, column)!r} "
                f"!= original {getattr(source, column)!r}"
            )


async def test_restored_world_brief_is_identical():
    """The model must see the same world, not merely an equivalent database."""
    factory, engine = await _factory()
    await _live_run(factory)
    async with factory() as session:
        manifest, records, _ = await export_session(session, SID, seed=21)
        original_state = await _world_state(session, SID, TURNS)

    await _restore(factory, TURNS, records, manifest)
    async with factory() as session:
        restored_state = await _world_state(session, "restored", TURNS)
    await engine.dispose()

    for agent in original_state["agents"]:
        aid = agent["agent_id"]
        assert render_world_brief(original_state, aid) == render_world_brief(
            restored_state, aid
        ), f"world brief differs for {aid}"


def test_a_new_agent_column_fails_until_handled():
    """Reflection, not a hand-listed subset -- that is how steal_count was missed."""
    covered = set(TurnState.model_fields) | RESTORE_EXEMPT | {"agent_id"}
    uncovered = set(Agent.__table__.columns.keys()) - covered
    assert not uncovered, (
        f"Agent columns not carried by TurnState and not exempt: {sorted(uncovered)}. "
        "Add them to TurnState or to RESTORE_EXEMPT with a reason."
    )


async def test_steal_count_actually_survives_the_round_trip():
    """The specific field whose absence moved steal success from 20% to 60%."""
    factory, engine = await _factory()
    await _live_run(factory)
    async with factory() as session:
        manifest, records, _ = await export_session(session, SID, seed=21)
        thieves = {
            r.agent_id: r.state.steal_count
            for r in records if r.turn == TURNS and (r.state.steal_count or 0) > 0
        }

    await _restore(factory, TURNS, records, manifest)
    async with factory() as session:
        restored = (await session.execute(
            select(Agent).where(Agent.session_id == "restored")
        )).scalars().all()
    await engine.dispose()

    by_id = {a.agent_id: a for a in restored}
    for agent_id, count in thieves.items():
        assert by_id[agent_id].steal_count == count
