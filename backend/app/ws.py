from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket


class Broadcaster:
    """Room-aware async broadcaster: events fan out only to one session's clients."""

    def __init__(self) -> None:
        # session_id -> set of connected sockets
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms.setdefault(session_id, set()).add(ws)

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            room = self._rooms.get(session_id)
            if room is not None:
                room.discard(ws)
                if not room:
                    self._rooms.pop(session_id, None)

    async def broadcast(self, session_id: str, payload: dict) -> None:
        msg = json.dumps(payload, default=str)
        async with self._lock:
            room = self._rooms.get(session_id)
            if not room:
                return
            stale: list[WebSocket] = []
            for ws in room:
                try:
                    await ws.send_text(msg)
                except Exception:  # noqa: BLE001
                    stale.append(ws)
            for ws in stale:
                room.discard(ws)
            if not room:
                self._rooms.pop(session_id, None)


broadcaster = Broadcaster()
