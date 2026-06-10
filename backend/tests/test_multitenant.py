"""Cross-session isolation: the same agent_id in two sessions must never
read or write each other's rows."""

from __future__ import annotations

import random

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models.agent import Agent
from app.models.ledger import Transaction
from app.oracle.actions import _get_agent, do_gift, do_work

SID_A = "alpha"
SID_B = "bravo"


def _agent(session_id: str, agent_id: str, balance: float) -> Agent:
    return Agent(
        session_id=session_id,
        agent_id=agent_id,
        display_name=agent_id.upper(),
        provider="stub",
        personality="x",
        sprite=agent_id,
        balance=balance,
        allies=[],
        enemies=[],
        inventory={"ore": 0, "food": 0, "tech": 0},
    )


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        # Both sessions share the SAME agent ids ("red"/"blue").
        s.add_all(
            [
                _agent(SID_A, "red", 10.0),
                _agent(SID_A, "blue", 10.0),
                _agent(SID_B, "red", 10.0),
                _agent(SID_B, "blue", 10.0),
            ]
        )
        await s.commit()
        yield s


@pytest.mark.asyncio
async def test_get_agent_is_session_scoped(session):
    a_red = await _get_agent(session, SID_A, "red")
    b_red = await _get_agent(session, SID_B, "red")
    assert a_red is not None and b_red is not None
    assert a_red is not b_red  # distinct rows despite identical agent_id


@pytest.mark.asyncio
async def test_work_in_one_session_does_not_touch_the_other(session):
    res = await do_work(session, session_id=SID_A, turn=1, actor_id="red", rng=random.Random(0))
    assert res.success

    a_red = await session.get(Agent, (SID_A, "red"))
    b_red = await session.get(Agent, (SID_B, "red"))
    assert a_red.balance > 10.0  # earned in session A
    assert b_red.balance == 10.0  # session B untouched


@pytest.mark.asyncio
async def test_transactions_are_tagged_with_session(session):
    await do_gift(session, session_id=SID_A, turn=1, actor_id="red", target="blue", amount=2.0)
    await session.commit()

    rows = (await session.execute(select(Transaction))).scalars().all()
    assert rows  # gift records ledger rows
    assert all(r.session_id == SID_A for r in rows)

    # Session B balances are completely unaffected by A's gift.
    b_red = await session.get(Agent, (SID_B, "red"))
    b_blue = await session.get(Agent, (SID_B, "blue"))
    assert b_red.balance == 10.0 and b_blue.balance == 10.0


@pytest.mark.asyncio
async def test_engine_settlement_paths_are_session_isolated(session):
    """Run session A through a full tax cycle; session B must stay pristine.

    This exercises the engine's settlement queries (_apply_survival_tax,
    _process_deferred, _check_bankruptcies, apex sweep) which run over
    ``select(Agent)`` — a missing session filter there would tax/settle both
    worlds together.
    """
    from app.agents.stub import StubAgent
    from app.models.ledger import ThoughtLog, WorldEvent
    from app.oracle.engine import run_turn

    async def snapshot_b() -> dict:
        rows = (
            (await session.execute(select(Agent).where(Agent.session_id == SID_B)))
            .scalars()
            .all()
        )
        return {a.agent_id: (a.balance, a.alive, a.trust_score) for a in rows}

    before = await snapshot_b()

    agents_a = {aid: StubAgent(agent_id=aid, model="stub") for aid in ("red", "blue")}
    # 12 turns crosses the tax cycle boundary (tax_interval_turns defaults to 10).
    for t in range(1, 13):
        await run_turn(session, session_id=SID_A, turn=t, agents=agents_a)

    after = await snapshot_b()
    assert after == before, f"session B mutated by A's turns: {before} -> {after}"

    # No A-driven ledger/thought/event rows leaked into B.
    for model in (Transaction, ThoughtLog, WorldEvent):
        rows = (
            (await session.execute(select(model).where(model.session_id == SID_B)))
            .scalars()
            .all()
        )
        assert rows == [], f"{model.__name__} rows leaked into session B"
