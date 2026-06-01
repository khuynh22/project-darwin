"""Engine-level test: agents are eliminated as soon as they hit $0 cash,
regardless of invested capital, goods, or whether the tax cycle just fired."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models.agent import Agent
from app.oracle.engine import _check_bankruptcies

SID = "test"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        s.add_all(
            [
                Agent(
                    session_id=SID,
                    agent_id="broke",
                    display_name="Broke",
                    provider="stub",
                    personality="x",
                    sprite="red",
                    balance=0.0,
                    allies=[],
                    enemies=[],
                    inventory={"ore": 5, "food": 5, "tech": 5},
                ),
                Agent(
                    session_id=SID,
                    agent_id="rich",
                    display_name="Rich",
                    provider="stub",
                    personality="x",
                    sprite="blue",
                    balance=10.0,
                    allies=[],
                    enemies=[],
                    inventory={"ore": 0, "food": 0, "tech": 0},
                ),
            ]
        )
        await s.commit()
        yield s


@pytest.mark.asyncio
async def test_zero_balance_eliminates_even_with_full_inventory(session):
    # `broke` has $0 cash but 15 goods in inventory — old behavior would
    # have kept them alive (and the tax sweep would have left them at $0).
    # New rule: $0 cash = eliminated, full stop.
    eliminated = await _check_bankruptcies(session, SID, turn=5)
    await session.commit()

    broke = await session.get(Agent, (SID, "broke"))
    rich = await session.get(Agent, (SID, "rich"))

    assert "broke" in eliminated
    assert broke.alive is False
    assert broke.eliminated_at_turn == 5
    # Rich is untouched.
    assert "rich" not in eliminated
    assert rich.alive is True


@pytest.mark.asyncio
async def test_positive_balance_survives(session):
    eliminated = await _check_bankruptcies(session, SID, turn=3)
    rich = await session.get(Agent, (SID, "rich"))
    assert "rich" not in eliminated
    assert rich.alive is True


@pytest.mark.asyncio
async def test_dead_agent_is_not_re_eliminated(session):
    broke = await session.get(Agent, (SID, "broke"))
    broke.alive = False
    broke.eliminated_at_turn = 1
    await session.commit()

    eliminated = await _check_bankruptcies(session, SID, turn=5)
    assert "broke" not in eliminated
    # Original elimination turn preserved.
    broke_again = await session.get(Agent, (SID, "broke"))
    assert broke_again.eliminated_at_turn == 1
