"""Tests for the LLM-judge deception layer (app/judge/* + models/judgment.py)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import agent as _agent  # noqa: F401  (register tables)
from app.models import api_key as _api_key  # noqa: F401  (register tables)
from app.models import deferred as _deferred  # noqa: F401  (register tables)
from app.models import ledger as _ledger  # noqa: F401  (register tables)
from app.models import session as _session  # noqa: F401  (register tables)
from app.models.judgment import DeceptionJudgment

# ---- Task 1: the verdict table ----------------------------------------------


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


def _judgment(**over) -> DeceptionJudgment:
    base = dict(
        session_id="j", turn=1, agent_id="a", judge_model="stub",
        prompt_version="v1", sample_idx=0, is_deceptive=True,
        deception_type="misdirection",
        channels_in_conflict=["public_message", "action"],
        target_id="b", confidence=0.9, rationale="says trade, does steal",
        evidence={"private_span": "rob him", "public_span": "let's trade",
                  "ground_truth_fact": "action=steal"},
    )
    base.update(over)
    return DeceptionJudgment(**base)


@pytest.mark.asyncio
async def test_judgment_roundtrip(db_session):
    db_session.add(_judgment())
    await db_session.commit()
    row = (
        await db_session.execute(
            select(DeceptionJudgment).where(DeceptionJudgment.session_id == "j")
        )
    ).scalar_one()
    assert row.is_deceptive is True
    assert row.deception_type == "misdirection"
    assert row.channels_in_conflict == ["public_message", "action"]
    assert row.evidence["public_span"] == "let's trade"


@pytest.mark.asyncio
async def test_judgment_identity_tuple_coexists(db_session):
    # Same agent-turn judged by two models, two prompt versions, K=2 samples.
    db_session.add_all([
        _judgment(sample_idx=0),
        _judgment(sample_idx=1),
        _judgment(judge_model="other/model"),
        _judgment(prompt_version="v2"),
    ])
    await db_session.commit()
    rows = (
        await db_session.execute(
            select(DeceptionJudgment).where(DeceptionJudgment.session_id == "j")
        )
    ).scalars().all()
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_purge_session_deletes_judgments(db_session):
    from app.main import _purge_session

    db_session.add_all([_judgment(), _judgment(session_id="keep")])
    await db_session.commit()
    await _purge_session(db_session, "j")
    await db_session.commit()
    rows = (await db_session.execute(select(DeceptionJudgment))).scalars().all()
    assert [r.session_id for r in rows] == ["keep"]
