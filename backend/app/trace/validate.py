"""Structural validation of a v4 trace. A precondition for judging."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.trace.schema import RunManifest, TurnRecord, WorldRecord, parse_record

MAX_ERRORS = 50

log = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    ok: bool = True
    n_turns: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.ok = False
        if len(self.errors) < MAX_ERRORS:
            self.errors.append(message)

    def warn(self, message: str) -> None:
        """Structurally sound, but something downstream cannot honour it.

        Kept off ``ok``: a gated trace is a valid trace, and failing validation
        would block judging and measurement, which read the recorded triple and
        do not care where the agent stood.
        """
        self.warnings.append(message)
        log.warning("%s", message)


def validate_trace(path: Path) -> ValidationReport:
    report = ValidationReport()
    manifest: RunManifest | None = None

    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = parse_record(json.loads(line))
            except (json.JSONDecodeError, ValidationError) as exc:
                report.fail(f"line {lineno}: {exc}")
                continue

            if isinstance(record, RunManifest):
                if lineno != 1:
                    report.fail(f"line {lineno}: manifest must be the first line")
                manifest = record
                if manifest.venue_gating:
                    report.warn(
                        f"{path}: recorded with venue gating. No entry point can "
                        "re-execute it yet -- replay and probe replay both drive "
                        "run_turn ungated and refuse a gated manifest."
                    )
                continue

            if manifest is None:
                report.fail(f"line {lineno}: record before any run manifest")
                continue

            if isinstance(record, WorldRecord):
                if record.turn > manifest.horizon:
                    report.fail(
                        f"line {lineno}: world turn {record.turn} exceeds "
                        f"horizon {manifest.horizon}"
                    )
                continue

            report.n_turns += 1
            _check_turn(record, manifest, lineno, report)

    if manifest is None:
        report.fail("no run manifest found")
    return report


def _check_turn(
    record: TurnRecord, manifest: RunManifest, lineno: int, report: ValidationReport
) -> None:
    if record.agent_id not in manifest.lifespans():
        report.fail(f"line {lineno}: turn for agent {record.agent_id!r} absent from manifest")
    if record.turn > manifest.horizon:
        report.fail(f"line {lineno}: turn {record.turn} exceeds horizon {manifest.horizon}")
    if record.turn < 1:
        report.fail(f"line {lineno}: turn {record.turn} is not positive")
