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
    effective_concurrency: int = 1


def _effective_concurrency(session_factory: Any, requested: int) -> int:
    """SQLite cannot take concurrent write transactions.

    Two cells committing at once raise "cannot commit transaction - SQL
    statements in progress" and lose a cell's data. SQLite is the default for
    offline CLI runs, so the clamp happens here rather than in a README nobody
    reads. Postgres runs at the requested concurrency.
    """
    if requested <= 1:
        return 1
    bind = getattr(session_factory, "kw", {}).get("bind")
    dialect = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect == "sqlite":
        log.warning(
            "sqlite does not support concurrent cell writes; running serially "
            "(requested concurrency=%s). Use Postgres for a parallel sweep.",
            requested,
        )
        return 1
    return requested


def cell_manifest_path(out_dir: Path, cell: Cell) -> Path:
    return Path(out_dir) / f"{cell.trace_name}.manifest.json"


def _is_complete(out_dir: Path, cell: Cell) -> bool:
    """A cell is done only if its manifest parses and says so.

    A partial cell re-runs from scratch: the arena has no mid-run checkpoint,
    and resuming into one would splice two different RNG streams.
    """
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

    concurrency = _effective_concurrency(session_factory, spec.concurrency)
    report.effective_concurrency = concurrency
    semaphore = asyncio.Semaphore(concurrency)
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
                session_factory, cell, roster=roster, turns=spec.turns,
                out_dir=out_dir,
                cache_root=Path(spec.cache) if spec.cache else None,
            )
        _write_manifest(out_dir, result)
        (report.completed if result.ok else report.failed).append(result)

    await asyncio.gather(*(_one(cell) for cell in pending))
    report.stopped_for_budget = budget_hit.is_set()
    return report
