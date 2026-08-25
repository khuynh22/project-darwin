from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.oracle.engine import run_turn, seed_roster
from app.trace.adapters.darwin_db import export_session

SID = "dbexport"


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


async def test_export_session_produces_valid_manifest_and_turns():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, SID, _roster(), seed=3)
        agents = build_agents(roster=_roster())
        for turn in range(1, 4):
            await run_turn(session, session_id=SID, turn=turn, agents=agents, seed=3)

        manifest, turns, _world = await export_session(session, SID, run_id="r", seed=3)

    assert manifest.schema_version == 5
    assert manifest.state_fidelity == "full"
    assert manifest.horizon == 3
    assert set(manifest.lifespans()) == {"a0", "a1", "a2"}
    assert manifest.models()["a0"] == "stub/model"
    assert turns
    assert all(t.state.balance is not None for t in turns)
    assert all(t.state.inventory is not None for t in turns)
    # v5: the fields whose absence silently fabricated a different world.
    assert all(t.state.steal_count is not None for t in turns)
    assert all(t.state.allies is not None for t in turns)
    assert all(t.state.share_balance is not None for t in turns)
    assert _world and [w.turn for w in _world] == sorted({t.turn for t in turns})


async def test_exported_trace_validates(tmp_path):
    from app.trace.io import TraceWriter
    from app.trace.validate import validate_trace

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        await seed_roster(session, "dbexport2", _roster(), seed=5)
        agents = build_agents(roster=_roster())
        for turn in range(1, 6):
            await run_turn(session, session_id="dbexport2", turn=turn, agents=agents, seed=5)
        manifest, turns, _world = await export_session(session, "dbexport2", seed=5)

    path = tmp_path / "run.jsonl"
    with TraceWriter(path, manifest) as w:
        for record in turns:
            w.append(record)

    report = validate_trace(path)
    assert report.ok, report.errors
    assert report.n_turns == len(turns)
