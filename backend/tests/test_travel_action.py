"""The travel action: what it accepts, and what it refuses to do."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models.agent import Agent
from app.oracle.actions import ACTION_TABLE, do_travel

SID = "trv"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(
            Agent(
                session_id=SID,
                agent_id="red",
                display_name="Red",
                provider="stub",
                personality="x",
                sprite="red",
                venue="plaza",
            )
        )
        await s.commit()
        yield s
    await engine.dispose()


async def test_travelling_to_a_built_venue_is_accepted(session):
    result = await do_travel(
        session, session_id=SID, turn=1, actor_id="red", venue="alley"
    )

    assert result.success


async def test_travelling_to_where_you_already_stand_is_rejected(session):
    result = await do_travel(
        session, session_id=SID, turn=1, actor_id="red", venue="plaza"
    )

    assert not result.success
    assert "already" in result.note


@pytest.mark.parametrize("target", ["courthouse", "atlantis", ""])
async def test_travelling_to_an_unbuilt_or_unknown_venue_is_rejected(session, target):
    result = await do_travel(
        session, session_id=SID, turn=1, actor_id="red", venue=target
    )

    assert not result.success
    assert "no such building" in result.note


async def test_travel_is_registered_in_the_action_table():
    assert ACTION_TABLE["travel"] is do_travel
