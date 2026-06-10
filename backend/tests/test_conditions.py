"""Control conditions (Phase 2, Part C): neutral / honesty / deception."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register tables)
from app.models import ledger as _ledger  # noqa: F401  (register tables)
from app.models.session import SimSession


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_condition_defaults_to_neutral(db_session):
    db_session.add(SimSession(session_id="c1"))
    await db_session.commit()
    sim = await db_session.get(SimSession, "c1")
    assert sim.condition == "neutral"


@pytest.mark.asyncio
async def test_session_condition_persists(db_session):
    db_session.add(SimSession(session_id="c2", condition="deception"))
    await db_session.commit()
    sim = await db_session.get(SimSession, "c2")
    assert sim.condition == "deception"
