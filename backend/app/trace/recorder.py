"""Stream a live session's trace to disk, one turn at a time.

A session run from the UI is only replayable if it leaves an artifact, and a
run that is still going -- or one that died -- is the common case. So the turn
loop appends as it goes rather than waiting for an explicit export.

Two rules make writing from the mutation path safe:

* The database has already committed by the time this runs. A write failure is
  logged and swallowed; it must never fail a turn that happened.
* Every row is flushed, so a killed process leaves a truncated-but-parseable
  trace rather than an empty buffer -- the same guarantee ``TraceWriter`` gives
  a sweep.

Records come from ``build_turn``, the single mapping shared with
``export_session``. See ``docs/adr/2026-08-26-live-session-trace-on-disk.md``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.deferred import DeferredAction
from app.models.ledger import ThoughtLog, TurnSnapshot
from app.models.registry import Contract, Office
from app.trace.adapters.darwin_db import build_turn, export_session

log = logging.getLogger(__name__)

TRACE_NAME = "trace.jsonl"

# A session id names a directory here, and `configure` upserts whatever id the
# caller asks for -- so the id is untrusted input on a filesystem path. Only
# what `secrets.token_urlsafe` produces is accepted; anything else is refused
# rather than sanitised, because a sanitised id no longer identifies the run.
_SAFE_SESSION_ID = re.compile(r"\A[A-Za-z0-9_-]{1,32}\Z")


def runs_root() -> Path:
    """Directory holding live-session traces.

    A relative setting resolves against the repo root, not the process cwd, so
    it means the same thing from a container and from a shell -- matching how
    ``releases_dir`` is resolved in ``app.main``.
    """
    configured = Path(get_settings().runs_dir)
    if configured.is_absolute():
        return configured
    return Path(__file__).resolve().parents[3] / configured


def trace_path(session_id: str) -> Path | None:
    """Where this session's trace lives, or ``None`` if the id is not safe."""
    if not _SAFE_SESSION_ID.match(session_id):
        return None
    return runs_root() / session_id / TRACE_NAME


async def record_turn(
    session: AsyncSession,
    session_id: str,
    turn: int,
    *,
    seed: int = 0,
    condition: str = "neutral",
) -> None:
    """Append one turn's records. Never raises."""
    try:
        path = trace_path(session_id)
        if path is None:
            log.warning("trace not recorded: unsafe session id %r", session_id)
            return

        if not path.exists():
            manifest, _turns, _world = await export_session(
                session, session_id, condition=condition, seed=seed
            )
            # export_session reports the horizon a finished run reached; here the
            # run has barely started, and a manifest claiming horizon 1 makes
            # every later turn fail validation. Declare the ceiling instead. The
            # agent rows are a turn-1 snapshot for the same reason -- promotion
            # into releases/ rewrites the manifest with what actually happened.
            manifest = manifest.model_copy(
                update={"horizon": max(get_settings().max_turns, turn)}
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            _append(path, manifest.model_dump(mode="json"), truncate=True)

        records, world = build_turn(turn, **await _rows(session, session_id, turn))
        for record in records:
            _append(path, record.model_dump(mode="json"))
        _append(path, world.model_dump(mode="json"))
    except Exception:  # noqa: BLE001 -- the turn already committed; see module docstring
        log.exception("trace not recorded for session %r turn %s", session_id, turn)


async def _rows(session: AsyncSession, session_id: str, turn: int) -> dict:
    async def all_of(stmt):
        return (await session.execute(stmt)).scalars().all()

    return {
        "thoughts": await all_of(
            select(ThoughtLog)
            .where(ThoughtLog.session_id == session_id, ThoughtLog.turn == turn)
            .order_by(ThoughtLog.id)
        ),
        "snapshots": await all_of(
            select(TurnSnapshot).where(
                TurnSnapshot.session_id == session_id, TurnSnapshot.turn == turn
            )
        ),
        "deferred": await all_of(
            select(DeferredAction).where(DeferredAction.session_id == session_id)
        ),
        "contracts": await all_of(
            select(Contract).where(Contract.session_id == session_id)
        ),
        "offices": await all_of(select(Office).where(Office.session_id == session_id)),
    }


def _append(path: Path, row: dict, *, truncate: bool = False) -> None:
    with path.open("w" if truncate else "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
        fh.flush()
