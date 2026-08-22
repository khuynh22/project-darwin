"""Benjamini-Hochberg FDR over the permutation-null test grid.

Coherence runs one test per ``(model, metric)`` cell -- 24 of them in the 335t
run. An uncorrected p-value from that grid is not a finding, so every
significance claim in the paper passes through here. Extracted from
``research/leaderboard_335t_20260726/analyze_coherence.py``, where it was
untested despite gating the results section.
"""

from __future__ import annotations

from typing import Any

DEFAULT_ALPHA = 0.05


def bh_correct(null: dict[str, Any], alpha: float = DEFAULT_ALPHA) -> dict[str, Any]:
    """Return BH-adjusted q-values for every ``(model, metric)`` test in *null*.

    *null* is the structure returned by ``permutation_null``: a ``per_model``
    mapping of model -> metric -> ``{"p_one_sided": float}``. Entries that carry
    no ``p_one_sided`` are summary values, not tests, and are skipped.
    """
    flat: list[tuple[str, str, float]] = []
    for model, metrics in null.get("per_model", {}).items():
        for metric, result in metrics.items():
            if isinstance(result, dict) and "p_one_sided" in result:
                flat.append((model, metric, float(result["p_one_sided"])))

    flat.sort(key=lambda row: row[2])
    n = len(flat)
    key = f"significant_at_fdr_{alpha}"
    tests: list[dict[str, Any]] = []

    # Walk from the largest p downward so the step-up guarantee -- q monotone
    # non-decreasing in p -- holds without a second pass.
    running_min = 1.0
    for rank in range(n, 0, -1):
        model, metric, p = flat[rank - 1]
        running_min = min(running_min, p * n / rank)
        tests.append(
            {
                "model": model,
                "metric": metric,
                "p": round(p, 4),
                "q_bh": round(running_min, 4),
                key: running_min <= alpha,
            }
        )
    tests.reverse()

    return {
        "alpha": alpha,
        "n_tests": n,
        "tests": tests,
        "n_significant": sum(1 for t in tests if t[key]),
    }
