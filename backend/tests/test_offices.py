"""Offices make a role claim falsifiable, and auditing makes knowledge earned.

Today information asymmetry is assigned by config. An auditor *earns* exact
knowledge of one agent's balance, which is what gives a concrete, checkable
reason to lie to a specific counterparty.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.agent import Agent
from app.models.ledger import WorldEvent
from app.models.registry import TERM_TURNS, Office
from app.oracle.actions import do_audit, do_stand_for_office
from app.oracle.engine import settle_offices

SID = "ofc"


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        for agent_id, balance in (("opus", 12.34), ("gemini", 3.50), ("grok", 7.0)):
            s.add(Agent(
                session_id=SID, agent_id=agent_id, display_name=agent_id.upper(),
                provider="stub", model="", personality="x", sprite="blue",
                balance=balance, alive=True, allies=[], enemies=[], inventory={},
                trust_score=50.0,
            ))
        await s.commit()
        yield s
    await engine.dispose()


async def _offices(db, session_id=SID):
    return (await db.execute(
        select(Office).where(Office.session_id == session_id)
    )).scalars().all()


@pytest.mark.asyncio
async def test_a_vacant_office_can_be_taken(db):
    result = await do_stand_for_office(
        db, session_id=SID, turn=3, actor_id="opus", office="auditor"
    )
    await db.commit()

    assert result.success, result.note
    rows = await _offices(db)
    assert len(rows) == 1
    assert (rows[0].office, rows[0].holder_id, rows[0].since_turn) == (
        "auditor", "opus", 3
    )


@pytest.mark.asyncio
async def test_an_occupied_office_cannot_be_taken(db):
    await do_stand_for_office(db, session_id=SID, turn=3, actor_id="opus",
                              office="auditor")
    await db.commit()

    result = await do_stand_for_office(db, session_id=SID, turn=4, actor_id="gemini",
                                       office="auditor")
    await db.commit()

    assert result.success is False
    rows = await _offices(db)
    assert rows[0].holder_id == "opus"


@pytest.mark.asyncio
async def test_an_unknown_office_is_rejected(db):
    result = await do_stand_for_office(db, session_id=SID, turn=1, actor_id="opus",
                                       office="emperor")
    assert result.success is False
    assert await _offices(db) == []


@pytest.mark.asyncio
async def test_the_term_expiring_vacates_the_office(db):
    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="opus",
                              office="auditor")
    await db.commit()

    await settle_offices(db, SID, turn=1 + TERM_TURNS)
    await db.commit()

    rows = await _offices(db)
    assert rows[0].holder_id is None


@pytest.mark.asyncio
async def test_an_office_within_its_term_is_not_vacated(db):
    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="opus",
                              office="auditor")
    await db.commit()

    await settle_offices(db, SID, turn=TERM_TURNS - 1)
    await db.commit()

    assert (await _offices(db))[0].holder_id == "opus"


@pytest.mark.asyncio
async def test_a_vacated_office_can_be_retaken(db):
    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="opus",
                              office="auditor")
    await db.commit()
    await settle_offices(db, SID, turn=1 + TERM_TURNS)
    await db.commit()

    result = await do_stand_for_office(db, session_id=SID, turn=1 + TERM_TURNS,
                                       actor_id="gemini", office="auditor")
    await db.commit()

    assert result.success
    assert (await _offices(db))[0].holder_id == "gemini"


@pytest.mark.asyncio
async def test_audit_by_a_non_auditor_is_rejected(db):
    """This rejection is what makes false_authority_claim worth telling."""
    result = await do_audit(db, session_id=SID, turn=2, actor_id="gemini",
                            target="opus")
    assert result.success is False
    assert "auditor" in result.note.lower()


@pytest.mark.asyncio
async def test_audit_by_the_auditor_returns_the_true_balance(db):
    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="gemini",
                              office="auditor")
    await db.commit()

    result = await do_audit(db, session_id=SID, turn=2, actor_id="gemini",
                            target="opus")
    await db.commit()

    assert result.success
    assert "12.34" in result.note


@pytest.mark.asyncio
async def test_the_audited_balance_is_recorded_as_ground_truth(db):
    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="gemini",
                              office="auditor")
    await db.commit()
    await do_audit(db, session_id=SID, turn=2, actor_id="gemini", target="opus")
    await db.commit()

    events = (await db.execute(
        select(WorldEvent).where(WorldEvent.session_id == SID,
                                 WorldEvent.kind == "audit")
    )).scalars().all()
    assert len(events) == 1
    assert events[0].payload["balance"] == 12.34
    assert events[0].payload["target"] == "opus"


@pytest.mark.asyncio
async def test_auditing_a_dead_or_unknown_agent_is_rejected(db):
    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="gemini",
                              office="auditor")
    await db.commit()

    result = await do_audit(db, session_id=SID, turn=2, actor_id="gemini",
                            target="ghost")
    assert result.success is False


@pytest.mark.asyncio
async def test_offices_are_scoped_by_session(db):
    # An agent can only hold office in a session it exists in, so the second
    # session needs its own roster row.
    db.add(Agent(session_id="other", agent_id="opus", display_name="OPUS",
                 provider="stub", model="", personality="x", sprite="blue",
                 balance=5.0, alive=True, allies=[], enemies=[], inventory={},
                 trust_score=50.0))
    await db.commit()

    await do_stand_for_office(db, session_id=SID, turn=1, actor_id="opus",
                              office="auditor")
    await do_stand_for_office(db, session_id="other", turn=1, actor_id="opus",
                              office="auditor")
    await db.commit()

    await settle_offices(db, SID, turn=1 + TERM_TURNS)
    await db.commit()

    assert (await _offices(db))[0].holder_id is None
    assert (await _offices(db, "other"))[0].holder_id == "opus"
