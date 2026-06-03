"""In-memory per-session runtime state (single-process). Caches the per-session
lock + decrypted roster; the DB is the source of truth and sessions reload
lazily after a restart. Locks don't coordinate across multiple instances."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class SessionRuntime:
    """Live, in-memory state for one simulation session."""

    session_id: str
    balance_visibility: str
    # Roster specs incl. decrypted ``api_key`` — in-memory only, never persisted.
    roster: list[dict]
    # Serializes turns within this session; distinct sessions run concurrently.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Set by POST /stop (without the lock) to break a running turn loop.
    stop_requested: bool = False


class SessionRegistry:
    """Lazily-loaded registry of live sessions, keyed by ``session_id``."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRuntime] = {}
        self._load_lock = asyncio.Lock()

    def put(self, runtime: SessionRuntime) -> None:
        self._sessions[runtime.session_id] = runtime

    def forget(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def get_or_load(self, session_id: str) -> SessionRuntime | None:
        """Live runtime, rebuilt from the DB on first hit. ``None`` if unknown."""
        rt = self._sessions.get(session_id)
        if rt is not None:
            return rt
        # Double-checked locking: only one coroutine reconstructs a given session.
        async with self._load_lock:
            rt = self._sessions.get(session_id)
            if rt is not None:
                return rt
            rt = await self._load_from_db(session_id)
            if rt is not None:
                self._sessions[session_id] = rt
            return rt

    async def _load_from_db(self, session_id: str) -> SessionRuntime | None:
        """Rebuild a runtime from persisted session + agents + encrypted keys."""
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models.agent import Agent
        from app.models.api_key import get_session_keys
        from app.models.session import SimSession

        async with SessionLocal() as session:
            sim = await session.get(SimSession, session_id)
            if sim is None:
                return None
            agents = (
                (
                    await session.execute(
                        select(Agent).where(Agent.session_id == session_id)
                    )
                )
                .scalars()
                .all()
            )
            keys = await get_session_keys(session, session_id)

        roster: list[dict] = []
        for a in agents:
            spec: dict = {
                "agent_id": a.agent_id,
                "display_name": a.display_name,
                "provider": a.provider,
                "model": a.model or "",
                "personality": a.personality,
                "sprite": a.sprite,
            }
            raw = keys.get(a.provider)
            if raw:
                spec["api_key"] = raw
            roster.append(spec)

        return SessionRuntime(
            session_id=session_id,
            balance_visibility=sim.balance_visibility,
            roster=roster,
        )


# Process-wide singleton.
registry = SessionRegistry()
