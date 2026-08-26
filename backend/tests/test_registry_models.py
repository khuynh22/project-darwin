"""Registries are per-session tables the judge can read as ground truth."""

import inspect

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import deferred as _deferred  # noqa: F401  (register table)
from app.models.registry import OFFICES, TERM_TURNS, Contract, Office


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


def _contract(**over) -> Contract:
    base = dict(
        session_id="s1", contract_id="c1", proposer_id="opus",
        counterparty_id="gemini",
        terms={"deliver": {"good": "tech", "qty": 3}, "pay": 2.0},
        created_turn=5, deadline_turn=10,
    )
    base.update(over)
    return Contract(**base)


@pytest.mark.asyncio
async def test_contract_round_trips_and_defaults_to_open(db_session):
    db_session.add(_contract())
    await db_session.commit()
    row = (await db_session.execute(
        select(Contract).where(Contract.session_id == "s1")
    )).scalar_one()
    assert row.status == "open"
    assert row.resolved_turn is None
    assert row.terms["deliver"]["qty"] == 3


@pytest.mark.asyncio
async def test_contracts_are_scoped_by_session(db_session):
    db_session.add_all([_contract(), _contract(session_id="s2", contract_id="c2")])
    await db_session.commit()
    rows = (await db_session.execute(
        select(Contract).where(Contract.session_id == "s1")
    )).scalars().all()
    assert [r.contract_id for r in rows] == ["c1"]


@pytest.mark.asyncio
async def test_contract_summary_is_legible(db_session):
    summary = _contract().summary()
    assert "opus" in summary and "gemini" in summary
    assert "3 tech" in summary
    assert "turn 10" in summary
    assert "[open]" in summary


@pytest.mark.asyncio
async def test_office_round_trips_and_computes_expiry(db_session):
    db_session.add(Office(session_id="s1", office="auditor", holder_id="opus",
                          since_turn=4))
    await db_session.commit()
    row = (await db_session.execute(
        select(Office).where(Office.session_id == "s1")
    )).scalar_one()
    assert row.holder_id == "opus"
    assert row.term_turns == TERM_TURNS
    assert row.expires_at() == 4 + TERM_TURNS


@pytest.mark.asyncio
async def test_a_vacant_office_holds_no_agent(db_session):
    db_session.add(Office(session_id="s1", office="bank", holder_id=None, since_turn=0))
    await db_session.commit()
    row = (await db_session.execute(select(Office))).scalar_one()
    assert row.holder_id is None


def test_offices_are_a_small_fixed_set():
    """Each office must justify itself by the lie it makes tellable."""
    assert OFFICES == ("bank", "auditor", "arbiter", "collector")


def test_registry_tables_are_registered_on_the_metadata():
    names = set(Base.metadata.tables)
    assert "contracts" in names
    assert "offices" in names


def test_init_db_imports_the_registry_module():
    """create_all only builds tables whose module has been imported.

    A new model that nothing imports is invisible to create_all, so the table
    silently never exists in the running app -- no migration row would help,
    because the table itself is absent. New tables need the import; new columns
    on old tables need the _MIGRATIONS row. Different failure, different guard.
    """
    from app import db as db_mod

    source = inspect.getsource(db_mod.init_db)
    assert "registry" in source, "app.models.registry is not imported by init_db"
