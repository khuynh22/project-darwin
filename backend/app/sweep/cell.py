"""Run one ``(condition, seed)`` cell to a validated v4 trace."""

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
    cache_root: Path | None = None,
) -> CellResult:
    """Run one cell. With *cache_root*, every model decision is recorded.

    Recording is the difference between a paid run that can be replayed and one
    that cannot, and it cannot be added afterwards -- the decisions are gone
    once the run ends.
    """
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
        if cache_root is not None:
            from app.config import ENV_VERSION
            from app.judge.prompts import PROMPT_VERSION
            from app.replay.cache import ResponseCache
            from app.replay.cached_agent import CachedAgent

            cache = ResponseCache(Path(cache_root) / cell.trace_name,
                                  env_version=ENV_VERSION)
            # Key on the roster's model, not the agent object's. StubAgent
            # reports "stub" while the roster and the trace manifest both say
            # "stub/model", and a replay reads the manifest -- so keying on the
            # object would miss every entry it just recorded.
            models = {spec["agent_id"]: spec.get("model", "") or "" for spec in roster}
            agents = {
                agent_id: CachedAgent(
                    agent_id, cache=cache, inner=inner, mode="permissive",
                    model=models.get(agent_id, ""),
                    prompt_version=PROMPT_VERSION,
                )
                for agent_id, inner in agents.items()
            }

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
            manifest, records, world = await export_session(
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
        by_turn: dict[int, list] = {}
        for record in records:
            by_turn.setdefault(record.turn, []).append(record)
        world_by_turn = {w.turn: w for w in world}
        # World record first for its turn, so a reader sees the registries that
        # were in force when the turn's decisions were made.
        for turn in sorted(by_turn):
            if turn in world_by_turn:
                writer.append(world_by_turn[turn])
            for record in by_turn[turn]:
                writer.append(record)

    return CellResult(
        cell=cell,
        ok=True,
        turns_run=turns_run,
        trace_path=trace_path,
        eliminated=eliminated,
        apex=apex,
    )
