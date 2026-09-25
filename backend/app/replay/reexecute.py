"""Re-run a recorded trace through the real engine using cached decisions.

This is the reproducibility claim in executable form. The engine genuinely
re-executes -- outcomes are computed, the RNG draws, the ledger is written --
and only the models' contributions come from disk.

A divergence is a finding, not noise: either the environment changed or the
cache is stale. Both are reported per turn rather than summarised away.

**The engine swallows agent exceptions** (``engine.py`` logs and falls back so
one provider outage cannot kill a live turn). That is right for a live run and
wrong for a replay: a ``CacheMiss`` would otherwise be absorbed and the run
would finish as a *different* experiment wearing the same name. So misses are
counted independently and any non-zero count fails the report, and the env
version is checked before a single turn executes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.replay.cache import ResponseCache
from app.replay.cached_agent import CachedAgent
from app.trace.io import read_trace

log = logging.getLogger(__name__)


async def _purge(session: Any, session_id: str) -> None:
    """Clear the target session before re-executing.

    Leftover rows from an earlier attempt would silently seed a different world
    -- ``seed_roster`` skips agents that already exist, so the run would start
    mid-game and every turn after would "diverge" for the wrong reason.
    """
    from sqlalchemy import delete

    from app.models.agent import Agent
    from app.models.deferred import DeferredAction
    from app.models.ledger import ThoughtLog, Transaction, TurnSnapshot, WorldEvent

    for model in (Agent, ThoughtLog, Transaction, TurnSnapshot, WorldEvent, DeferredAction):
        await session.execute(delete(model).where(model.session_id == session_id))
    await session.commit()


@dataclass
class Divergence:
    turn: int
    agent_id: str
    recorded: str
    replayed: str

    def __str__(self) -> str:
        return (
            f"t{self.turn} {self.agent_id}: recorded {self.recorded!r} "
            f"but replayed {self.replayed!r}"
        )


@dataclass
class ReexecuteReport:
    run_id: str
    turns: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    divergences: list[Divergence] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        """A miss alone is enough to fail, even with no visible divergence.

        The engine's fallback action can coincide with the recorded one, so
        absence of divergence does not imply the cache served the run.
        """
        return not self.divergences and not self.error and self.cache_misses == 0


async def reexecute(
    trace_path: Path,
    cache_root: Path,
    session_factory: Any,
    *,
    mode: str = "strict",
    session_id: str = "reexec",
    prompt_version: str | None = None,
) -> ReexecuteReport:
    """*prompt_version* defaults to the live PROMPT_VERSION.

    Never hardcode it: a stale literal here misses every cache key the moment
    the judge prompt is bumped, and the run silently re-executes as a fresh
    experiment instead of a replay.
    """
    from app.judge.prompts import PROMPT_VERSION
    from app.oracle.engine import run_turn, seed_roster

    if prompt_version is None:
        prompt_version = PROMPT_VERSION

    manifest, records = read_trace(trace_path)
    report = ReexecuteReport(run_id=manifest.run_id)

    if manifest.venue_gating:
        # Re-executing this ungated does fail -- every prompt misses the cache --
        # but it fails reading as a stale cache, which sends the next person
        # rebuilding the cache instead of noticing that nothing here can honour
        # gating. Say so before a single turn runs.
        report.error = (
            "VenueGatingUnsupported: trace was recorded with venue gating, and "
            "reexecute drives run_turn, which offers every action regardless of "
            "where an agent stands. No entry point can replay a gated run yet."
        )
        return report

    cache = ResponseCache(cache_root, env_version=manifest.env.version)

    recorded_version = cache.recorded_env_version()
    if recorded_version is not None and recorded_version != manifest.env.version:
        report.error = (
            f"EnvVersionMismatch: cache recorded against {recorded_version!r}, "
            f"trace declares {manifest.env.version!r}"
        )
        return report
    roster = [
        {
            "agent_id": a.agent_id,
            "display_name": a.agent_id.upper(),
            "provider": "stub",
            "personality": a.persona or "",
            "sprite": "blue",
            "model": a.model,
        }
        for a in manifest.agents
    ]
    agents = {
        a.agent_id: CachedAgent(
            a.agent_id, cache=cache, inner=None, mode=mode,
            model=a.model, prompt_version=prompt_version,
        )
        for a in manifest.agents
    }

    recorded = {(r.turn, r.agent_id): r for r in records}
    horizon = manifest.horizon

    try:
        async with session_factory() as session:
            await _purge(session, session_id)
            await seed_roster(session, session_id, roster=roster, seed=manifest.env.seed)
        for turn in range(1, horizon + 1):
            async with session_factory() as session:
                await run_turn(session, session_id=session_id, turn=turn,
                               agents=agents, seed=manifest.env.seed,
                               condition=manifest.condition)
            report.turns = turn
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        report.error = repr(exc)

    stats = cache.stats()
    report.cache_hits = stats.hits
    report.cache_misses = stats.misses

    if not report.error:
        async with session_factory() as session:
            from app.trace.adapters.darwin_db import export_session

            _, replayed_records, _ = await export_session(
                session, session_id, seed=manifest.env.seed
            )
        for row in replayed_records:
            source = recorded.get((row.turn, row.agent_id))
            if source is None:
                continue
            if source.action != row.action or source.outcome != row.outcome:
                report.divergences.append(
                    Divergence(turn=row.turn, agent_id=row.agent_id,
                               recorded=f"{source.action} -> {source.outcome}",
                               replayed=f"{row.action} -> {row.outcome}")
                )
    return report
