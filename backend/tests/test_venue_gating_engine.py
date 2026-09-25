"""Gating, from the engine's side: what moves, what is refused, what it costs."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import AgentDecision, BaseAgent
from app.db import Base
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.engine import run_turn
from app.oracle.event_engine import run_events
from app.oracle.space import travel_ticks
from app.oracle.world_data import BUILT_VENUES

SID = "gate"


class Scripted(BaseAgent):
    provider = "scripted"

    def __init__(
        self,
        agent_id: str,
        *,
        script: list[tuple[str, dict]],
        wake_after: float = 1.0,
        wake_if: list[str] | None = None,
    ):
        super().__init__(agent_id, "scripted")
        self.script = list(script)
        self.wake_after = wake_after
        self.wake_if = list(wake_if or [])

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        action, arguments = self.script[0] if len(self.script) == 1 else self.script.pop(0)
        return AgentDecision(
            action,
            dict(arguments),
            wake_after=self.wake_after,
            wake_if=list(self.wake_if),
        )


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
    assert any("not available here" in o for o in await _outcomes(session, "blue"))

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


async def test_a_malformed_travel_argument_does_not_move_the_agent(session):
    agents = {
        "red": Scripted("red", script=[("travel", {"venue": None})], wake_after=25.0),
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
    assert any(
        "argument validation failed" in o for o in await _outcomes(session, "red")
    )


async def test_a_stale_venue_cannot_travel_to_where_the_engine_already_put_it(session):
    """The handler and the engine must agree about where the agent is standing.

    The engine normalises an unknown row to the plaza, so a walk to the plaza is
    a walk to nowhere. Read off the raw row it looks like a move.
    """
    row = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    row.venue = "atlantis"
    await session.commit()

    agents = {
        "red": Scripted("red", script=[("travel", {"venue": "plaza"})], wake_after=25.0),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(
        session, session_id=SID, agents=agents, horizon_beats=4, venue_gating=True
    )

    red_outcomes = await _outcomes(session, "red")
    assert any("already at plaza" in o for o in red_outcomes), red_outcomes
    assert not any("walking to plaza" in o for o in red_outcomes)


async def test_a_gate_rejected_action_does_not_wake_its_target(session):
    """No mutation happened, so the victim has nothing to be woken about.

    An interrupt here costs the target an unscheduled wake -- a real provider
    call, a perturbed schedule, and a ``wake_reason`` in the trace asserting a
    theft the engine refused to run.
    """
    agents = {
        "red": Scripted("red", script=[("steal", {"target": "blue"})]),
        "blue": Scripted(
            "blue", script=[("rest", {})], wake_after=25.0, wake_if=["stolen_from"]
        ),
    }
    result = await run_events(
        session, session_id=SID, agents=agents, horizon_beats=8, venue_gating=True
    )

    red_events = [e for e in result.events if e.event.agent_id == "red"]
    assert red_events
    assert all("not available here" in e.outcome for e in red_events)
    assert all(e.interrupted == [] for e in red_events)
    assert not any(e.event.wake_reason == "interrupt:stolen_from" for e in result.events)


async def test_a_handler_rejection_still_wakes_its_target(session):
    """The gate is the exception, not the ``[rejected]`` suffix.

    Red is standing where ``trade`` lives, so the gate lets it through; the
    handler then refuses for want of funds. Blue asked to be woken by a trade
    offer and one was genuinely made at it.
    """
    row = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    row.venue = "market"
    await session.commit()

    agents = {
        "red": Scripted(
            "red", script=[("trade", {"target": "blue", "amount": 999.0})]
        ),
        "blue": Scripted(
            "blue", script=[("rest", {})], wake_after=25.0, wake_if=["trade_offered"]
        ),
    }
    result = await run_events(
        session, session_id=SID, agents=agents, horizon_beats=8, venue_gating=True
    )

    red_events = [e for e in result.events if e.event.agent_id == "red"]
    assert any("insufficient funds" in e.outcome for e in red_events)
    assert any("blue" in e.interrupted for e in red_events)


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


async def test_an_ungated_travel_call_leaves_the_agent_at_a_real_building(session):
    """A model can emit a tool it was never offered, and weak ones do.

    Ungated there is no ``travel`` in the catalogue, so the call is unasked for;
    the row it writes must still name a building rather than the ``anywhere``
    sentinel that ``travel`` carries in ``shared/actions.json``.
    """
    agents = {
        "red": Scripted("red", script=[("travel", {"venue": "alley"})], wake_after=25.0),
        "blue": Scripted("blue", script=[("rest", {})], wake_after=25.0),
    }
    await run_events(session, session_id=SID, agents=agents, horizon_beats=4)

    red = (
        await session.execute(
            select(Agent).where(Agent.session_id == SID, Agent.agent_id == "red")
        )
    ).scalar_one()
    assert red.venue in BUILT_VENUES


async def test_run_turn_survives_an_unoffered_travel_call(session):
    agents = {
        "red": Scripted("red", script=[("travel", {"venue": "alley"})]),
        "blue": Scripted("blue", script=[("rest", {})]),
    }
    await run_turn(session, session_id=SID, turn=1, agents=agents, seed=3)

    rows = (
        await session.execute(select(Agent).where(Agent.session_id == SID))
    ).scalars().all()
    for row in rows:
        assert row.venue in BUILT_VENUES, row.venue
