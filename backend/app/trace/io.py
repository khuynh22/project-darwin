"""Read and write schema-v4 traces. Manifest first, turns after."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType

from app.trace.schema import RunManifest, TurnRecord, parse_record


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

    def append(self, record: TurnRecord) -> None:
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
    manifest: RunManifest | None = None
    turns: list[TurnRecord] = []
    for raw in _iter_raw(path):
        record = parse_record(raw)
        if isinstance(record, RunManifest):
            manifest = record
        else:
            turns.append(record)
    if manifest is None:
        raise ValueError(f"{path}: no run manifest (is this a legacy v2/v3 export?)")
    return manifest, turns


def iter_turns(path: Path) -> Iterator[TurnRecord]:
    for raw in _iter_raw(path):
        record = parse_record(raw)
        if isinstance(record, TurnRecord):
            yield record
