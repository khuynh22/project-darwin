"""Judge a v4 trace to a verdicts JSONL. Resumable, and safe to interrupt.

Two properties matter more than speed, both learned from the 335-turn run:

* **Resume is idempotent.** Re-running skips rows already present in *out*, so a
  key or budget cutoff mid-run never costs a re-judge.
* **A failed verdict is never written.** A judge that errors returns
  ``failed_verdict``; persisting it would be indistinguishable from a real
  negative label *and* would make resume skip the row forever. Such rows are
  retried and, if still failing, left unwritten -- so an incomplete run is
  visibly incomplete and the next pass picks it up.

This replaces both earlier drivers: the DB-backed ``scripts/judge_deception.py``
and the run-local ``research/leaderboard_335t_20260726/judge_export.py``. The
hardcoded ``EXCLUDE_AGENTS = {"kimi"}`` is gone -- eligibility now reads
``instrument.tool_call_ok`` off the trace.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.judge.context import JudgeContext
from app.judge.schemas import normalize_verdict
from app.trace.io import read_trace
from app.trace.schema import TurnRecord

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
            done.add((int(row["turn"]), row["agent_id"]))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return done


def _context(run_id: str, record: TurnRecord) -> JudgeContext:
    return JudgeContext(
        session_id=run_id,
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


async def judge_trace(
    trace_path: Path,
    out_path: Path,
    *,
    judge: Any,
    concurrency: int = 8,
    skip_actions: Iterable[str] = DEFAULT_SKIP_ACTIONS,
    require_tool_call: bool = True,
    max_attempts: int = 3,
    retry_backoff: float = 0.5,
) -> JudgeBatchResult:
    trace_path, out_path = Path(trace_path), Path(out_path)
    manifest, records = read_trace(trace_path)
    done = _already_judged(out_path)
    skip = set(skip_actions)
    result = JudgeBatchResult(resumed=len(done))

    todo: list[TurnRecord] = []
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

    async def _one(record: TurnRecord) -> None:
        ctx = _context(manifest.run_id, record)
        for attempt in range(1, max_attempts + 1):
            async with semaphore:
                verdict = await judge.judge(ctx)
            if not verdict.failed:
                row = normalize_verdict(verdict, actor_id=record.agent_id).model_dump()
                row["turn"] = record.turn
                row["agent_id"] = record.agent_id
                async with lock:
                    with out_path.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, default=str) + "\n")
                    result.judged += 1
                return
            if attempt < max_attempts and retry_backoff:
                await asyncio.sleep(retry_backoff * attempt)
        async with lock:
            result.failed += 1
        log.warning(
            "giving up on t%s/%s after %s attempts; row left unwritten for a later pass",
            record.turn, record.agent_id, max_attempts,
        )

    await asyncio.gather(*(_one(record) for record in todo))
    return result
