import json

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.sweep.runner import cell_manifest_path, run_sweep
from app.sweep.spec import ExperimentSpec


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


def _spec(**over) -> ExperimentSpec:
    base = {
        "experiment": "swp", "roster": "unused.json",
        "conditions": ["neutral", "honesty"], "seeds": {"start": 1, "count": 2},
        "turns": 4, "out": "unused", "concurrency": 2,
    }
    base.update(over)
    return ExperimentSpec.model_validate(base)


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


async def test_sweep_runs_every_cell(tmp_path):
    factory, engine = await _factory()
    report = await run_sweep(_spec(), session_factory=factory, roster=_roster(),
                             out_dir=tmp_path)
    await engine.dispose()

    assert len(report.completed) == 4
    assert report.failed == []
    assert all(cell_manifest_path(tmp_path, c).exists() for c in _spec().cells())


async def test_resume_skips_completed_cells(tmp_path):
    factory, engine = await _factory()
    await run_sweep(_spec(), session_factory=factory, roster=_roster(), out_dir=tmp_path)
    second = await run_sweep(_spec(), session_factory=factory, roster=_roster(),
                             out_dir=tmp_path)
    await engine.dispose()

    assert len(second.skipped) == 4
    assert second.completed == []


async def test_no_resume_reruns_everything(tmp_path):
    factory, engine = await _factory()
    await run_sweep(_spec(), session_factory=factory, roster=_roster(), out_dir=tmp_path)
    second = await run_sweep(_spec(), session_factory=factory, roster=_roster(),
                             out_dir=tmp_path, resume=False)
    await engine.dispose()

    assert second.skipped == []
    assert len(second.completed) == 4


async def test_resume_reruns_a_cell_whose_manifest_says_failed(tmp_path):
    factory, engine = await _factory()
    await run_sweep(_spec(), session_factory=factory, roster=_roster(), out_dir=tmp_path)

    victim = _spec().cells()[0]
    path = cell_manifest_path(tmp_path, victim)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["ok"] = False
    path.write_text(json.dumps(data), encoding="utf-8")

    second = await run_sweep(_spec(), session_factory=factory, roster=_roster(),
                             out_dir=tmp_path)
    await engine.dispose()
    assert len(second.completed) == 1
    assert len(second.skipped) == 3


async def test_a_corrupt_manifest_is_treated_as_incomplete(tmp_path):
    factory, engine = await _factory()
    await run_sweep(_spec(), session_factory=factory, roster=_roster(), out_dir=tmp_path)

    victim = _spec().cells()[0]
    cell_manifest_path(tmp_path, victim).write_text("{not json", encoding="utf-8")

    second = await run_sweep(_spec(), session_factory=factory, roster=_roster(),
                             out_dir=tmp_path)
    await engine.dispose()
    assert len(second.completed) == 1


async def test_budget_stops_the_sweep_cleanly(tmp_path):
    factory, engine = await _factory()
    calls = {"n": 0}

    def counter() -> int:
        calls["n"] += 1
        return calls["n"]

    spec = _spec(budget={"max_calls": 2})
    report = await run_sweep(spec, session_factory=factory, roster=_roster(),
                             out_dir=tmp_path, call_counter=counter)
    await engine.dispose()

    assert report.stopped_for_budget is True
    assert len(report.completed) < 4
    for result in report.completed:
        assert cell_manifest_path(tmp_path, result.cell).exists()


async def test_a_budget_stopped_sweep_resumes(tmp_path):
    """The point of stopping cleanly is that the rest can be picked up later."""
    factory, engine = await _factory()
    calls = {"n": 0}

    def counter() -> int:
        calls["n"] += 1
        return calls["n"]

    first = await run_sweep(_spec(budget={"max_calls": 2}), session_factory=factory,
                            roster=_roster(), out_dir=tmp_path, call_counter=counter)
    second = await run_sweep(_spec(), session_factory=factory, roster=_roster(),
                             out_dir=tmp_path)
    await engine.dispose()

    assert len(first.completed) + len(second.completed) == 4
    assert len(second.skipped) == len(first.completed)


async def test_manifest_records_both_identities(tmp_path):
    factory, engine = await _factory()
    await run_sweep(_spec(), session_factory=factory, roster=_roster(), out_dir=tmp_path)
    await engine.dispose()

    cell = _spec().cells()[0]
    data = json.loads(cell_manifest_path(tmp_path, cell).read_text(encoding="utf-8"))
    assert data["session_id"] == cell.session_id
    assert data["natural_id"] == cell.natural_id
    assert data["ok"] is True


async def test_sqlite_is_forced_serial(tmp_path):
    """Concurrent commits on SQLite lose a cell; the clamp must be automatic."""
    factory, engine = await _factory()
    report = await run_sweep(_spec(concurrency=4), session_factory=factory,
                             roster=_roster(), out_dir=tmp_path)
    await engine.dispose()

    assert report.effective_concurrency == 1
    assert len(report.completed) == 4
