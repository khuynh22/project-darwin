"""A session run from the UI must leave a replayable trace on disk.

The turn loop is the only mutation path in the system, so these tests pin the
two properties that make writing from inside it safe: the file is parseable
after every turn (a killed process must not produce a broken artifact), and a
write that fails cannot fail a turn that already committed.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.oracle.engine import run_turn, seed_roster
from app.trace import recorder
from app.trace.adapters.darwin_db import export_session
from app.trace.io import read_trace
from app.trace.validate import validate_trace

TURNS = 4


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)()


async def _run(session, session_id: str, turns: int = TURNS) -> None:
    await seed_roster(session, session_id, _roster(), seed=11)
    agents = build_agents(roster=_roster())
    for turn in range(1, turns + 1):
        await run_turn(session, session_id=session_id, turn=turn, agents=agents, seed=11)


async def test_turn_loop_writes_a_valid_trace_for_every_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder, "runs_root", lambda: tmp_path)
    session = await _session()
    async with session:
        await _run(session, "writeme")
        _manifest, expected, _world = await export_session(session, "writeme", seed=11)

    path = tmp_path / "writeme" / "trace.jsonl"
    report = validate_trace(path)
    assert report.ok, report.errors

    _got_manifest, got = read_trace(path)
    assert [t.model_dump() for t in got] == [t.model_dump() for t in expected]


async def test_trace_is_parseable_after_each_turn_not_only_at_the_end(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(recorder, "runs_root", lambda: tmp_path)
    session = await _session()
    path = tmp_path / "midrun" / "trace.jsonl"

    async with session:
        await seed_roster(session, "midrun", _roster(), seed=11)
        agents = build_agents(roster=_roster())
        for turn in range(1, TURNS + 1):
            await run_turn(session, session_id="midrun", turn=turn, agents=agents, seed=11)
            report = validate_trace(path)
            assert report.ok, f"turn {turn}: {report.errors}"
            _m, turns = read_trace(path)
            assert {t.turn for t in turns} == set(range(1, turn + 1))


@pytest.mark.parametrize("session_id", ["../escape", "a/b", "with space", "x" * 33])
async def test_a_session_id_that_is_not_a_safe_directory_name_writes_nothing(
    tmp_path, monkeypatch, session_id
):
    monkeypatch.setattr(recorder, "runs_root", lambda: tmp_path)
    session = await _session()
    async with session:
        await _run(session, session_id, turns=1)

    assert list(tmp_path.rglob("trace.jsonl")) == []


async def test_a_failing_trace_write_does_not_fail_the_turn(tmp_path, monkeypatch):
    blocked = tmp_path / "not-a-dir"
    blocked.write_text("this is a file, so mkdir underneath it must fail")
    monkeypatch.setattr(recorder, "runs_root", lambda: blocked)

    session = await _session()
    async with session:
        await _run(session, "resilient", turns=2)
        _manifest, turns, _world = await export_session(session, "resilient", seed=11)

    assert turns, "the turns must have run and committed despite the write failing"


def test_read_events_returns_v6_rows_and_ignores_turn_traces(tmp_path):
    """A v6 trace is unreadable through `read_turns`, which drops event records
    silently -- so the events path has to exist and be exercised."""
    import json

    from app.releases import read_events

    run = tmp_path / "evt"
    run.mkdir()
    manifest = {
        "kind": "run",
        "schema_version": 6,
        "run_id": "evt",
        "env": {"name": "darwin"},
        "horizon": 10,
        "agents": [],
    }
    rows = [manifest] + [
        {
            "kind": "event",
            "event_id": i,
            "tick": i * 1000,
            "agent_seq": i,
            "agent_id": "red",
            "action": "work",
            "venue": "work",
            "travel_ticks": 500,
        }
        for i in range(1, 4)
    ]
    (run / "trace.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    events, total = read_events(tmp_path, "evt", offset=0, limit=50)
    assert total == 3
    assert [e.event_id for e in events] == [1, 2, 3]
    assert [e.tick for e in events] == [1000, 2000, 3000]
    assert events[0].travel_ticks == 500
    # agent_seq, never event_id, is what a coherence reader must see as "turn".
    assert [e.turn for e in events] == [1, 2, 3]


def test_read_events_is_empty_for_a_missing_run(tmp_path):
    from app.releases import read_events

    assert read_events(tmp_path, "nope") == ([], 0)
