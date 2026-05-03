"""Streaming thought-log exporter — writes JSONL during web-served simulation."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_active_exporter: ThoughtExporter | None = None


class ThoughtExporter:
    """Appends one JSONL row per agent-turn decision to a file."""

    def __init__(self, session_label: str | None = None) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        label = session_label or "web"
        self._dir = Path("thought_logs")
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"session_{label}_{ts}.jsonl"
        self._fh = open(self._path, "a", encoding="utf-8")  # noqa: SIM115
        log.info("ThoughtExporter opened: %s", self._path)

    @property
    def filepath(self) -> Path:
        return self._path

    def append(
        self,
        *,
        turn: int,
        agent_id: str,
        monologue: str,
        action: str,
        arguments: dict,
        outcome: str,
    ) -> None:
        row = {
            "schema_version": 2,
            "turn": turn,
            "agent_id": agent_id,
            "monologue": monologue,
            "action": action,
            "arguments": arguments,
            "outcome": outcome,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._fh.write(json.dumps(row, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()
        log.info("ThoughtExporter closed: %s", self._path)

    def tail(self, n: int = 50) -> list[dict]:
        """Return the last *n* entries from the file."""
        try:
            with open(self._path, encoding="utf-8") as f:
                lines = f.readlines()
            return [json.loads(line) for line in lines[-n:]]
        except Exception:  # noqa: BLE001
            return []


def start_export(session_label: str | None = None) -> ThoughtExporter:
    global _active_exporter
    if _active_exporter is not None:
        _active_exporter.close()
    _active_exporter = ThoughtExporter(session_label)
    return _active_exporter


def get_exporter() -> ThoughtExporter | None:
    return _active_exporter


def stop_export() -> None:
    global _active_exporter
    if _active_exporter is not None:
        _active_exporter.close()
        _active_exporter = None
