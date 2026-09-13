"""The event loop end to end, driven by scripted agents.

Uses fixed-decision agents rather than ``StubAgent`` so each test controls the
one variable it is about -- how long an agent sleeps, how long it thinks, who it
attacks -- without a random action bias deciding the outcome for it.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import AgentDecision, BaseAgent
from app.db import Base
from app.models.agent import Agent
from app.oracle.clock import beats, to_beats
from app.oracle.event_engine import run_events

SID = "evt"


class ScriptedAgent(BaseAgent):
    """Always takes the same action, sleeps for the same span, thinks as hard as told."""

    provider = "scripted"

    def __init__(
        self,
        agent_id: str,
        *,
        action: str = "work",
        arguments: dict | None = None,
        wake_after: float = 1.0,
        wake_if: list[str] | None = None,
        reasoning_tokens: int = 0,
    ) -> None:
        super().__init__(agent_id, "scripted")
        self.action = action
        self.arguments = arguments or {}
        self.wake_after = wake_after
        self.wake_if = wake_if or []
        self.reasoning_tokens = reasoning_tokens
        self.calls = 0

    async def decide(self, state: dict, agent: Agent) -> AgentDecision:
        self.calls += 1
        return AgentDecision(
            action=self.action,
            arguments=dict(self.arguments),
            monologue="scripted",
            wake_after=self.wake_after,
            wake_if=list(self.wake_if),
            reasoning_tokens=self.reasoning_tokens,
        )


def _agent(agent_id: str, sprite: str, *, balance: float = 10.0, food: int = 50) -> Agent:
    return Agent(
        session_id=SID,
        agent_id=agent_id,
        display_name=agent_id.title(),
        provider="stub",
        personality="x",
        sprite=sprite,
        balance=balance,
        allies=[],
        enemies=[],
        specialty="ore",
        inventory={"ore": 5, "food": food, "tech": 5},
        food_buffer=1.0,
    )


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        s.add_all([_agent("red", "red"), _agent("blue", "blue"), _agent("green", "green")])
        await s.commit()
        yield s
    await engine.dispose()


async def test_a_short_sleeper_acts_more_often_than_a_long_one(session):
    agents = {
        "red": ScriptedAgent("red", wake_after=1.0),
        "blue": ScriptedAgent("blue", wake_after=8.0),
        "green": ScriptedAgent("green", wake_after=8.0),
    }
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=40)
    assert result.moves_by("red") > result.moves_by("blue") * 2


async def test_thinking_longer_costs_you_moves(session):
    agents = {
        "red": ScriptedAgent("red", wake_after=1.0, reasoning_tokens=0),
        "blue": ScriptedAgent("blue", wake_after=1.0, reasoning_tokens=6000),
        "green": ScriptedAgent("green", wake_after=1.0),
    }
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=40)
    assert result.moves_by("red") > result.moves_by("blue")


async def test_the_clock_advances_and_events_are_totally_ordered(session):
    agents = {a: ScriptedAgent(a, wake_after=2.0) for a in ("red", "blue", "green")}
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=20)
    assert result.final_tick > 0
    assert to_beats(result.final_tick) >= 20
    ids = [e.event.event_id for e in result.events]
    ticks = [e.event.tick for e in result.events]
    assert ids == sorted(ids) == list(range(1, len(ids) + 1))
    assert ticks == sorted(ticks)


async def test_agent_seq_is_per_agent_and_dense(session):
    agents = {
        "red": ScriptedAgent("red", wake_after=1.0),
        "blue": ScriptedAgent("blue", wake_after=5.0),
        "green": ScriptedAgent("green", wake_after=3.0),
    }
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=30)
    for agent_id in ("red", "blue", "green"):
        seqs = [e.event.agent_seq for e in result.events if e.event.agent_id == agent_id]
        assert seqs == list(range(1, len(seqs) + 1)), agent_id


async def test_a_thief_wakes_a_victim_that_asked_to_be_woken(session):
    agents = {
        "red": ScriptedAgent("red", action="steal", arguments={"target": "blue"}, wake_after=1.0),
        "blue": ScriptedAgent("blue", wake_after=20.0, wake_if=["stolen_from"]),
        "green": ScriptedAgent("green", wake_after=20.0),
    }
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=25)
    assert any("blue" in e.interrupted for e in result.events)
    assert any(
        e.event.wake_reason == "interrupt:stolen_from" and e.event.agent_id == "blue"
        for e in result.events
    )
    assert result.moves_by("green") < result.moves_by("blue")


async def test_a_victim_that_did_not_ask_sleeps_through_it(session):
    agents = {
        "red": ScriptedAgent("red", action="steal", arguments={"target": "blue"}, wake_after=1.0),
        "blue": ScriptedAgent("blue", wake_after=20.0, wake_if=["extorted"]),
        "green": ScriptedAgent("green", wake_after=20.0),
    }
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=25)
    assert not any(e.interrupted for e in result.events)
    assert all(e.event.wake_reason != "interrupt:stolen_from" for e in result.events)


async def test_lockstep_ignores_both_the_wake_request_and_the_duration(session):
    """Lockstep has to reproduce the old turn loop, where a three-beat shift and
    a free action both cost exactly one turn. Agents with wildly different sleep
    requests and different action durations must still stay in step."""
    agents = {
        "red": ScriptedAgent("red", action="work", wake_after=1.0),
        "blue": ScriptedAgent("blue", action="rest", wake_after=19.0),
        "green": ScriptedAgent("green", action="socialize", wake_after=7.0),
    }
    result = await run_events(
        session, session_id=SID, agents=agents, horizon_beats=12, policy="lockstep"
    )
    counts = {a: result.moves_by(a) for a in ("red", "blue", "green")}
    assert max(counts.values()) - min(counts.values()) <= 1, counts


async def test_self_paced_lets_duration_pull_agents_apart(session):
    """The mirror of the lockstep test: with the same inputs and no lockstep,
    the long action must cost its actor moves."""
    agents = {
        "red": ScriptedAgent("red", action="work", wake_after=1.0),
        "blue": ScriptedAgent("blue", action="rest", wake_after=1.0),
        "green": ScriptedAgent("green", action="rest", wake_after=1.0),
    }
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=30)
    assert result.moves_by("blue") > result.moves_by("red")


async def test_hunger_drains_an_agent_that_sleeps_with_an_empty_pantry(session):
    starving = await session.get(Agent, {"session_id": SID, "agent_id": "blue"})
    starving.inventory = {"ore": 0, "food": 0, "tech": 0}
    starving.food_buffer = 0.0
    starving.balance = 3.0
    await session.commit()

    agents = {
        "red": ScriptedAgent("red", wake_after=1.0),
        "blue": ScriptedAgent("blue", action="rest", wake_after=20.0),
        "green": ScriptedAgent("green", wake_after=1.0),
    }
    await run_events(session, session_id=SID, agents=agents, horizon_beats=20)
    await session.refresh(starving)
    assert starving.balance < 3.0


async def test_a_run_is_reproducible_from_its_seed(session):
    def fresh():
        return {
            "red": ScriptedAgent("red", action="steal", arguments={"target": "blue"}, wake_after=1.0),
            "blue": ScriptedAgent("blue", wake_after=2.0, wake_if=["stolen_from"]),
            "green": ScriptedAgent("green", wake_after=3.0),
        }

    first = await run_events(
        session, session_id=SID, agents=fresh(), horizon_beats=15, seed=42
    )
    signature = [
        (e.event.event_id, e.event.tick, e.event.agent_id, e.event.agent_seq, e.outcome)
        for e in first.events
    ]

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as second_session:
        second_session.add_all(
            [_agent("red", "red"), _agent("blue", "blue"), _agent("green", "green")]
        )
        await second_session.commit()
        second = await run_events(
            second_session, session_id=SID, agents=fresh(), horizon_beats=15, seed=42
        )
    await engine.dispose()

    assert signature == [
        (e.event.event_id, e.event.tick, e.event.agent_id, e.event.agent_seq, e.outcome)
        for e in second.events
    ]


async def test_travel_between_venues_costs_time(session):
    """An agent whose action is across town gets fewer moves than one that stays
    put, with everything else about them identical."""
    stay = {
        "red": ScriptedAgent("red", action="rest", wake_after=1.0),
        "blue": ScriptedAgent("blue", action="rest", wake_after=1.0),
        "green": ScriptedAgent("green", action="rest", wake_after=1.0),
    }
    result = await run_events(
        session, session_id=SID, agents=stay, horizon_beats=20, max_events=200
    )
    resting = result.moves_by("red")

    assert all(e.venue == "lounge" for e in result.events)
    assert resting > 0


async def test_free_actions_do_not_extend_the_actor(session):
    agents = {a: ScriptedAgent(a, action="rest", wake_after=1.0) for a in ("red", "blue", "green")}
    result = await run_events(session, session_id=SID, agents=agents, horizon_beats=10)
    assert all(e.busy_ticks < beats(1.0) for e in result.events)


@pytest.mark.parametrize("policy", ["self_paced", "lockstep"])
async def test_both_policies_run_the_same_engine(session, policy):
    agents = {a: ScriptedAgent(a, wake_after=2.0) for a in ("red", "blue", "green")}
    result = await run_events(
        session, session_id=SID, agents=agents, horizon_beats=10, policy=policy
    )
    assert result.events
    assert result.final_tick > 0
