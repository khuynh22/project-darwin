"""Offline re-execution: a recorded run reproduces through the real engine."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.factory import build_agents
from app.config import ENV_VERSION
from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.oracle.engine import run_turn, seed_roster
from app.replay.cache import CacheMiss, ResponseCache
from app.replay.cached_agent import CachedAgent
from app.replay.reexecute import reexecute
from app.trace.adapters.darwin_db import export_session
from app.trace.io import TraceWriter

TURNS = 6


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


async def _record(tmp_path):
    """Run once with a permissive cache and write the trace."""
    factory, engine = await _factory()
    cache = ResponseCache(tmp_path / "responses", env_version=ENV_VERSION)
    live = build_agents(roster=_roster())
    agents = {
        aid: CachedAgent(aid, cache=cache, inner=inner, mode="permissive",
                         model="stub/model", prompt_version="v3")
        for aid, inner in live.items()
    }
    async with factory() as session:
        await seed_roster(session, "rec", _roster(), seed=13)
        for turn in range(1, TURNS + 1):
            await run_turn(session, session_id="rec", turn=turn, agents=agents, seed=13)
        manifest, records, _ = await export_session(session, "rec", seed=13)
    await engine.dispose()

    trace = tmp_path / "trace.jsonl"
    with TraceWriter(trace, manifest) as w:
        for record in records:
            w.append(record)
    return trace, tmp_path / "responses"


async def test_a_recorded_run_reexecutes_with_no_misses(tmp_path):
    trace, cache_root = await _record(tmp_path)
    factory, engine = await _factory()
    report = await reexecute(trace, cache_root, factory, mode="strict")
    await engine.dispose()

    assert report.error == "", report.error
    assert report.cache_misses == 0
    assert report.cache_hits > 0
    assert report.divergences == [], [str(d) for d in report.divergences]
    assert report.ok is True


async def test_a_deleted_cache_entry_fails_loudly(tmp_path):
    """Silence here would let a reproduction quietly become a fresh run.

    The engine deliberately survives an agent raising -- one provider outage
    must not kill a live turn -- so a CacheMiss never reaches the caller. The
    miss counter is therefore the signal, not an exception.
    """
    trace, cache_root = await _record(tmp_path)
    victim = next(cache_root.rglob("*.json"))
    victim.unlink()

    factory, engine = await _factory()
    report = await reexecute(trace, cache_root, factory, mode="strict")
    await engine.dispose()

    assert report.cache_misses > 0
    assert report.ok is False


async def test_a_mismatched_env_version_refuses_to_run(tmp_path):
    """A mechanic change alters every prompt; a stale hit would mix environments."""
    trace, cache_root = await _record(tmp_path)
    raw = json.loads(trace.read_text(encoding="utf-8").splitlines()[0])
    raw["env"]["version"] = "darwin-99.0"
    lines = trace.read_text(encoding="utf-8").splitlines()
    lines[0] = json.dumps(raw)
    trace.write_text("\n".join(lines) + "\n", encoding="utf-8")

    factory, engine = await _factory()
    report = await reexecute(trace, cache_root, factory, mode="strict")
    await engine.dispose()

    assert report.ok is False
    assert "EnvVersionMismatch" in report.error
    assert report.turns == 0, "must refuse before executing, not discover it mid-run"


async def test_exported_traces_carry_the_env_version(tmp_path):
    trace, _ = await _record(tmp_path)
    manifest = json.loads(trace.read_text(encoding="utf-8").splitlines()[0])
    assert manifest["env"]["version"] == ENV_VERSION


def test_cli_reexecute_reports_and_exits_zero(tmp_path, capsys, monkeypatch):
    import asyncio

    from app.cli.main import main

    trace, cache_root = asyncio.run(_record_sync(tmp_path))
    assert main(["replay", str(trace), "--from-cache", str(cache_root)]) == 0
    printed = capsys.readouterr().out
    assert "re-executed" in printed
    assert "0 divergences" in printed


async def _record_sync(tmp_path):
    return await _record(tmp_path)


@pytest.mark.parametrize("mode", ["strict", "permissive"])
def test_mode_is_accepted_by_the_parser(mode):
    from app.cli.main import build_parser

    args = build_parser().parse_args(
        ["replay", "t.jsonl", "--from-cache", "c", "--mode", mode]
    )
    assert args.mode == mode
    assert args.from_cache == "c"


def test_cache_miss_is_importable_from_the_replay_package():
    assert issubclass(CacheMiss, Exception)


async def test_a_miss_alone_fails_even_without_a_visible_divergence(tmp_path):
    """The engine's fallback can coincide with the recorded action.

    Absence of divergence therefore does not prove the cache served the run,
    which is why ok requires zero misses independently.
    """
    trace, cache_root = await _record(tmp_path)
    for path in cache_root.rglob("*.json"):
        path.unlink()

    factory, engine = await _factory()
    report = await reexecute(trace, cache_root, factory, mode="strict")
    await engine.dispose()

    assert report.cache_misses > 0
    assert report.ok is False
