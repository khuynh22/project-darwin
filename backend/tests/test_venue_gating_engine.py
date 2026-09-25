"""Gating, from the engine's side: what moves, what is refused, what it costs."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import AgentDecision, BaseAgent
from app.db import Base
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.event_engine import run_events
from app.oracle.space import travel_ticks

SID = "gate"


class Scripted(BaseAgent):
    provider = "scripted"

    def __init__(self, agent_id: str, *, script: list[tuple[str, dict]], wake_after: float = 1.0):
        super().__init__(agent_id, "scripted")
        self.script = list(script)
        self.wake_after = wake_after

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        action, arguments = self.script[0] if len(self.script) == 1 else self.script.pop(0)
        return AgentDecision(action, dict(arguments), wake_after=self.wake_after)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        for aid in ("red", "blue"):
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


async def _outcomes(session, agent_id: str | None = None) -> list[str]:
    stmt = select(ThoughtLog).where(ThoughtLog.session_id == SID)
    if agent_id is not None:
        stmt = stmt.where(ThoughtLog.agent_id == agent_id)
    rows = (await session.execute(stmt.order_by(ThoughtLog.id))).scalars().all()
    return [r.outcome for r in rows]


async def test_an_action_from_the_wrong_venue_is_refused_and_recorded(session):
    agents = {
        "red": Scripted("red", script=[("steal", {"target": "blue"})]),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=4, venue_gating=True
    )

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue == "plaza"
    assert any("not available here" in o for o in await _outcomes(session))


async def test_travel_moves_the_agent_and_then_the_action_lands(session):
    agents = {
        "red": Scripted(
            "red",
            script=[("travel", {"venue": "alley"}), ("steal", {"target": "blue"})],
        ),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    result = await run_events(
        session, session_id=SID, agents=agents, horizon_beats=12, venue_gating=True
    )

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue == "alley"
    outcomes = await _outcomes(session)
    assert any("walking to alley" in o for o in outcomes)
    # Blue never leaves the plaza, so its own "rest" (a lounge action) is
    # correctly refused under gating -- that is not a regression in red's
    # journey. Scope the "no unintended rejection" check to red.
    red_outcomes = await _outcomes(session, "red")
    assert not any("not available here" in o for o in red_outcomes)

    travel_event = next(
        e for e in result.events if e.event.agent_id == "red" and e.action == "travel"
    )
    assert travel_event.busy_ticks == travel_ticks("plaza", "alley")


async def test_a_stale_venue_degrades_to_the_plaza(session):
    row = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    row.venue = "atlantis"
    await session.commit()

    agents = {
        "red": Scripted("red", script=[("travel", {"venue": "market"})]),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=6, venue_gating=True
    )

    assert any("walking to market" in o for o in await _outcomes(session))


async def test_ungated_runs_still_derive_the_venue_from_the_action(session):
    agents = {
        "red": Scripted("red", script=[("steal", {"target": "blue"})]),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(session, session_id=SID, agents=agents, horizon_beats=4)

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue == "alley"
