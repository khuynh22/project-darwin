"""Read-only registry over published artifacts.

A release is a directory holding a v4 trace and, optionally, its verdicts,
probe scores, and a note. Nothing here touches the sessions tables: a gallery
request must never mutate simulation state.

Layout::

    releases/<run_id>/trace.jsonl      schema v4, required
                     /verdicts.jsonl   optional
                     /scores.json      optional
                     /about.md         optional
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.trace.io import read_trace
from app.trace.schema import RunManifest, TurnRecord

log = logging.getLogger(__name__)

TRACE_NAME = "trace.jsonl"
VERDICTS_NAME = "verdicts.jsonl"
SCORES_NAME = "scores.json"
ABOUT_NAME = "about.md"

MAX_PAGE = 200


@dataclass(frozen=True)
class ReleaseSummary:
    run_id: str
    condition: str
    horizon: int
    n_agents: int
    n_turns: int
    state_fidelity: str
    models: list[str] = field(default_factory=list)
    has_verdicts: bool = False
    has_scores: bool = False
    about: str = ""


@dataclass(frozen=True)
class Release:
    summary: ReleaseSummary
    manifest: RunManifest
    turns: list[TurnRecord]


# Keyed by (path, mtime): a republished release is picked up without a restart,
# and a gallery page load does not re-parse a 2000-line trace per request.
_CACHE: dict[tuple[str, float], Release] = {}


def _trace_path(root: Path, run_id: str) -> Path:
    return Path(root) / run_id / TRACE_NAME


def load_release(root: Path, run_id: str) -> Release | None:
    path = _trace_path(root, run_id)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None

    key = (str(path), mtime)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    try:
        manifest, turns = read_trace(path)
    except Exception as exc:  # noqa: BLE001 - a bad release is skipped, never served
        log.warning("skipping release %s: %s", run_id, exc)
        return None

    directory = path.parent
    about_path = directory / ABOUT_NAME
    summary = ReleaseSummary(
        run_id=manifest.run_id or run_id,
        condition=manifest.condition,
        horizon=manifest.horizon,
        n_agents=len(manifest.agents),
        n_turns=len(turns),
        state_fidelity=manifest.state_fidelity,
        models=sorted({a.model for a in manifest.agents if a.model}),
        has_verdicts=(directory / VERDICTS_NAME).exists(),
        has_scores=(directory / SCORES_NAME).exists(),
        about=about_path.read_text(encoding="utf-8") if about_path.exists() else "",
    )
    release = Release(summary=summary, manifest=manifest, turns=turns)

    # Drop any stale entry for this path before caching the fresh one.
    for stale in [k for k in _CACHE if k[0] == str(path)]:
        _CACHE.pop(stale, None)
    _CACHE[key] = release
    return release


def list_releases(root: Path) -> list[ReleaseSummary]:
    root = Path(root)
    if not root.is_dir():
        return []
    out: list[ReleaseSummary] = []
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        release = load_release(root, directory.name)
        if release is not None:
            out.append(release.summary)
    return out


def read_turns(
    root: Path, run_id: str, *, offset: int = 0, limit: int = 50
) -> tuple[list[TurnRecord], int]:
    release = load_release(root, run_id)
    if release is None:
        return ([], 0)
    limit = max(1, min(limit, MAX_PAGE))
    offset = max(0, offset)
    return (release.turns[offset:offset + limit], len(release.turns))


def read_verdicts(root: Path, run_id: str) -> dict[tuple[int, str], dict]:
    path = Path(root) / run_id / VERDICTS_NAME
    if not path.exists():
        return {}
    index: dict[tuple[int, str], dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            index[(int(row["turn"]), row["agent_id"])] = row
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return index


def read_scores(root: Path, run_id: str) -> list[dict]:
    path = Path(root) / run_id / SCORES_NAME
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("skipping scores for %s: %s", run_id, exc)
        return []
    return data if isinstance(data, list) else [data]
