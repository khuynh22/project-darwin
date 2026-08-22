"""Tests for deception-coherence episode reconstruction and metrics."""

from __future__ import annotations

import pytest

from app.measure.coherence import (
    Episode,
    build_episodes,
    coherence_metrics,
    gap_sensitivity,
    pair_gaps,
)


def v(turn: int, agent: str, target: str | None, *, deceptive: bool = True, dtype: str = "false_promise"):
    return {
        "turn": turn,
        "agent_id": agent,
        "target_id": target,
        "is_deceptive": deceptive,
        "deception_type": dtype if deceptive else "none",
    }


# --------------------------------------------------------------- episodes


def test_honest_turns_produce_no_episodes():
    rows = [v(t, "opus", "grok", deceptive=False) for t in range(1, 10)]
    assert build_episodes(rows) == []


def test_consecutive_turns_form_one_episode():
    rows = [v(t, "opus", "grok") for t in (1, 2, 3)]
    (ep,) = build_episodes(rows)
    assert ep.turns == (1, 2, 3)
    assert ep.length == 3 and ep.span == 3
    assert ep.density == 1.0
    assert ep.internal_gaps == (0, 0)


def test_gap_within_max_gap_is_joined_and_counts_as_resumption():
    # turns 1 then 5 -> gap of 3 silent turns; max_gap=5 joins them.
    rows = [v(1, "opus", "grok"), v(5, "opus", "grok")]
    (ep,) = build_episodes(rows, max_gap=5)
    assert ep.turns == (1, 5)
    assert ep.internal_gaps == (3,)
    assert ep.span == 5 and ep.length == 2
    assert ep.n_resumptions(resume_gap=2) == 1


def test_gap_beyond_max_gap_splits_into_two_episodes():
    rows = [v(1, "opus", "grok"), v(20, "opus", "grok")]
    eps = build_episodes(rows, max_gap=5)
    assert [e.turns for e in eps] == [(1,), (20,)]


def test_episodes_are_split_per_target():
    rows = [v(1, "opus", "grok"), v(2, "opus", "gemini"), v(3, "opus", "grok")]
    eps = build_episodes(rows, max_gap=5)
    by_target = {e.target: e.turns for e in eps}
    assert by_target == {"grok": (1, 3), "gemini": (2,)}


def test_untargeted_excluded_by_default_included_on_request():
    rows = [v(1, "opus", None), v(2, "opus", None)]
    assert build_episodes(rows) == []
    (ep,) = build_episodes(rows, include_untargeted=True)
    assert ep.target is None and ep.length == 2


def test_type_consistency_is_modal_share():
    rows = [
        v(1, "opus", "grok", dtype="false_promise"),
        v(2, "opus", "grok", dtype="false_promise"),
        v(3, "opus", "grok", dtype="misdirection"),
    ]
    (ep,) = build_episodes(rows)
    assert ep.type_consistency == pytest.approx(2 / 3)


# ------------------------------------------------------------- pair gaps


def test_pair_gaps_are_segmentation_free():
    rows = [v(t, "opus", "grok") for t in (1, 2, 50)]
    assert pair_gaps(rows) == {("opus", "grok"): [0, 47]}


# --------------------------------------------------------------- metrics


def test_repeat_target_share_distinguishes_campaign_from_scattershot():
    # campaigner: 4 lies, all at one victim -> 3 of 4 turns are repeats.
    campaign = [v(t, "camp", "grok") for t in (1, 2, 3, 4)]
    # scattershot: 4 lies, 4 different victims -> no repeats at all.
    scatter = [v(t, "scat", tgt) for t, tgt in zip((1, 2, 3, 4), ("a", "b", "c", "d"))]
    m = coherence_metrics(campaign + scatter)["per_model"]
    assert m["camp"]["repeat_target_share"] == pytest.approx(0.75)
    assert m["scat"]["repeat_target_share"] == 0.0
    assert m["camp"]["n_targets"] == 1
    assert m["scat"]["n_targets"] == 4


def test_max_return_gap_captures_long_horizon_thread():
    rows = [v(t, "opus", "grok") for t in (1, 2, 100, 101)]
    m = coherence_metrics(rows, max_gap=200)["per_model"]["opus"]
    assert m["max_return_gap"] == 97
    assert m["return_rate"] == pytest.approx(1 / 3, abs=1e-4)  # metric rounds to 4dp


def test_lifespan_normalisation_present_only_with_lifespans():
    rows = [v(t, "opus", "grok") for t in (1, 2, 3)]
    bare = coherence_metrics(rows)["per_model"]["opus"]
    assert bare["turns_alive"] is None
    assert "episodes_per_100_turns" not in bare

    norm = coherence_metrics(rows, lifespans={"opus": 300})["per_model"]["opus"]
    assert norm["turns_alive"] == 300
    assert norm["episodes_per_100_turns"] == pytest.approx(100 / 300, abs=1e-3)
    assert norm["max_episode_span_frac_life"] == pytest.approx(3 / 300)


def test_singleton_share_flags_one_off_lies():
    rows = [v(1, "a", "x"), v(30, "a", "x"), v(60, "a", "x")]
    m = coherence_metrics(rows, max_gap=5)["per_model"]["a"]
    assert m["n_episodes"] == 3
    assert m["singleton_share"] == 1.0
    assert m["max_episode_len"] == 1


# ----------------------------------------------------------- sensitivity


def test_gap_sensitivity_monotone_in_episode_count():
    rows = [v(t, "opus", "grok") for t in (1, 4, 9, 30)]
    sweep = gap_sensitivity(rows, grid=(1, 3, 5, 8, 40))
    counts = [s["n_episodes"] for s in sweep]
    # Raising max_gap can only merge episodes, never create them.
    assert counts == sorted(counts, reverse=True)
    assert sweep[0]["n_episodes"] == 4  # max_gap=1 splits everything
    assert sweep[-1]["n_episodes"] == 1  # max_gap=40 merges everything


def test_episode_is_hashable_and_frozen():
    ep = Episode("a", "b", (1, 2), ("false_promise", "false_promise"))
    assert hash(ep)
    with pytest.raises(Exception):
        ep.deceiver = "c"  # type: ignore[misc]
