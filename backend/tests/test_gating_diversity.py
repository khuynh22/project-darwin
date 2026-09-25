"""Gating must not collapse the action distribution.

The failure mode this pack risks is an agent that never leaves the building it
woke in, or one that does nothing but walk. A stub roster is the cheapest
detector: it has no strategy, so any narrowing is the mechanic's doing and not
the model's.

The spec asks for a *comparison*, so both modes run at the same seed and horizon
and the gated arm is measured against the ungated one. Hand-tuned absolutes on
the gated arm alone cannot see a collapse -- they only say whether today's
numbers are inside a band somebody once picked -- and they need re-tuning every
time a content pack changes what a building is for.

Observed at seed 7 over 60 beats when this was written: ungated 39 events, 17
distinct actions, no travel; gated 41 events, 10 distinct actions, 49% travel.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.stub import StubAgent
from app.db import Base
from app.models.agent import Agent
from app.models.ledger import ThoughtLog
from app.oracle.event_engine import run_events

SID = "div"
AGENT_IDS = ("red", "blue", "green")
SEED = 7
HORIZON_BEATS = 60


@dataclass
class Arm:
    actions: list[str]
    venues: list[str]
    gate_rejections: int

    @property
    def events(self) -> int:
        return len(self.actions)

    @property
    def distinct(self) -> int:
        return len(set(self.actions))

    @property
    def travel_share(self) -> float:
        return self.actions.count("travel") / max(1, self.events)


async def _arm(*, gated: bool) -> Arm:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            for aid in AGENT_IDS:
                session.add(
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
            await session.commit()
            agents = {aid: StubAgent(agent_id=aid, model="stub") for aid in AGENT_IDS}
            result = await run_events(
                session,
                session_id=SID,
                agents=agents,
                horizon_beats=HORIZON_BEATS,
                seed=SEED,
                venue_gating=gated,
            )
            rows = (
                await session.execute(
                    select(ThoughtLog)
                    .where(ThoughtLog.session_id == SID)
                    .order_by(ThoughtLog.id)
                )
            ).scalars().all()
    finally:
        await engine.dispose()

    return Arm(
        actions=[r.action for r in rows],
        venues=[e.venue for e in result.events],
        gate_rejections=sum(
            "not available here" in (r.outcome or "") for r in rows
        ),
    )


async def test_gating_does_not_collapse_the_action_distribution():
    ungated = await _arm(gated=False)
    gated = await _arm(gated=True)

    assert ungated.events > 10, "the ungated run did not produce enough events to judge"
    assert gated.events > 10, "the gated run did not produce enough events to judge"

    # Self-calibrating: the ungated arm is whatever the current action table
    # affords, so a content pack that changes the catalogue moves both sides.
    assert gated.distinct >= ungated.distinct / 2, (
        f"gating halved the action space: {gated.distinct} distinct actions "
        f"against {ungated.distinct} ungated"
    )
    # Travel exists so agents can reach other buildings; it must not be all
    # they do. The ungated arm cannot call it at all, so there is nothing to
    # compare against -- this one stays an absolute.
    assert gated.travel_share < 0.65, f"travel share {gated.travel_share:.2f}"
    assert ungated.travel_share == 0.0


async def test_a_gated_stub_run_visits_more_than_one_building():
    gated = await _arm(gated=True)

    assert len(set(gated.venues)) > 1, set(gated.venues)


async def test_the_gate_refuses_nothing_the_prompt_offered():
    """The prompt's venue and the gate's venue must be the same venue.

    A stub only ever picks from ``actions_at(here, gated=True)``, so a single
    rejection means the building the agent was told it was standing at and the
    building the engine gated against had drifted apart.
    """
    ungated = await _arm(gated=False)
    gated = await _arm(gated=True)

    assert gated.gate_rejections == 0
    assert ungated.gate_rejections == 0
