"""Read and write schema-v4 traces. Manifest first, turns after."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType

from app.trace.schema import (
    EventRecord,
    RunManifest,
    TurnRecord,
    WorldRecord,
    parse_record,
)


class TraceWriter:
    """Writes a manifest line on open, then one line per appended turn.

    Flushes after every row: a sweep that is killed mid-run must leave a
    truncated-but-parseable trace, never a buffer that vanished.
    """

    def __init__(self, path: Path, manifest: RunManifest) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open("w", encoding="utf-8")
        self._write(manifest.model_dump(mode="json"))

    def _write(self, row: dict) -> None:
        self._fh.write(json.dumps(row, default=str) + "\n")
        self._fh.flush()

    def append(self, record: TurnRecord | WorldRecord) -> None:
        self._write(record.model_dump(mode="json"))

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> TraceWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def _iter_raw(path: Path) -> Iterator[dict]:
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_trace(path: Path) -> tuple[RunManifest, list[TurnRecord]]:
    """Manifest plus turns. World records are dropped -- see ``read_world``.

    Keeping the turn stream free of world records means every existing reader
    keeps working against a v5 file without change.
    """
    manifest: RunManifest | None = None
    turns: list[TurnRecord] = []
    for raw in _iter_raw(path):
        record = parse_record(raw)
        if isinstance(record, RunManifest):
            manifest = record
        elif isinstance(record, TurnRecord):
            turns.append(record)
    if manifest is None:
        raise ValueError(f"{path}: no run manifest (is this a legacy v2/v3 export?)")
    return manifest, turns


def read_events(path: Path) -> list[EventRecord]:
    """Event records in file order, for a v6 trace. Empty for v4 and v5.

    Kept separate from :func:`read_trace` for the same reason world records are:
    every existing reader keeps working against a turn-shaped file without
    change, and a reader that wants events asks for them.
    """
    return [r for r in map(parse_record, _iter_raw(path)) if isinstance(r, EventRecord)]


def read_world(path: Path) -> dict[int, WorldRecord]:
    """World records indexed by turn. Empty for a v4 trace."""
    out: dict[int, WorldRecord] = {}
    for raw in _iter_raw(path):
        record = parse_record(raw)
        if isinstance(record, WorldRecord):
            out[record.turn] = record
    return out


def iter_turns(path: Path) -> Iterator[TurnRecord]:
    for raw in _iter_raw(path):
        record = parse_record(raw)
        if isinstance(record, TurnRecord):
            yield record
