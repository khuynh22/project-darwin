# Sweep Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a grid of arena cells (roster × condition × seed) from one command, writing a validated v4 trace per cell, resumable after interruption and capped by a spend budget.

**Architecture:** An experiment spec names the roster, the conditions, the seeds, and the budget. The sweep derives one `session_id` per cell and runs cells with bounded concurrency against a single database, relying on the existing multi-tenancy (composite PK by `session_id`) so cells never collide. Each cell writes `<out>/<cell>.jsonl` plus a cell manifest; a completed manifest is the resume marker.

**Tech Stack:** Python 3.12, Pydantic v2, SQLAlchemy 2 async, `asyncio.Semaphore` for concurrency, argparse for the CLI.

**Spec:** `docs/superpowers/specs/2026-08-22-darwin-benchmark-harness-design.md` §5

**Status:** COMPLETE (2026-08-22). All five tasks landed; 163 backend tests pass, ruff clean. See `## Execution notes`.

**Depends on:** `docs/superpowers/plans/2026-08-22-harness-foundation.md` (complete) — specifically `app.trace.io.TraceWriter`, `app.trace.adapters.darwin_db.export_session`, and `app.trace.validate.validate_trace`.

## Global Constraints

- `session_id` is `varchar(32)`. Every derived id is asserted `<= 32` characters **before the first cell runs**, never at insert time.
- Experiment specs are **JSON**, not YAML. The repo has no yaml dependency and already uses JSON for rosters (`research/*/roster*.json`); the spec document's YAML was illustrative.
- A cell that fails must not abort the sweep. It is recorded as failed and the remaining cells continue.
- Resume is by cell manifest. A partial cell re-runs from scratch — the arena has no mid-run checkpoint, and pretending otherwise would splice two different RNG streams.
- Tests run offline with `provider="stub"`. No test may require `OPENROUTER_API_KEY` or a running Postgres.
- Money is `round(x, 2)`.

---

### Task 1: Experiment spec and cell derivation

**Files:**
- Create: `backend/app/sweep/__init__.py`
- Create: `backend/app/sweep/spec.py`
- Test: `backend/tests/test_sweep_spec.py`

**Interfaces:**
- Produces: `ExperimentSpec`, `Cell`, `SeedRange`, `Budget`, `load_spec(path: Path) -> ExperimentSpec`, and `ExperimentSpec.cells() -> list[Cell]`. `Cell` carries `condition: str`, `seed: int`, `session_id: str`, `natural_id: str`, `trace_name: str`.

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_sweep_spec.py
import json

import pytest
from pydantic import ValidationError

from app.sweep.spec import MAX_SESSION_ID, ExperimentSpec, load_spec


def _spec(**over) -> dict:
    base = {
        "experiment": "cond-contrast",
        "roster": "rosters/cheap8.json",
        "conditions": ["neutral", "honesty"],
        "seeds": {"start": 1, "count": 3},
        "turns": 20,
        "out": "runs/cond-contrast",
    }
    base.update(over)
    return base


def test_cells_are_the_condition_seed_product():
    spec = ExperimentSpec.model_validate(_spec())
    cells = spec.cells()
    assert len(cells) == 6
    assert {c.condition for c in cells} == {"neutral", "honesty"}
    assert sorted({c.seed for c in cells}) == [1, 2, 3]


def test_explicit_seed_list_is_honoured():
    spec = ExperimentSpec.model_validate(_spec(seeds=[7, 9]))
    assert sorted({c.seed for c in spec.cells()}) == [7, 9]


def test_session_ids_are_unique_and_within_the_column_limit():
    spec = ExperimentSpec.model_validate(_spec())
    ids = [c.session_id for c in spec.cells()]
    assert len(set(ids)) == len(ids)
    assert all(len(i) <= MAX_SESSION_ID for i in ids)


def test_long_experiment_name_still_fits():
    spec = ExperimentSpec.model_validate(
        _spec(experiment="a-very-long-experiment-name-indeed-2026", seeds=[123456])
    )
    for cell in spec.cells():
        assert len(cell.session_id) <= MAX_SESSION_ID
        assert cell.natural_id.startswith("a-very-long-experiment-name")


def test_unknown_condition_rejected():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(_spec(conditions=["neutral", "nonsense"]))


def test_zero_seeds_rejected():
    with pytest.raises(ValidationError):
        ExperimentSpec.model_validate(_spec(seeds={"start": 1, "count": 0}))


def test_trace_names_are_filesystem_safe_and_unique():
    spec = ExperimentSpec.model_validate(_spec())
    names = [c.trace_name for c in spec.cells()]
    assert len(set(names)) == len(names)
    assert all(":" not in n for n in names)


def test_load_spec_reads_json(tmp_path):
    path = tmp_path / "exp.json"
    path.write_text(json.dumps(_spec()), encoding="utf-8")
    spec = load_spec(path)
    assert spec.experiment == "cond-contrast"
    assert spec.turns == 20
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sweep_spec.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.sweep'`

- [x] **Step 3: Write minimal implementation**

```python
# backend/app/sweep/__init__.py
"""Batch execution of arena cells from an experiment spec."""
```

```python
# backend/app/sweep/spec.py
"""Experiment spec: the grid of cells a sweep runs.

JSON rather than YAML -- the repo has no yaml dependency and already uses JSON
for rosters. One cell is one (condition, seed) pair.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ``Agent.session_id`` and every scoped table are VARCHAR(32). A derived id that
# overflows would fail at insert time partway into a sweep, so it is checked
# before the first cell runs.
MAX_SESSION_ID = 32

Condition = Literal["neutral", "honesty", "deception"]


class SeedRange(BaseModel):
    start: int = 1
    count: int = Field(ge=1)

    def values(self) -> list[int]:
        return list(range(self.start, self.start + self.count))


class Budget(BaseModel):
    max_usd: float | None = None
    max_calls: int | None = None


class Cell(BaseModel):
    condition: str
    seed: int
    session_id: str
    natural_id: str
    trace_name: str


class ExperimentSpec(BaseModel):
    experiment: str = Field(min_length=1, max_length=64)
    roster: str
    conditions: list[Condition] = Field(min_length=1)
    seeds: SeedRange | list[int]
    turns: int = Field(ge=1)
    out: str
    concurrency: int = Field(default=2, ge=1)
    budget: Budget = Field(default_factory=Budget)

    @field_validator("seeds")
    @classmethod
    def _non_empty_seeds(cls, v: SeedRange | list[int]) -> SeedRange | list[int]:
        if isinstance(v, list) and not v:
            raise ValueError("seeds must not be empty")
        return v

    @model_validator(mode="after")
    def _ids_fit_the_column(self) -> ExperimentSpec:
        for cell in self.cells():
            if len(cell.session_id) > MAX_SESSION_ID:
                raise ValueError(
                    f"derived session_id {cell.session_id!r} exceeds {MAX_SESSION_ID} chars"
                )
        return self

    def seed_values(self) -> list[int]:
        return self.seeds.values() if isinstance(self.seeds, SeedRange) else list(self.seeds)

    def cells(self) -> list[Cell]:
        out: list[Cell] = []
        for condition in self.conditions:
            for seed in self.seed_values():
                natural = f"{self.experiment}:{condition}:{seed}"
                out.append(
                    Cell(
                        condition=condition,
                        seed=seed,
                        session_id=_derive_session_id(self.experiment, condition, seed),
                        natural_id=natural,
                        trace_name=f"{condition}-s{seed}",
                    )
                )
        return out


def _derive_session_id(experiment: str, condition: str, seed: int) -> str:
    """Short, unique, and inside VARCHAR(32).

    Prefer a readable id; fall back to a hash of the natural id when the
    readable form would overflow, so a long experiment name degrades to
    something opaque rather than to a runtime failure.
    """
    short = f"{experiment[:12]}:{condition[:3]}:{seed}"
    if len(short) <= MAX_SESSION_ID:
        return short
    natural = f"{experiment}:{condition}:{seed}"
    digest = hashlib.sha1(natural.encode("utf-8")).hexdigest()[:12]
    return f"x{digest}:{seed}"[:MAX_SESSION_ID]


def load_spec(path: Path) -> ExperimentSpec:
    return ExperimentSpec.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sweep_spec.py -v`
Expected: PASS (8 tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/sweep backend/tests/test_sweep_spec.py
git commit -m "feat(sweep): experiment spec and cell derivation"
```

---

### Task 2: Run one cell to a trace

**Files:**
- Create: `backend/app/sweep/cell.py`
- Test: `backend/tests/test_sweep_cell.py`

**Interfaces:**
- Consumes: `app.sweep.spec.Cell`, `app.oracle.engine.{run_turn, seed_roster}`, `app.agents.factory.build_agents`, `app.trace.adapters.darwin_db.export_session`, `app.trace.io.TraceWriter`.
- Produces: `CellResult` (dataclass: `cell`, `ok`, `turns_run`, `trace_path`, `error`, `eliminated`, `apex`) and `async def run_cell(session_factory, cell: Cell, *, roster: list[dict], turns: int, out_dir: Path) -> CellResult`.

**Why a separate module:** the cell is the unit a test can drive without any orchestration, and the unit the sweep retries. Mixing it into the orchestrator makes both untestable.

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_sweep_cell.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.sweep.cell import run_cell
from app.sweep.spec import Cell
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
    from app.trace.io import read_trace

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
    from app.trace.io import read_trace

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
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sweep_cell.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.sweep.cell'`

- [x] **Step 3: Write minimal implementation**

```python
# backend/app/sweep/cell.py
"""Run one (condition, seed) cell to a validated v4 trace."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.sweep.spec import Cell
from app.trace.adapters.darwin_db import export_session
from app.trace.io import TraceWriter

log = logging.getLogger(__name__)


@dataclass
class CellResult:
    cell: Cell
    ok: bool
    turns_run: int = 0
    trace_path: Path | None = None
    error: str = ""
    eliminated: list[str] = field(default_factory=list)
    apex: str | None = None


async def run_cell(
    session_factory: Any,
    cell: Cell,
    *,
    roster: list[dict],
    turns: int,
    out_dir: Path,
) -> CellResult:
    from app.agents.factory import build_agents
    from app.oracle.engine import run_turn, seed_roster

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / f"{cell.trace_name}.jsonl"
    eliminated: list[str] = []
    apex: str | None = None
    turns_run = 0

    try:
        async with session_factory() as session:
            await seed_roster(session, cell.session_id, roster=roster, seed=cell.seed)

        agents = build_agents(roster=roster)

        for turn in range(1, turns + 1):
            async with session_factory() as session:
                result = await run_turn(
                    session,
                    session_id=cell.session_id,
                    turn=turn,
                    agents=agents,
                    seed=cell.seed,
                    condition=cell.condition,
                )
            turns_run = turn
            if result.eliminated:
                eliminated.extend(result.eliminated)
            if result.apex_declared:
                apex = result.apex_declared
                break

        async with session_factory() as session:
            manifest, records = await export_session(
                session,
                cell.session_id,
                run_id=cell.natural_id,
                condition=cell.condition,
                seed=cell.seed,
            )
    except Exception as exc:  # noqa: BLE001 - one bad cell must not kill the sweep
        log.exception("cell %s failed", cell.natural_id)
        return CellResult(cell=cell, ok=False, turns_run=turns_run, error=repr(exc))

    with TraceWriter(trace_path, manifest) as writer:
        for record in records:
            writer.append(record)

    return CellResult(
        cell=cell,
        ok=True,
        turns_run=turns_run,
        trace_path=trace_path,
        eliminated=eliminated,
        apex=apex,
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sweep_cell.py -v`
Expected: PASS (4 tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/sweep/cell.py backend/tests/test_sweep_cell.py
git commit -m "feat(sweep): run one cell to a validated trace"
```

---

### Task 3: Sweep orchestration, resume, and budget

**Files:**
- Create: `backend/app/sweep/runner.py`
- Test: `backend/tests/test_sweep_runner.py`

**Interfaces:**
- Consumes: `app.sweep.spec.{ExperimentSpec, Cell, load_spec}`, `app.sweep.cell.{run_cell, CellResult}`.
- Produces: `SweepReport` (dataclass: `experiment`, `completed`, `failed`, `skipped`, `stopped_for_budget`) and `async def run_sweep(spec: ExperimentSpec, *, session_factory, roster, out_dir, resume=True, call_counter=None) -> SweepReport`, plus `cell_manifest_path(out_dir, cell)`.

**Resume contract:** a cell is complete when `<out>/<trace_name>.manifest.json` exists with `"ok": true`. A partial cell re-runs from scratch — the arena has no mid-run checkpoint, and resuming mid-run would splice two RNG streams.

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_sweep_runner.py
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
    # Whatever did finish is still valid and resumable.
    for result in report.completed:
        assert cell_manifest_path(tmp_path, result.cell).exists()


async def test_manifest_records_both_identities(tmp_path):
    factory, engine = await _factory()
    await run_sweep(_spec(), session_factory=factory, roster=_roster(), out_dir=tmp_path)
    await engine.dispose()

    cell = _spec().cells()[0]
    data = json.loads(cell_manifest_path(tmp_path, cell).read_text(encoding="utf-8"))
    assert data["session_id"] == cell.session_id
    assert data["natural_id"] == cell.natural_id
    assert data["ok"] is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sweep_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.sweep.runner'`

- [x] **Step 3: Write minimal implementation**

```python
# backend/app/sweep/runner.py
"""Orchestrate a grid of cells: bounded concurrency, resume, budget guard."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.sweep.cell import CellResult, run_cell
from app.sweep.spec import Cell, ExperimentSpec

log = logging.getLogger(__name__)


@dataclass
class SweepReport:
    experiment: str
    completed: list[CellResult] = field(default_factory=list)
    failed: list[CellResult] = field(default_factory=list)
    skipped: list[Cell] = field(default_factory=list)
    stopped_for_budget: bool = False


def cell_manifest_path(out_dir: Path, cell: Cell) -> Path:
    return Path(out_dir) / f"{cell.trace_name}.manifest.json"


def _is_complete(out_dir: Path, cell: Cell) -> bool:
    path = cell_manifest_path(out_dir, cell)
    if not path.exists():
        return False
    try:
        return bool(json.loads(path.read_text(encoding="utf-8")).get("ok"))
    except (json.JSONDecodeError, OSError):
        return False


def _write_manifest(out_dir: Path, result: CellResult) -> None:
    payload = {
        "ok": result.ok,
        "session_id": result.cell.session_id,
        "natural_id": result.cell.natural_id,
        "condition": result.cell.condition,
        "seed": result.cell.seed,
        "turns_run": result.turns_run,
        "trace": result.trace_path.name if result.trace_path else None,
        "eliminated": result.eliminated,
        "apex": result.apex,
        "error": result.error,
    }
    cell_manifest_path(out_dir, result.cell).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


async def run_sweep(
    spec: ExperimentSpec,
    *,
    session_factory: Any,
    roster: list[dict],
    out_dir: Path,
    resume: bool = True,
    call_counter: Callable[[], int] | None = None,
) -> SweepReport:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = SweepReport(experiment=spec.experiment)

    pending: list[Cell] = []
    for cell in spec.cells():
        if resume and _is_complete(out_dir, cell):
            report.skipped.append(cell)
        else:
            pending.append(cell)

    semaphore = asyncio.Semaphore(spec.concurrency)
    budget_hit = asyncio.Event()

    async def _one(cell: Cell) -> None:
        if budget_hit.is_set():
            return
        async with semaphore:
            if budget_hit.is_set():
                return
            if call_counter is not None and spec.budget.max_calls is not None:
                if call_counter() > spec.budget.max_calls:
                    budget_hit.set()
                    return
            result = await run_cell(
                session_factory, cell, roster=roster, turns=spec.turns, out_dir=out_dir
            )
        _write_manifest(out_dir, result)
        (report.completed if result.ok else report.failed).append(result)

    await asyncio.gather(*(_one(cell) for cell in pending))
    report.stopped_for_budget = budget_hit.is_set()
    return report
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sweep_runner.py -v`
Expected: PASS (5 tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/sweep/runner.py backend/tests/test_sweep_runner.py
git commit -m "feat(sweep): orchestration with resume and budget guard"
```

---

### Task 4: `darwin sweep`

**Files:**
- Modify: `backend/app/cli/main.py`
- Test: `backend/tests/test_cli_sweep.py`

**Interfaces:**
- Consumes: `app.sweep.{spec,runner}`.
- Produces: `darwin sweep <spec.json> [--out DIR] [--no-resume] [--dry-run]`, returning 0 when every cell completed or was skipped, 1 when any failed.

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_cli_sweep.py
import json

from app.cli.main import main


def _spec_file(tmp_path, roster_path, out_dir):
    spec = {
        "experiment": "clis", "roster": str(roster_path),
        "conditions": ["neutral"], "seeds": [1, 2], "turns": 3,
        "out": str(out_dir), "concurrency": 1,
    }
    path = tmp_path / "exp.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _roster_file(tmp_path):
    roster = [
        {"agent_id": f"a{i}", "display_name": f"A{i}", "provider": "stub",
         "personality": "x", "sprite": "blue", "model": "stub/model"}
        for i in range(3)
    ]
    path = tmp_path / "roster.json"
    path.write_text(json.dumps(roster), encoding="utf-8")
    return path


def test_dry_run_lists_cells_without_running(tmp_path, capsys):
    out = tmp_path / "runs"
    spec = _spec_file(tmp_path, _roster_file(tmp_path), out)
    assert main(["sweep", str(spec), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "clis:neutral:1" in printed
    assert "clis:neutral:2" in printed
    assert not out.exists()


def test_sweep_runs_and_validates(tmp_path, capsys):
    out = tmp_path / "runs"
    spec = _spec_file(tmp_path, _roster_file(tmp_path), out)
    assert main(["sweep", str(spec), "--out", str(out)]) == 0
    traces = sorted(out.glob("*.jsonl"))
    assert len(traces) == 2
    for trace in traces:
        assert main(["validate", str(trace)]) == 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_cli_sweep.py -v`
Expected: FAIL — argparse exits 2 for the unknown `sweep` command.

- [x] **Step 3: Write minimal implementation**

Add to `backend/app/cli/main.py`:

```python
def _cmd_sweep(args: argparse.Namespace) -> int:
    import asyncio

    from app.sweep.runner import run_sweep
    from app.sweep.spec import load_spec

    spec = load_spec(Path(args.spec))
    out_dir = Path(args.out) if args.out else Path(spec.out)

    if args.dry_run:
        for cell in spec.cells():
            print(f"{cell.natural_id}  -> session_id={cell.session_id}  "
                  f"trace={cell.trace_name}.jsonl")
        print(f"{len(spec.cells())} cells, concurrency={spec.concurrency}, "
              f"turns={spec.turns}")
        return 0

    roster = json.loads(Path(spec.roster).read_text(encoding="utf-8"))

    async def _go() -> int:
        from app.db import SessionLocal, init_db

        await init_db()
        report = await run_sweep(
            spec,
            session_factory=SessionLocal,
            roster=roster,
            out_dir=out_dir,
            resume=not args.no_resume,
        )
        print(f"[sweep] {spec.experiment}: {len(report.completed)} completed, "
              f"{len(report.skipped)} skipped, {len(report.failed)} failed")
        for failure in report.failed:
            print(f"  FAILED {failure.cell.natural_id}: {failure.error}")
        if report.stopped_for_budget:
            print("[sweep] stopped early: budget reached")
        return 1 if report.failed else 0

    return asyncio.run(_go())
```

Register it in `build_parser`:

```python
    p_sweep = sub.add_parser("sweep", help="run a grid of cells from an experiment spec")
    p_sweep.add_argument("spec")
    p_sweep.add_argument("--out", help="override the spec's out directory")
    p_sweep.add_argument("--no-resume", action="store_true",
                         help="re-run cells even if a completed manifest exists")
    p_sweep.add_argument("--dry-run", action="store_true",
                         help="list the cells and derived session ids, run nothing")
    p_sweep.set_defaults(func=_cmd_sweep)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_cli_sweep.py tests/test_cli.py -v`
Expected: PASS

Note: the sweep test writes to the conftest SQLite database rather than an in-memory one, because the CLI owns its own `SessionLocal`. That is intentional — it exercises the real path a user takes.

- [x] **Step 5: Commit**

```bash
git add backend/app/cli/main.py backend/tests/test_cli_sweep.py
git commit -m "feat(cli): darwin sweep with dry-run and resume"
```

---

### Task 5: One judge driver, and `darwin judge`

**Files:**
- Create: `backend/app/judge/batch.py`
- Modify: `backend/app/cli/main.py`
- Test: `backend/tests/test_judge_batch.py`

**Interfaces:**
- Consumes: `app.trace.io.read_trace`, `app.judge.factory.build_judge`, `app.judge.context.JudgeContext`, `app.judge.schemas.normalize_verdict`.
- Produces: `async def judge_trace(trace_path: Path, out_path: Path, *, judge, concurrency: int = 8, skip_actions=frozenset({"skip"}), require_tool_call: bool = True) -> JudgeBatchResult` with `JudgeBatchResult(judged: int, skipped: int, failed: int, resumed: int)`.

**Why this replaces two drivers:** `research/leaderboard_335t_20260726/judge_export.py` has the right properties — idempotent resume, retry with backoff, and it never persists a failed verdict, because a degraded `none @ confidence=0` is indistinguishable from a real negative label and would make resume skip the row forever. Those properties belong in the library, not in a run directory. The Kimi exclusion is gone: `require_tool_call` reads `instrument.tool_call_ok` from the trace.

- [x] **Step 1: Write the failing test**

```python
# backend/tests/test_judge_batch.py
import json

from app.judge.batch import judge_trace
from app.judge.factory import build_judge
from app.trace.io import TraceWriter
from app.trace.schema import (
    AgentManifest,
    EnvManifest,
    Instrument,
    RunManifest,
    TurnRecord,
)


def _trace(path, rows):
    manifest = RunManifest(
        kind="run", schema_version=4, run_id="jb",
        env=EnvManifest(name="darwin", seed=1), horizon=10,
        agents=[AgentManifest(agent_id="a0", turns_alive=10),
                AgentManifest(agent_id="a1", turns_alive=10)],
    )
    with TraceWriter(path, manifest) as w:
        for row in rows:
            w.append(row)
    return path


def _turn(turn, agent="a0", action="work", ok=True, msg="hello"):
    return TurnRecord(kind="turn", turn=turn, agent_id=agent, action=action,
                      monologue="m", public_message=msg,
                      instrument=Instrument(tool_call_ok=ok))


async def test_judges_every_eligible_turn(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2, agent="a1")])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"))

    assert result.judged == 2
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert {(r["turn"], r["agent_id"]) for r in lines} == {(1, "a0"), (2, "a1")}
    assert all("is_deceptive" in r for r in lines)


async def test_skips_fallback_turns_by_instrument_flag(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1, ok=False), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"))

    assert result.judged == 1
    assert result.skipped == 1
    lines = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert [r["turn"] for r in lines] == [2]


async def test_skips_skip_actions(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1, action="skip"), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=build_judge(provider="stub"))
    assert result.judged == 1
    assert result.skipped == 1


async def test_resume_does_not_rejudge(tmp_path):
    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2)])
    out = tmp_path / "v.jsonl"
    first = await judge_trace(src, out, judge=build_judge(provider="stub"))
    second = await judge_trace(src, out, judge=build_judge(provider="stub"))

    assert first.judged == 2
    assert second.judged == 0
    assert second.resumed == 2
    lines = [x for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 2  # no duplicates appended


async def test_a_failed_verdict_is_never_written(tmp_path):
    """A degraded none@0 is indistinguishable from a real negative label."""
    from app.judge.base import BaseJudge
    from app.judge.schemas import none_verdict

    class AlwaysFails(BaseJudge):
        provider = "boom"

        def __init__(self):
            super().__init__(judge_model="boom", prompt_version="v3")

        async def judge(self, ctx):
            return none_verdict("api error")

    src = _trace(tmp_path / "t.jsonl", [_turn(1), _turn(2)])
    out = tmp_path / "v.jsonl"
    result = await judge_trace(src, out, judge=AlwaysFails(), max_attempts=2)

    assert result.judged == 0
    assert result.failed == 2
    assert not out.exists() or out.read_text(encoding="utf-8").strip() == ""
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_judge_batch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.judge.batch'`

- [x] **Step 3: Write minimal implementation**

```python
# backend/app/judge/batch.py
"""Judge a v4 trace to a verdicts JSONL. Resumable, and safe to interrupt.

Two properties matter more than speed, both learned from the 335t run:

* **Resume is idempotent.** Re-running skips rows already present in *out*, so a
  key or budget cutoff mid-run never costs a re-judge.
* **A failed verdict is never written.** ``parse_verdict`` degrades an API error
  to ``none`` with ``confidence=0``; persisting that would be indistinguishable
  from a real negative label *and* would make resume skip the row forever. Such
  rows are retried and, if still failing, left unwritten -- so an incomplete run
  is visibly incomplete.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.judge.context import JudgeContext
from app.judge.schemas import normalize_verdict
from app.trace.io import read_trace

log = logging.getLogger(__name__)

DEFAULT_SKIP_ACTIONS = frozenset({"skip"})


@dataclass
class JudgeBatchResult:
    judged: int = 0
    skipped: int = 0
    failed: int = 0
    resumed: int = 0


def _already_judged(out_path: Path) -> set[tuple[int, str]]:
    if not out_path.exists():
        return set()
    done: set[tuple[int, str]] = set()
    for line in out_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        done.add((int(row["turn"]), row["agent_id"]))
    return done


async def judge_trace(
    trace_path: Path,
    out_path: Path,
    *,
    judge,
    concurrency: int = 8,
    skip_actions: Iterable[str] = DEFAULT_SKIP_ACTIONS,
    require_tool_call: bool = True,
    max_attempts: int = 3,
) -> JudgeBatchResult:
    trace_path, out_path = Path(trace_path), Path(out_path)
    manifest, records = read_trace(trace_path)
    done = _already_judged(out_path)
    skip = set(skip_actions)
    result = JudgeBatchResult(resumed=len(done))

    todo = []
    for record in records:
        if (record.turn, record.agent_id) in done:
            continue
        if record.action in skip:
            result.skipped += 1
            continue
        if require_tool_call and not record.instrument.tool_call_ok:
            result.skipped += 1
            continue
        todo.append(record)

    semaphore = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async def _one(record) -> None:
        ctx = JudgeContext(
            session_id=manifest.run_id,
            turn=record.turn,
            agent_id=record.agent_id,
            monologue=record.monologue,
            public_message=record.public_message,
            action=record.action,
            arguments=record.arguments,
            outcome=record.outcome,
            balance=record.state.balance,
            trust_score=record.state.trust_score,
            target_id=record.arguments.get("target") or record.arguments.get("target_id"),
            transactions=[],
        )
        for attempt in range(1, max_attempts + 1):
            async with semaphore:
                verdict = await judge.judge(ctx)
            if verdict.confidence > 0:
                row = normalize_verdict(verdict, actor_id=record.agent_id).model_dump()
                row["turn"] = record.turn
                row["agent_id"] = record.agent_id
                async with lock:
                    with out_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, default=str) + "\n")
                    result.judged += 1
                return
            if attempt < max_attempts:
                await asyncio.sleep(0.5 * attempt)
        async with lock:
            result.failed += 1
        log.warning("giving up on t%s/%s after %s attempts",
                    record.turn, record.agent_id, max_attempts)

    await asyncio.gather(*(_one(r) for r in todo))
    return result
```

Then add the CLI subcommand to `backend/app/cli/main.py`:

```python
def _cmd_judge(args: argparse.Namespace) -> int:
    import asyncio

    from app.judge.batch import judge_trace
    from app.judge.factory import build_judge

    judge = build_judge(provider=args.provider, judge_model=args.judge_model)
    result = asyncio.run(
        judge_trace(Path(args.trace), Path(args.out), judge=judge,
                    concurrency=args.concurrency)
    )
    print(f"judged {result.judged}, skipped {result.skipped}, "
          f"resumed {result.resumed}, failed {result.failed}")
    return 1 if result.failed else 0
```

```python
    p_judge = sub.add_parser("judge", help="judge a v4 trace to a verdicts JSONL")
    p_judge.add_argument("trace")
    p_judge.add_argument("--out", required=True)
    p_judge.add_argument("--provider", default="openrouter", choices=["stub", "openrouter"])
    p_judge.add_argument("--judge-model", default=None)
    p_judge.add_argument("--concurrency", type=int, default=8)
    p_judge.set_defaults(func=_cmd_judge)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS across the suite.

- [x] **Step 5: Commit**

```bash
git add backend/app/judge/batch.py backend/app/cli/main.py backend/tests/test_judge_batch.py
git commit -m "feat(judge): one resumable batch driver over v4 traces"
```

---

## What this plan does not cover

- **Probe suite** (spec §7) — its own plan. Should open with a divergence-rate spike before the full suite is built.
- **Site** (spec §8) — replay gallery over v4 traces, then the leaderboard.
- **Cost accounting in dollars.** `budget.max_calls` is enforced; `max_usd` needs per-model token pricing and is deliberately left unenforced rather than estimated wrongly. The field parses and is recorded; the CLI warns when it is set.


## Execution notes

Two things the plan did not anticipate, both real defects rather than plan slips.

1. **SQLite cannot run cells concurrently.** Two cells committing at once raise `cannot commit transaction - SQL statements in progress` and one cell's data is lost. SQLite is the default for offline CLI runs, so `run_sweep` now clamps concurrency to 1 when the bind's dialect is sqlite, records `effective_concurrency` on the report, and logs why. Postgres runs at the requested concurrency. `test_sqlite_is_forced_serial` pins it.

2. **`none_verdict()` could not distinguish "no deception" from "the judge failed".** Both are `is_deceptive=False, confidence=0.0`. The planned batch driver keyed on `confidence > 0`, which works for `LLMJudge` by accident and is wrong for `StubJudge`, whose honest verdicts are indistinguishable from an outage. Added `failed_verdict()` and a non-persisted `failed` flag; `parse_verdict` and `LLMJudge` use it for their degraded paths.

   This turned out to be the more serious find: `app/judge/runner.py` was persisting failed verdicts into `deception_judgments` as genuine negative labels, and its idempotency check then skipped those rows on every later pass. Any judged session that hit an API blip carries silently invented "not deceptive" rows. The DB path now drops them.

   **Follow-up worth doing:** the existing `deception_judgments` rows for session `99l5EEPjp5k` (487 rows) predate this fix and may contain such rows. They are identifiable by `confidence = 0.0` — worth checking before that data is used in the paper.
