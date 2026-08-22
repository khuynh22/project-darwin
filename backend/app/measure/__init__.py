"""Environment-agnostic measurement: coherence, its null model, and correction.

One import path so a paper can name it. Everything eagerly exported here is
pure over plain dicts and imports with no database driver installed, so an
environment other than Darwin reuses it by emitting :mod:`app.trace` records.

``compute_metrics`` and friends are DB-bound, so they are resolved lazily
(PEP 562): importing this package must never drag in ``app.db`` and require an
asyncpg/aiosqlite install just to run ``bh_correct`` over a JSONL file.
"""

from typing import Any

from app.measure.coherence import (
    Episode,
    build_episodes,
    coherence_metrics,
    gap_sensitivity,
    pair_gaps,
    permutation_null,
)
from app.measure.fdr import bh_correct

_LAZY = {"classify_major", "compute_metrics", "detect_betrayals", "gini"}

__all__ = [
    "Episode",
    "bh_correct",
    "build_episodes",
    "classify_major",
    "coherence_metrics",
    "compute_metrics",
    "detect_betrayals",
    "gap_sensitivity",
    "gini",
    "pair_gaps",
    "permutation_null",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        from app.measure import metrics

        return getattr(metrics, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
