from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.ledger import TurnSnapshot
from app.oracle.engine import run_turn, seed_roster

SID = "snapstate"


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": ""}
        for i in range(3)
    ]


async def test_snapshot_records_inventory_and_spouse():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, SID, _roster(), seed=1)
        agents = build_agents(roster=_roster())
        for turn in range(1, 4):
            await run_turn(session, session_id=SID, turn=turn, agents=agents, seed=1)

        rows = (
            await session.execute(select(TurnSnapshot).where(TurnSnapshot.session_id == SID))
        ).scalars().all()

    assert rows, "engine wrote no snapshots"
    assert all(isinstance(r.inventory, dict) for r in rows)
    assert all(set(r.inventory) == {"ore", "food", "tech"} for r in rows)
    assert all(hasattr(r, "spouse_id") for r in rows)
