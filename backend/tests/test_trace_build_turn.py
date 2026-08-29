"""`build_turn` must be the only place a turn becomes trace records.

`export_session` and the live per-turn writer both go through it, so these
tests pin the two together: whatever the whole-session export says about turn
N, the single-turn builder must say exactly the same thing. A second mapping
that drifts is the `steal_count` defect again, and it fails silently.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.deferred import DeferredAction
from app.models.ledger import ThoughtLog, TurnSnapshot
from app.models.registry import Contract, Office
from app.oracle.engine import run_turn, seed_roster
from app.trace.adapters.darwin_db import build_turn, export_session

SID = "buildturn"
TURNS = 6


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


async def _run(session_id: str) -> tuple[AsyncSession, dict]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = Session()
    await seed_roster(session, session_id, _roster(), seed=7)
    agents = build_agents(roster=_roster())
    for turn in range(1, TURNS + 1):
        await run_turn(session, session_id=session_id, turn=turn, agents=agents, seed=7)
    return session, agents


async def _rows(session: AsyncSession, session_id: str) -> dict:
    async def all_of(stmt):
        return (await session.execute(stmt)).scalars().all()

    return {
        "thoughts": await all_of(
            select(ThoughtLog)
            .where(ThoughtLog.session_id == session_id)
            .order_by(ThoughtLog.turn, ThoughtLog.id)
        ),
        "snapshots": await all_of(
            select(TurnSnapshot).where(TurnSnapshot.session_id == session_id)
        ),
        "deferred": await all_of(
            select(DeferredAction).where(DeferredAction.session_id == session_id)
        ),
        "contracts": await all_of(
            select(Contract).where(Contract.session_id == session_id)
        ),
        "offices": await all_of(select(Office).where(Office.session_id == session_id)),
    }


async def test_build_turn_matches_export_session_for_every_turn():
    session, _ = await _run(SID)
    async with session:
        _manifest, turns, world = await export_session(session, SID, seed=7)
        rows = await _rows(session, SID)

    assert turns and world

    for record in world:
        expected_turns = [t for t in turns if t.turn == record.turn]
        got_turns, got_world = build_turn(record.turn, **rows)
        assert [t.model_dump() for t in got_turns] == [
            t.model_dump() for t in expected_turns
        ]
        assert got_world.model_dump() == record.model_dump()


async def test_build_turn_is_empty_for_a_turn_that_never_ran():
    session, _ = await _run(SID + "2")
    async with session:
        rows = await _rows(session, SID + "2")

    records, world = build_turn(TURNS + 99, **rows)
    assert records == []
    assert world.turn == TURNS + 99
