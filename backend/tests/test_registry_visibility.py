"""Registries must be visible to agents and carried in the trace.

An agent can only lie about what it can see, so the brief has to show the
registries. And a replayed turn must see the registries that were in force
*then*, not the ones that exist now.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.base import render_world_brief
from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.agent import Agent
from app.models.registry import Contract, Office
from app.oracle.engine import _world_state, run_turn, seed_roster
from app.trace.adapters.darwin_db import export_session

SID = "vis"


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        await seed_roster(s, SID, _roster(), seed=9)
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_the_brief_lists_office_holders(db):
    db.add(Office(session_id=SID, office="auditor", holder_id="a1", since_turn=1))
    db.add(Office(session_id=SID, office="bank", holder_id=None, since_turn=0))
    await db.commit()

    brief = render_world_brief(await _world_state(db, SID, 2), "a0")
    assert "OFFICES:" in brief
    assert "auditor=a1" in brief
    assert "bank=vacant" in brief


@pytest.mark.asyncio
async def test_the_brief_lists_open_contracts_and_marks_your_own(db):
    db.add(Contract(session_id=SID, contract_id="k1", proposer_id="a0",
                    counterparty_id="a1",
                    terms={"deliver": {"good": "tech", "qty": 2}, "pay": 1.0},
                    created_turn=1, deadline_turn=7, status="open"))
    await db.commit()

    own = render_world_brief(await _world_state(db, SID, 2), "a0")
    assert "OPEN CONTRACTS:" in own
    assert "k1" in own and "2 tech" in own
    assert "<-- yours" in own

    other = render_world_brief(await _world_state(db, SID, 2), "a1")
    assert "k1" in other
    assert "<-- yours" not in other


@pytest.mark.asyncio
async def test_a_resolved_contract_leaves_the_open_list(db):
    db.add(Contract(session_id=SID, contract_id="k1", proposer_id="a0",
                    counterparty_id="a1", terms={"deliver": {"good": "ore", "qty": 1},
                                                 "pay": 0.5},
                    created_turn=1, deadline_turn=7, status="fulfilled",
                    resolved_turn=3))
    await db.commit()

    brief = render_world_brief(await _world_state(db, SID, 4), "a0")
    assert "OPEN CONTRACTS:" not in brief


@pytest.mark.asyncio
async def test_a_world_without_registries_shows_no_sections(db):
    brief = render_world_brief(await _world_state(db, SID, 1), "a0")
    assert "OPEN CONTRACTS:" not in brief
    assert "OFFICES:" not in brief


async def test_world_records_carry_the_registries_in_force_at_that_turn():
    """A contract resolved later was still in force earlier.

    Reading current status would show a replay a world the agents never faced.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, SID, _roster(), seed=9)
        agents = build_agents(roster=_roster())
        for turn in range(1, 5):
            await run_turn(session, session_id=SID, turn=turn, agents=agents, seed=9)

        session.add(Contract(
            session_id=SID, contract_id="k9", proposer_id="a0", counterparty_id="a1",
            terms={"deliver": {"good": "tech", "qty": 1}, "pay": 1.0},
            created_turn=2, deadline_turn=9, status="fulfilled", resolved_turn=4,
        ))
        session.add(Office(session_id=SID, office="arbiter", holder_id="a2",
                           since_turn=1))
        await session.commit()

        _, _, world = await export_session(session, SID, seed=9)
    await engine.dispose()

    by_turn = {w.turn: w for w in world}
    assert "k9" in {c["contract_id"] for c in by_turn[3].contracts}, (
        "a contract open at turn 3 must appear in that turn's world record"
    )
    assert "k9" not in {c["contract_id"] for c in by_turn[4].contracts}, (
        "it resolved at turn 4, so it is no longer open there"
    )
    assert "k9" not in {c["contract_id"] for c in by_turn[1].contracts}, (
        "it did not exist at turn 1"
    )
    assert by_turn[3].offices["arbiter"] == "a2"


@pytest.mark.asyncio
async def test_registry_visibility_is_session_scoped(db):
    db.add(Office(session_id="other", office="auditor", holder_id="ghost",
                  since_turn=1))
    db.add(Agent(session_id="other", agent_id="ghost", display_name="G",
                 provider="stub", model="", personality="x", sprite="blue",
                 balance=1.0, alive=True, allies=[], enemies=[], inventory={}))
    await db.commit()

    brief = render_world_brief(await _world_state(db, SID, 2), "a0")
    assert "ghost" not in brief
