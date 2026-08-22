"""Environment-agnostic measurement: coherence, its null model, and correction.

One import path so a paper can name it. Everything here is pure over plain
dicts and works identically against JSONL traces and DB rows, so an environment
other than Darwin reuses it by emitting :mod:`app.trace` records.
"""

from app.measure.coherence import (
    Episode,
    build_episodes,
    coherence_metrics,
    gap_sensitivity,
    pair_gaps,
    permutation_null,
)
from app.measure.fdr import bh_correct
from app.measure.metrics import classify_major, compute_metrics, detect_betrayals, gini

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
