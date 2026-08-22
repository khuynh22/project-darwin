from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.sweep.cell import run_cell
from app.sweep.spec import Cell
from app.trace.io import read_trace
from app.trace.validate import validate_trace


def _roster() -> list[dict]:
    return [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]


def _cell(seed: int = 1) -> Cell:
    return Cell(condition="neutral", seed=seed, session_id=f"t:neu:{seed}",
                natural_id=f"t:neutral:{seed}", trace_name=f"neutral-s{seed}")


async def _factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


async def test_run_cell_writes_a_valid_trace(tmp_path):
    factory, engine = await _factory()
    result = await run_cell(factory, _cell(), roster=_roster(), turns=6, out_dir=tmp_path)
    await engine.dispose()

    assert result.ok, result.error
    assert result.trace_path.exists()
    report = validate_trace(result.trace_path)
    assert report.ok, report.errors
    assert report.n_turns > 0


async def test_trace_manifest_carries_the_cell_identity(tmp_path):
    factory, engine = await _factory()
    result = await run_cell(factory, _cell(seed=4), roster=_roster(), turns=4, out_dir=tmp_path)
    await engine.dispose()

    manifest, _ = read_trace(result.trace_path)
    assert manifest.condition == "neutral"
    assert manifest.env.seed == 4
    assert manifest.run_id == "t:neutral:4"


async def test_two_cells_coexist_in_one_database(tmp_path):
    factory, engine = await _factory()
    first = await run_cell(factory, _cell(seed=1), roster=_roster(), turns=4, out_dir=tmp_path)
    second = await run_cell(factory, _cell(seed=2), roster=_roster(), turns=4, out_dir=tmp_path)
    await engine.dispose()

    assert first.ok and second.ok
    assert first.trace_path != second.trace_path
    assert validate_trace(first.trace_path).ok
    assert validate_trace(second.trace_path).ok


async def test_same_seed_reproduces_the_same_trace(tmp_path):
    """Determinism is the whole basis for comparing cells."""

    def _sig(path):
        _, turns = read_trace(path)
        return [(t.turn, t.agent_id, t.action, t.outcome) for t in turns]

    factory_a, engine_a = await _factory()
    a = await run_cell(factory_a, _cell(seed=9), roster=_roster(), turns=6,
                       out_dir=tmp_path / "a")
    await engine_a.dispose()

    factory_b, engine_b = await _factory()
    b = await run_cell(factory_b, _cell(seed=9), roster=_roster(), turns=6,
                       out_dir=tmp_path / "b")
    await engine_b.dispose()

    assert _sig(a.trace_path) == _sig(b.trace_path)


async def test_different_seeds_diverge(tmp_path):
    def _sig(path):
        _, turns = read_trace(path)
        return [(t.turn, t.agent_id, t.action, t.outcome) for t in turns]

    factory, engine = await _factory()
    a = await run_cell(factory, _cell(seed=1), roster=_roster(), turns=8, out_dir=tmp_path)
    b = await run_cell(factory, _cell(seed=2), roster=_roster(), turns=8, out_dir=tmp_path)
    await engine.dispose()

    assert _sig(a.trace_path) != _sig(b.trace_path)


async def test_a_broken_cell_reports_instead_of_raising(tmp_path):
    """One bad cell must not abort a 60-cell sweep."""
    factory, engine = await _factory()
    bad_roster = [{"agent_id": "a0"}]  # missing required roster fields
    result = await run_cell(factory, _cell(), roster=bad_roster, turns=2, out_dir=tmp_path)
    await engine.dispose()

    assert result.ok is False
    assert result.error
