"""Unit tests for the Oracle action handlers -- exercised against an in-memory SQLite."""

from __future__ import annotations

import random

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models.agent import Agent
from app.oracle.actions import do_bet, do_sabotage, do_socialize, do_trade, do_work

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
                    agent_id="a",
                    display_name="A",
                    provider="stub",
                    personality="x",
                    sprite="x",
                    balance=10.0,
                    allies=[],
                    enemies=[],
                    inventory={"ore": 0, "food": 0, "tech": 0},
                ),
                Agent(
                    session_id=SID,
                    agent_id="b",
                    display_name="B",
                    provider="stub",
                    personality="x",
                    sprite="x",
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
async def test_work_increases_balance(session):
    res = await do_work(session, session_id=SID, turn=1, actor_id="a", rng=random.Random(1))
    assert res.success
    assert res.delta >= 0.05  # base + ore bonus
    a = await session.get(Agent, (SID, "a"))
    assert a.balance == round(10.0 + res.delta, 2)
    # Should produce 2-4 goods (2-3 specialty + 0-1 others)
    assert sum(a.inventory.values()) >= 2


@pytest.mark.asyncio
async def test_sabotage_costs_actor_and_skips_target(session):
    res = await do_sabotage(session, session_id=SID, turn=1, actor_id="a", target="b", cost=1.0)
    assert res.success
    a = await session.get(Agent, (SID, "a"))
    b = await session.get(Agent, (SID, "b"))
    assert a.balance == 9.0
    assert b.skip_next_turn is True
    assert "b" in a.enemies and "a" in b.enemies


@pytest.mark.asyncio
async def test_marriage_requires_mutual_consent(session):
    # First proposal: sets pending, no balance change
    a = await session.get(Agent, (SID, "a"))
    a.balance = 4.0
    res1 = await do_socialize(
        session, session_id=SID, turn=1, actor_id="a", target="b", proposal_type="marriage"
    )
    assert res1.success
    a = await session.get(Agent, (SID, "a"))
    assert a.balance == 4.0  # no pooling yet
    assert a.marriage_pending == "b"
    assert a.spouse_id is None

    # Second proposal from b to a: marriage happens
    res2 = await do_socialize(
        session, session_id=SID, turn=2, actor_id="b", target="a", proposal_type="marriage"
    )
    assert res2.success
    a = await session.get(Agent, (SID, "a"))
    b = await session.get(Agent, (SID, "b"))
    assert a.spouse_id == "b" and b.spouse_id == "a"
    assert a.balance == 7.0 and b.balance == 7.0  # pooled


@pytest.mark.asyncio
async def test_bet_respects_funds(session):
    res = await do_bet(
        session, session_id=SID, turn=1, actor_id="a", amount=999.0, bet_type="coin_flip", rng=random.Random(0)
    )
    assert not res.success


@pytest.mark.asyncio
async def test_trade_rejected_when_insufficient(session):
    a = await session.get(Agent, (SID, "a"))
    a.balance = 0.05
    res = await do_trade(session, session_id=SID, turn=1, actor_id="a", target="b", amount=1.0, rng=random.Random(0))
    assert not res.success
