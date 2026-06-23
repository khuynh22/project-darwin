"""Batch-judge one session: triple + ground truth per agent-turn -> K verdicts
-> idempotent upsert into deception_judgments (keyed by the identity tuple).

Offline batch by design — never called from the turn loop.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.judge.base import BaseJudge
from app.judge.context import build_context
from app.judge.schemas import normalize_verdict
from app.models.judgment import DeceptionJudgment
from app.models.ledger import ThoughtLog, Transaction, TurnSnapshot


async def judge_session(
    session: AsyncSession,
    session_id: str,
    judge: BaseJudge,
    *,
    samples: int = 1,
    concurrency: int = 8,
) -> int:
    """Judge every decision agent-turn in *session_id* with *judge*, drawing
    *samples* verdicts each. Returns the number of verdict rows written.
    Re-running with the same (judge_model, prompt_version) overwrites in place.
    If any judge call raises, the whole batch aborts uncommitted (judges are
    expected never to raise; the shipped judges degrade to a none-verdict instead)."""
    thoughts = (
        (
            await session.execute(
                select(ThoughtLog)
                .where(ThoughtLog.session_id == session_id, ThoughtLog.action != "skip")
                .order_by(ThoughtLog.turn, ThoughtLog.agent_id)
            )
        )
        .scalars()
        .all()
    )
    snaps = {
        (s.turn, s.agent_id): s
        for s in (
            await session.execute(
                select(TurnSnapshot).where(TurnSnapshot.session_id == session_id)
            )
        ).scalars()
    }
    txns_by: dict[tuple[int, str], list] = defaultdict(list)
    for tx in (
        await session.execute(
            select(Transaction)
            .where(Transaction.session_id == session_id)
            .order_by(Transaction.turn, Transaction.id)
        )
    ).scalars():
        txns_by[(tx.turn, tx.actor_id)].append(tx)

    sem = asyncio.Semaphore(concurrency)

    async def _one(th, k: int):
        ctx = build_context(
            th, snaps.get((th.turn, th.agent_id)), txns_by.get((th.turn, th.agent_id), [])
        )
        async with sem:
            verdict = await judge.judge(ctx)
        return th, k, verdict

    results = await asyncio.gather(
        *[_one(th, k) for th in thoughts for k in range(samples)]
    )

    written = 0
    for th, k, v in results:
        v = normalize_verdict(v, actor_id=th.agent_id)
        existing = (
            await session.execute(
                select(DeceptionJudgment).where(
                    DeceptionJudgment.session_id == session_id,
                    DeceptionJudgment.turn == th.turn,
                    DeceptionJudgment.agent_id == th.agent_id,
                    DeceptionJudgment.judge_model == judge.judge_model,
                    DeceptionJudgment.prompt_version == judge.prompt_version,
                    DeceptionJudgment.sample_idx == k,
                )
            )
        ).scalar_one_or_none()
        row = existing or DeceptionJudgment(
            session_id=session_id, turn=th.turn, agent_id=th.agent_id,
            judge_model=judge.judge_model, prompt_version=judge.prompt_version,
            sample_idx=k,
        )
        row.is_deceptive = v.is_deceptive
        row.deception_type = v.deception_type
        row.channels_in_conflict = list(v.channels_in_conflict)
        row.target_id = v.target_id
        row.confidence = v.confidence
        row.rationale = v.rationale
        row.evidence = v.evidence.model_dump()
        if existing is None:
            session.add(row)
        written += 1

    await session.commit()
    return written
