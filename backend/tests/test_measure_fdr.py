import pytest

from app.measure import bh_correct


def _null(p_by_model_metric: dict[tuple[str, str], float]) -> dict:
    per_model: dict[str, dict] = {}
    for (model, metric), p in p_by_model_metric.items():
        per_model.setdefault(model, {})[metric] = {"p_one_sided": p}
    return {"per_model": per_model}


def test_single_test_leaves_p_unchanged():
    out = bh_correct(_null({("opus", "repeat_target_share"): 0.01}))
    assert out["n_tests"] == 1
    assert out["tests"][0]["q_bh"] == pytest.approx(0.01)
    assert out["tests"][0]["significant_at_fdr_0.05"] is True


def test_q_values_are_monotone_nondecreasing_by_rank():
    out = bh_correct(_null({
        ("a", "m"): 0.001, ("b", "m"): 0.30, ("c", "m"): 0.02, ("d", "m"): 0.04,
    }))
    qs = [t["q_bh"] for t in sorted(out["tests"], key=lambda t: t["p"])]
    assert qs == sorted(qs)


def test_borderline_p_fails_after_correction():
    """The H3d case: p=.018 alone is significant, across 24 tests it is not."""
    tests = {(f"m{i}", "metric"): 0.5 for i in range(23)}
    tests[("opus", "return_gap")] = 0.018
    out = bh_correct(_null(tests))
    hit = next(t for t in out["tests"] if t["model"] == "opus")
    assert hit["p"] == pytest.approx(0.018)
    assert hit["q_bh"] > 0.05
    assert hit["significant_at_fdr_0.05"] is False


def test_n_significant_counts_survivors():
    out = bh_correct(_null({("a", "m"): 0.001, ("b", "m"): 0.002, ("c", "m"): 0.9}))
    assert out["n_significant"] == 2


def test_empty_input_is_safe():
    out = bh_correct(_null({}))
    assert out["n_tests"] == 0
    assert out["tests"] == []
    assert out["n_significant"] == 0


def test_non_test_entries_are_ignored():
    """permutation_null blocks carry summary keys alongside the tests."""
    null = _null({("a", "m"): 0.01})
    null["per_model"]["a"]["n_deceptive"] = 12
    out = bh_correct(null)
    assert out["n_tests"] == 1


def test_measure_imports_without_a_db_driver(monkeypatch):
    """The pure metrics must not drag in app.db -- that is the portability claim."""
    import subprocess
    import sys

    code = (
        "import sys;"
        "sys.modules['asyncpg'] = None;"
        "from app.measure import bh_correct, coherence_metrics, permutation_null;"
        "assert 'app.db' not in sys.modules, sorted(m for m in sys.modules if m.startswith('app.'));"
        "print('ok')"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout
