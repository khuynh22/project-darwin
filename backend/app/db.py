from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
engine = create_async_engine(_settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create tables (additive) and backfill any missing columns on existing tables.

    ``create_all`` never ALTERs existing tables, so new columns on old tables
    must be added explicitly.  We keep a simple list of ``(table, column, type)``
    tuples here instead of pulling in Alembic for what is still a research tool.
    """
    import logging

    from sqlalchemy import inspect, text

    from app.models import agent, api_key, deferred, ledger  # noqa: F401

    log = logging.getLogger(__name__)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # --- Backfill missing columns on pre-existing tables ---------------------
    _MIGRATIONS: list[tuple[str, str, str, str]] = [
        # (table, column, pg_type, default)
        ("agents", "consecutive_errors", "INTEGER", "0"),
        ("agents", "last_error", "VARCHAR(512)", "NULL"),
        ("agents", "trust_score", "FLOAT", "50.0"),
        ("agents", "steal_count", "INTEGER", "0"),
        ("agents", "share_balance", "BOOLEAN", "TRUE"),
        ("agents", "inventory", "JSON", "'{}'"),
        ("agents", "rest_bonus", "BOOLEAN", "FALSE"),
        ("agents", "will_target", "VARCHAR(64)", "NULL"),
        ("agents", "extortion_pending", "JSON", "NULL"),
        ("agents", "bribe_pending", "JSON", "NULL"),
        ("agents", "marriage_pending", "VARCHAR(64)", "NULL"),
        ("agents", "specialty", "VARCHAR(16)", "'ore'"),
        ("thoughts", "public_message", "VARCHAR(1024)", "''"),
    ]

    async with engine.begin() as conn:
        # Get existing column names per table
        def _get_columns(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            result = {}
            for tbl, col, _, _ in _MIGRATIONS:
                if tbl not in result:
                    try:
                        result[tbl] = {c["name"] for c in insp.get_columns(tbl)}
                    except Exception:  # noqa: BLE001
                        result[tbl] = set()
            return result

        existing = await conn.run_sync(_get_columns)

        for tbl, col, pg_type, default in _MIGRATIONS:
            if col not in existing.get(tbl, set()):
                stmt = f"ALTER TABLE {tbl} ADD COLUMN {col} {pg_type} DEFAULT {default}"
                log.info("Backfilling column: %s", stmt)
                await conn.execute(text(stmt))
