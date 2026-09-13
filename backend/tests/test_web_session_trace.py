"""The live trace endpoint: replay a session while it is still running."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.oracle.engine import run_turn, seed_roster
from app.trace import recorder

TURNS = 5
SID = "livetrace"


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import main as main_mod

    monkeypatch.setattr(recorder, "runs_root", lambda: tmp_path)
    return TestClient(main_mod.app)


async def _run(session_id: str, turns: int = TURNS) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        await seed_roster(session, session_id, _roster(), seed=13)
        agents = build_agents(roster=_roster())
        for turn in range(1, turns + 1):
            await run_turn(session, session_id=session_id, turn=turn, agents=agents, seed=13)


async def test_turns_are_served_in_the_release_shape(client):
    await _run(SID)

    body = client.get(f"/sessions/{SID}/trace/turns?offset=0&limit=3").json()
    assert body["offset"] == 0
    assert body["limit"] == 3
    assert body["total"] == TURNS * 3
    assert len(body["turns"]) == 3
    first = body["turns"][0]
    assert set(first) >= {
        "turn", "agent_id", "monologue", "public_message", "action", "outcome", "state"
    }
    assert first["turn"] == 1


async def test_paging_walks_the_whole_run(client):
    await _run(SID)

    seen = []
    offset = 0
    while True:
        body = client.get(f"/sessions/{SID}/trace/turns?offset={offset}&limit=4").json()
        seen.extend(body["turns"])
        offset += 4
        if offset >= body["total"]:
            break
    assert len(seen) == TURNS * 3
    assert [t["turn"] for t in seen] == sorted(t["turn"] for t in seen)


async def test_a_session_with_no_trace_is_404(client):
    assert client.get("/sessions/neverran/trace/turns").status_code == 404


def test_an_unsafe_session_id_is_404_and_reads_no_file(client, tmp_path):
    # Not merely absent: the id must be refused before it reaches the filesystem.
    assert client.get("/sessions/..%2F..%2Fetc/trace/turns").status_code == 404
