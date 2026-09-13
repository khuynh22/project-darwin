"""Coherence must not depend on how agents were scheduled.

This is the property the continuous clock is designed around. Once agents wake
at their own pace, a gap counted in global events mostly counts *other* agents
acting and this one sleeping, so the same behaviour scores differently depending
on how busy the rest of the town happened to be.

Measured in the deceiver's own action index the statistic is a fact about the
deceiver. These tests pin that, so a future change to the metric or the
scheduler cannot quietly reintroduce the dependency.
"""

from __future__ import annotations

import random

import pytest

from app.measure.coherence import by_agent_seq, coherence_metrics

AGENTS = ("red", "blue", "green")
VICTIMS = {"red": "blue", "blue": "green", "green": "red"}

WAKE_PATTERNS = {
    "lockstep": lambda rng: 1,
    "uniform": lambda rng: rng.randint(1, 3),
    "sparse_sleeper": lambda rng: rng.choice([1, 2, 8, 15]),
    "bursty_reactor": lambda rng: 1 if rng.random() < 0.6 else rng.randint(10, 25),
}

HEADLINE_KEYS = ("repeat_target_share", "max_return_gap", "max_episode_len")


def _verdicts() -> list[dict]:
    """A fixed campaign: each agent lies at its own moves 3, 5, 6, 14, 15, 30."""
    rows = []
    for agent in AGENTS:
        for move in range(1, 41):
            deceptive = move in {3, 5, 6, 14, 15, 30}
            rows.append(
                {
                    "turn": move,
                    "agent_id": agent,
                    "is_deceptive": deceptive,
                    "deception_type": "lie" if deceptive else "none",
                    "target_id": VICTIMS[agent] if deceptive else None,
                }
            )
    return rows


def _reschedule(rows: list[dict], pattern, seed: int = 7) -> list[dict]:
    """Re-index rows onto a global event id under a given wake pattern."""
    rng = random.Random(seed)
    stamped = []
    for agent in AGENTS:
        tick = 0
        moves = sorted(r for r in {row["turn"] for row in rows if row["agent_id"] == agent})
        for move in moves:
            tick += pattern(rng)
            stamped.append((tick, agent, move))
    stamped.sort(key=lambda s: (s[0], s[1]))
    event_of = {(a, m): eid for eid, (t, a, m) in enumerate(stamped, start=1)}
    return [
        {**r, "turn": event_of[(r["agent_id"], r["turn"])]}
        for r in rows
        if (r["agent_id"], r["turn"]) in event_of
    ]


def _headline(rows: list[dict]) -> dict[str, dict[str, float]]:
    per_model = coherence_metrics(rows)["per_model"]
    return {
        agent: {k: block.get(k) for k in HEADLINE_KEYS}
        for agent, block in per_model.items()
    }


BASELINE = _headline(_verdicts())


@pytest.mark.parametrize("name", sorted(WAKE_PATTERNS))
def test_own_index_gaps_are_invariant_across_wake_patterns(name):
    rescheduled = _reschedule(_verdicts(), WAKE_PATTERNS[name])
    assert _headline(by_agent_seq(rescheduled)) == BASELINE


@pytest.mark.parametrize("name", ["sparse_sleeper", "bursty_reactor"])
def test_global_event_gaps_are_not_invariant(name):
    """The negative control. If this ever passes, the fixture stopped exercising
    ragged scheduling and the invariance test above proves nothing."""
    rescheduled = _reschedule(_verdicts(), WAKE_PATTERNS[name])
    assert _headline(rescheduled) != BASELINE


def test_repeat_target_share_survives_either_gap_unit():
    """The segmentation-free statistic the module recommends for headline
    claims: it reads no gaps at all, so scheduling cannot touch it."""
    for name in WAKE_PATTERNS:
        rescheduled = _reschedule(_verdicts(), WAKE_PATTERNS[name])
        for rows in (rescheduled, by_agent_seq(rescheduled)):
            got = _headline(rows)
            for agent, block in got.items():
                assert block["repeat_target_share"] == pytest.approx(
                    BASELINE[agent]["repeat_target_share"]
                ), (name, agent)


def test_by_agent_seq_is_idempotent():
    once = by_agent_seq(_verdicts())
    assert by_agent_seq(once) == once
