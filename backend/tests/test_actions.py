"""Unit tests for the Oracle action handlers — exercised against an in-memory SQLite."""
from __future__ import annotations

import random

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models.agent import Agent
from app.oracle.actions import do_bet, do_sabotage, do_socialize, do_trade, do_work


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        s.add_all(
            [
                Agent(agent_id="a", display_name="A", provider="stub", personality="x", sprite="x", balance=10.0, allies=[], enemies=[]),
                Agent(agent_id="b", display_name="B", provider="stub", personality="x", sprite="x", balance=10.0, allies=[], enemies=[]),
            ]
        )
        await s.commit()
        yield s


@pytest.mark.asyncio
async def test_work_increases_balance(session):
    random.seed(1)
    res = await do_work(session, turn=1, actor_id="a")
    assert res.success
    assert 0.10 <= res.delta <= 0.50
    a = await session.get(Agent, "a")
    assert a.balance == round(10.0 + res.delta, 2)


@pytest.mark.asyncio
async def test_sabotage_costs_actor_and_skips_target(session):
    res = await do_sabotage(session, turn=1, actor_id="a", target="b", cost=1.0)
    assert res.success
    a = await session.get(Agent, "a")
    b = await session.get(Agent, "b")
    assert a.balance == 9.0
    assert b.skip_next_turn is True
    assert "b" in a.enemies and "a" in b.enemies


@pytest.mark.asyncio
async def test_marriage_pools_balances(session):
    a = await session.get(Agent, "a")
    a.balance = 4.0
    res = await do_socialize(session, turn=1, actor_id="a", target="b", proposal_type="marriage")
    assert res.success
    a = await session.get(Agent, "a")
    b = await session.get(Agent, "b")
    assert a.balance == 7.0 and b.balance == 7.0
    assert a.spouse_id == "b" and b.spouse_id == "a"


@pytest.mark.asyncio
async def test_bet_respects_funds(session):
    res = await do_bet(session, turn=1, actor_id="a", amount=999.0, bet_type="coin_flip")
    assert not res.success


@pytest.mark.asyncio
async def test_trade_rejected_when_insufficient(session):
    a = await session.get(Agent, "a")
    a.balance = 0.05
    res = await do_trade(session, turn=1, actor_id="a", target="b", amount=1.0, item="information")
    assert not res.success
