"""Determinism / reproducibility of the Oracle's randomness.

The environment's stochastic mechanics (work reward, steal success, betting,
investment outcomes, specialty assignment) must be driven by an *injected*,
seeded RNG -- not the global ``random`` module -- so that a run is reproducible
from its seed even under multi-tenant concurrency.
"""

from __future__ import annotations

import random

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table in metadata)
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.actions import do_work
from app.oracle.engine import run_turn, seed_roster

SID = "seedtest"


def _stub_roster() -> list[dict]:
    return [
        {
            "agent_id": f"a{i}",
            "display_name": f"A{i}",
            "provider": "stub",
            "personality": "x",
            "sprite": "blue",
            "model": "",
        }
        for i in range(3)
    ]


async def _run_stub_sim(seed: int, turns: int = 8):
    """Run a full stub simulation and return a signature of everything that
    happened (decisions + outcomes + final agent state)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    roster = _stub_roster()
    async with Session() as s:
        await seed_roster(s, "rep", roster=roster, seed=seed)
        agents = build_agents(roster=roster)
        for t in range(1, turns + 1):
            await run_turn(s, session_id="rep", turn=t, agents=agents, seed=seed)
        thoughts = (
            (
                await s.execute(
                    select(ThoughtLog)
                    .where(ThoughtLog.session_id == "rep")
                    .order_by(ThoughtLog.id)
                )
            )
            .scalars()
            .all()
        )
        sig = [(t.turn, t.agent_id, t.action, t.monologue, t.outcome) for t in thoughts]
        rows = (
            (
                await s.execute(
                    select(Agent)
                    .where(Agent.session_id == "rep")
                    .order_by(Agent.agent_id)
                )
            )
            .scalars()
            .all()
        )
        final = [(a.agent_id, a.balance, a.specialty, a.alive) for a in rows]
    await engine.dispose()
    return sig, final


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        s.add(
            Agent(
                session_id=SID,
                agent_id="a",
                display_name="A",
                provider="stub",
                personality="x",
                sprite="x",
                balance=10.0,
                allies=[],
                enemies=[],
                inventory={"ore": 0, "food": 0, "tech": 0},
            )
        )
        await s.commit()
        yield s


@pytest.mark.asyncio
async def test_work_uses_injected_rng(session):
    # do_work must draw its reward from the INJECTED rng, not the global module.
    expected = round(random.Random(42).uniform(0.05, 0.20), 2)
    res = await do_work(
        session, session_id=SID, turn=1, actor_id="a", rng=random.Random(42)
    )
    assert res.delta == expected


@pytest.mark.asyncio
async def test_same_seed_reproduces_run():
    # Same seed + same stub roster must produce a byte-identical run.
    a = await _run_stub_sim(seed=12345)
    b = await _run_stub_sim(seed=12345)
    assert a == b


@pytest.mark.asyncio
async def test_different_seed_changes_run():
    # Different seeds must diverge (the seed actually drives the run).
    a = await _run_stub_sim(seed=1)
    b = await _run_stub_sim(seed=2)
    assert a != b
