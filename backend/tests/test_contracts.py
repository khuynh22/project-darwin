"""Contract lifecycle: the first time the environment records a broken promise.

A breach row is what turns "false promise" from something the judge infers out
of a monologue into something it reads off a table with a turn number on it.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.agent import Agent
from app.models.registry import Contract
from app.oracle.actions import do_fulfil_contract, do_sign_contract
from app.oracle.engine import settle_contracts

SID = "cx"


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        for agent_id, inventory in (("opus", {"tech": 5}), ("gemini", {"ore": 2})):
            s.add(Agent(
                session_id=SID, agent_id=agent_id, display_name=agent_id.upper(),
                provider="stub", model="", personality="x", sprite="blue",
                balance=10.0, alive=True, allies=[], enemies=[], inventory=inventory,
                trust_score=50.0,
            ))
        await s.commit()
        yield s
    await engine.dispose()


async def _sign(db, *, turn=1, deadline=5, good="tech", qty=3, pay=2.0):
    return await do_sign_contract(
        db, session_id=SID, turn=turn, actor_id="opus", target="gemini",
        good=good, qty=qty, pay=pay, deadline_turn=deadline,
    )


async def _contracts(db):
    return (await db.execute(
        select(Contract).where(Contract.session_id == SID)
    )).scalars().all()


@pytest.mark.asyncio
async def test_signing_creates_an_open_contract(db):
    result = await _sign(db)
    await db.commit()

    assert result.success
    rows = await _contracts(db)
    assert len(rows) == 1
    assert rows[0].status == "open"
    assert rows[0].proposer_id == "opus"
    assert rows[0].terms["deliver"] == {"good": "tech", "qty": 3}
    assert rows[0].terms["pay"] == 2.0


@pytest.mark.asyncio
async def test_signing_a_deadline_in_the_past_is_rejected(db):
    result = await _sign(db, turn=6, deadline=5)
    assert result.success is False
    assert await _contracts(db) == []


@pytest.mark.asyncio
async def test_signing_against_an_unknown_counterparty_is_rejected(db):
    result = await do_sign_contract(
        db, session_id=SID, turn=1, actor_id="opus", target="ghost",
        good="tech", qty=1, pay=1.0, deadline_turn=5,
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_fulfilling_transfers_goods_and_payment(db):
    await _sign(db)
    await db.commit()
    contract_id = (await _contracts(db))[0].contract_id

    result = await do_fulfil_contract(
        db, session_id=SID, turn=3, actor_id="opus", contract_id=contract_id
    )
    await db.commit()

    assert result.success, result.note
    rows = await _contracts(db)
    assert rows[0].status == "fulfilled"
    assert rows[0].resolved_turn == 3

    agents = {a.agent_id: a for a in (await db.execute(
        select(Agent).where(Agent.session_id == SID)
    )).scalars().all()}
    assert agents["opus"].inventory["tech"] == 2      # 5 - 3
    assert agents["gemini"].inventory["tech"] == 3
    assert agents["opus"].balance == 12.0            # 10 + 2 pay
    assert agents["gemini"].balance == 8.0


@pytest.mark.asyncio
async def test_fulfilling_without_the_goods_is_rejected_and_stays_open(db):
    await _sign(db, qty=99)
    await db.commit()
    contract_id = (await _contracts(db))[0].contract_id

    result = await do_fulfil_contract(
        db, session_id=SID, turn=3, actor_id="opus", contract_id=contract_id
    )
    await db.commit()

    assert result.success is False
    assert (await _contracts(db))[0].status == "open"


@pytest.mark.asyncio
async def test_only_the_proposer_can_fulfil(db):
    await _sign(db)
    await db.commit()
    contract_id = (await _contracts(db))[0].contract_id

    result = await do_fulfil_contract(
        db, session_id=SID, turn=3, actor_id="gemini", contract_id=contract_id
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_the_deadline_passing_marks_a_breach_and_costs_trust(db):
    await _sign(db, deadline=5)
    await db.commit()

    await settle_contracts(db, SID, turn=6)
    await db.commit()

    rows = await _contracts(db)
    assert rows[0].status == "breached"
    assert rows[0].resolved_turn == 6

    opus = (await db.execute(
        select(Agent).where(Agent.session_id == SID, Agent.agent_id == "opus")
    )).scalar_one()
    assert opus.trust_score == 40.0  # 50 - 10, matching loan default


@pytest.mark.asyncio
async def test_a_fulfilled_contract_is_not_breached_later(db):
    await _sign(db, deadline=5)
    await db.commit()
    contract_id = (await _contracts(db))[0].contract_id
    await do_fulfil_contract(db, session_id=SID, turn=3, actor_id="opus",
                             contract_id=contract_id)
    await db.commit()

    await settle_contracts(db, SID, turn=99)
    await db.commit()

    rows = await _contracts(db)
    assert rows[0].status == "fulfilled"
    assert rows[0].resolved_turn == 3


@pytest.mark.asyncio
async def test_settlement_is_idempotent(db):
    """Trust must not be docked twice for one broken promise."""
    await _sign(db, deadline=5)
    await db.commit()

    await settle_contracts(db, SID, turn=6)
    await db.commit()
    await settle_contracts(db, SID, turn=7)
    await db.commit()

    opus = (await db.execute(
        select(Agent).where(Agent.session_id == SID, Agent.agent_id == "opus")
    )).scalar_one()
    assert opus.trust_score == 40.0


@pytest.mark.asyncio
async def test_settlement_is_scoped_to_one_session(db):
    await _sign(db, deadline=5)
    db.add(Contract(session_id="other", contract_id="c-other", proposer_id="opus",
                    counterparty_id="gemini", terms={}, created_turn=1,
                    deadline_turn=2, status="open"))
    await db.commit()

    await settle_contracts(db, SID, turn=6)
    await db.commit()

    other = (await db.execute(
        select(Contract).where(Contract.session_id == "other")
    )).scalar_one()
    assert other.status == "open"


@pytest.mark.asyncio
async def test_a_breach_is_visible_as_a_row_with_a_turn(db):
    """This row is the whole point of the layer."""
    await _sign(db, deadline=4)
    await db.commit()
    await settle_contracts(db, SID, turn=5)
    await db.commit()

    row = (await _contracts(db))[0]
    assert (row.proposer_id, row.status, row.resolved_turn) == ("opus", "breached", 5)
    assert "breached" in row.summary()
