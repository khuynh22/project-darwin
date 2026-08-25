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


async def test_snapshot_captures_every_mechanically_relevant_field():
    """A field absent here is a field a restored probe silently fabricates."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, "capture", _roster(), seed=7)
        agents = build_agents(roster=_roster())
        for turn in range(1, 6):
            await run_turn(session, session_id="capture", turn=turn, agents=agents, seed=7)
        rows = (await session.execute(
            select(TurnSnapshot).where(TurnSnapshot.session_id == "capture")
        )).scalars().all()
    await engine.dispose()

    required = {
        "balance", "trust_score", "alive", "inventory", "spouse_id",
        "steal_count", "allies", "enemies", "skip_next_turn", "rest_bonus",
        "will_target", "share_balance", "extortion_pending", "bribe_pending",
        "marriage_pending",
    }
    missing = required - set(TurnSnapshot.__table__.columns.keys())
    assert not missing, f"turn_snapshots is missing {sorted(missing)}"
    assert rows
    assert all(isinstance(r.allies, list) for r in rows)
    assert all(isinstance(r.steal_count, int) for r in rows)


def test_every_new_snapshot_column_has_a_migration_row():
    """Adding a column without a _MIGRATIONS row leaves existing databases behind."""
    import inspect

    from app import db as db_mod

    # Columns the table shipped with: create_all builds them, so no ALTER
    # backfill applies. Everything added later needs a _MIGRATIONS row or
    # existing databases silently never gain it.
    ORIGINAL = {
        "id", "session_id", "turn", "agent_id", "created_at",
        "balance", "trust_score", "alive",
    }
    source = inspect.getsource(db_mod.init_db)
    for column in TurnSnapshot.__table__.columns.keys():
        if column in ORIGINAL:
            continue
        assert f'"turn_snapshots", "{column}"' in source, (
            f"turn_snapshots.{column} has no _MIGRATIONS row"
        )
