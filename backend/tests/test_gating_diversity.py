"""Gating must not collapse the action distribution.

The failure mode this pack risks is an agent that never leaves the building it
woke in. A stub roster is the cheapest detector: it has no strategy, so any
narrowing is the mechanic's doing and not the model's.
"""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.stub import StubAgent
from app.db import Base
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.event_engine import run_events

SID = "div"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for aid in ("red", "blue", "green"):
            s.add(
                Agent(
                    session_id=SID,
                    agent_id=aid,
                    display_name=aid.title(),
                    provider="stub",
                    personality="x",
                    sprite=aid,
                    balance=10.0,
                    venue="plaza",
                )
            )
        await s.commit()
        yield s
    await engine.dispose()


async def test_a_gated_stub_run_visits_more_than_one_building(session):
    agents = {aid: StubAgent(agent_id=aid, model="stub") for aid in ("red", "blue", "green")}
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=60,
        seed=7, venue_gating=True,
    )

    rows = (
        await session.execute(
            select(ThoughtLog).where(ThoughtLog.session_id == SID)
        )
    ).scalars().all()
    actions = [r.action for r in rows]

    assert len(rows) > 10, "the run did not produce enough events to judge"
    # Travel exists so agents can reach other buildings; it must not be all they do.
    assert actions.count("travel") < len(actions) * 0.8
    assert len(set(actions)) >= 4
    assert sum("not available here" in (r.outcome or "") for r in rows) < len(rows) * 0.2
