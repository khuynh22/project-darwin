"""The continuous-time primitives: clock, durations, space, accrual, scheduler."""

from __future__ import annotations

import pytest

from app.oracle.accrual import HUNGER_PENALTY_PER_BEAT, Wallet, accrue, tax_rate
from app.oracle.clock import BEAT, beats, elapsed_beats, to_beats
from app.oracle.durations import (
    ACTION_BEATS,
    MAX_DELIBERATION_BEATS,
    action_ticks,
    capacity_beats_per_unit,
    commit_ticks,
    deliberation_ticks,
)
from app.oracle.scheduler import LOCKSTEP_WAKE_BEATS, MAX_WAKE_BEATS, Scheduler
from app.oracle.schemas import FREE_ACTIONS, MAJOR_ACTIONS
from app.oracle.space import (
    Placement,
    observable_by,
    travel_ticks,
    venue_for,
    witnesses,
)


def test_beats_and_ticks_round_trip():
    assert beats(1) == BEAT
    assert to_beats(BEAT) == 1.0
    assert beats(0.5) == BEAT // 2


def test_clock_refuses_to_run_backwards():
    with pytest.raises(ValueError):
        elapsed_beats(BEAT * 2, BEAT)


def test_every_action_has_a_duration():
    assert set(ACTION_BEATS) == MAJOR_ACTIONS | FREE_ACTIONS


def test_free_actions_occupy_no_time():
    for action in FREE_ACTIONS:
        assert action_ticks(action) == 0, action


def test_major_actions_all_occupy_time():
    for action in MAJOR_ACTIONS:
        assert action_ticks(action) > 0, action


def test_deliberation_scales_with_tokens_and_is_capped():
    assert deliberation_ticks(0, 0) == 0
    assert deliberation_ticks(0, 200) < deliberation_ticks(0, 4000)
    assert deliberation_ticks(0, 10**9) == beats(MAX_DELIBERATION_BEATS)


def test_thinking_longer_makes_you_act_later():
    quick = commit_ticks("trade", completion_tokens=150)
    slow = commit_ticks("trade", reasoning_tokens=4000, completion_tokens=400)
    assert slow > quick


def test_specialist_produces_faster_than_generalist():
    assert capacity_beats_per_unit("ore", "ore") < capacity_beats_per_unit("ore", "food")


def test_travel_is_free_within_a_venue_and_symmetric_between_them():
    assert travel_ticks("market", "market") == 0
    assert travel_ticks("market", "alley") == travel_ticks("alley", "market") > 0


def test_every_action_maps_to_a_venue():
    for action in MAJOR_ACTIONS | FREE_ACTIONS:
        assert venue_for(action)


def test_only_agents_present_witness_an_event():
    placements = [
        Placement("red", "alley", arrives_at=0),
        Placement("blue", "alley", arrives_at=0, departs_at=BEAT),
        Placement("green", "market", arrives_at=0),
    ]
    assert witnesses(placements, venue="alley", tick=0, actor="red") == ["blue"]
    assert witnesses(placements, venue="alley", tick=BEAT, actor="red") == []


def test_the_plaza_is_public_and_everywhere_else_is_not():
    placements = [
        Placement("red", "plaza", arrives_at=0),
        Placement("blue", "market", arrives_at=0),
    ]
    assert observable_by(placements, venue="plaza", tick=0, actor="red") == ["blue"]
    assert observable_by(placements, venue="alley", tick=0, actor="red") == []


def test_continuous_tax_stays_under_the_old_cycles_single_stroke():
    """A drain compounds within the cycle, so ten beats take less than the old
    loop's one-off charge against the opening balance. Documented, not a bug --
    but it is a real reduction in pressure and comparisons must account for it."""
    wallet = Wallet(balance=10.0, food=99, food_buffer=1.0)
    accrue(wallet, from_tick=0, to_tick=beats(10))
    nominal = 10.0 * tax_rate(10.0)
    assert 0.5 * nominal < wallet.tax_paid < nominal


def test_ten_beat_tax_take_is_pinned():
    """Pins the number the docstring quotes, so a rate change cannot drift the
    calibration without a failing test."""
    wallet = Wallet(balance=10.0, food=99, food_buffer=1.0)
    accrue(wallet, from_tick=0, to_tick=beats(10))
    assert wallet.tax_paid == pytest.approx(1.00, abs=0.01)


def test_accrual_is_independent_of_how_time_was_sliced():
    """The property the whole design rests on: chopping time finer must not
    change the bill, or the economy would run faster in a chatty world."""
    coarse = Wallet(balance=12.0, food=5, food_buffer=1.0)
    accrue(coarse, from_tick=0, to_tick=beats(10))

    fine = Wallet(balance=12.0, food=5, food_buffer=1.0)
    for b in range(10):
        accrue(fine, from_tick=beats(b), to_tick=beats(b + 1))

    ragged = Wallet(balance=12.0, food=5, food_buffer=1.0)
    for lo, hi in ((0, 0.3), (0.3, 3.7), (3.7, 4.0), (4.0, 9.1), (9.1, 10.0)):
        accrue(ragged, from_tick=beats(lo), to_tick=beats(hi))

    assert coarse.balance == fine.balance == ragged.balance
    assert coarse.food == fine.food == ragged.food
    assert coarse.tax_paid == fine.tax_paid == ragged.tax_paid


def test_an_agent_with_food_eats_before_it_starves():
    wallet = Wallet(balance=5.0, food=3, food_buffer=0.0)
    result = accrue(wallet, from_tick=0, to_tick=beats(10))
    assert result.food_eaten >= 1
    assert wallet.hunger_paid == 0.0


def test_sleeping_through_an_empty_pantry_costs_real_money():
    wallet = Wallet(balance=5.0, food=0, food_buffer=0.0, tax_exempt=True)
    accrue(wallet, from_tick=0, to_tick=beats(10))
    assert wallet.hunger_paid == pytest.approx(10 * HUNGER_PENALTY_PER_BEAT, rel=1e-6)
    assert wallet.starved_beats == 10


def test_invested_capital_is_exempt_from_the_drain():
    exempt = Wallet(balance=20.0, food=99, food_buffer=1.0, tax_exempt=True)
    taxed = Wallet(balance=20.0, food=99, food_buffer=1.0)
    accrue(exempt, from_tick=0, to_tick=beats(10))
    accrue(taxed, from_tick=0, to_tick=beats(10))
    assert exempt.tax_paid == 0.0
    assert taxed.tax_paid > 0.0


def test_partial_beats_are_carried_not_dropped():
    wallet = Wallet(balance=10.0, food=99, food_buffer=1.0)
    result = accrue(wallet, from_tick=0, to_tick=beats(0.9))
    assert result.beats_settled == 0
    assert wallet.tax_paid == 0.0


def _drain(sched: Scheduler, *, limit: int, wake: float = 1.0) -> list[tuple]:
    out = []
    while len(out) < limit:
        event = sched.pop()
        if event is None:
            break
        out.append((event.event_id, event.tick, event.agent_id, event.agent_seq))
        sched.commit(event.agent_id, busy_until=event.tick, wake_after_beats=wake)
    return out


def test_ordering_does_not_depend_on_admission_order():
    a = Scheduler()
    for agent in ("red", "blue", "green"):
        a.admit(agent)
    b = Scheduler()
    for agent in ("green", "red", "blue"):
        b.admit(agent)
    assert _drain(a, limit=12) == _drain(b, limit=12)


def test_agent_seq_counts_that_agent_only():
    sched = Scheduler()
    sched.admit("red")
    sched.admit("blue")
    seqs: dict[str, list[int]] = {"red": [], "blue": []}
    for _ in range(6):
        event = sched.pop()
        seqs[event.agent_id].append(event.agent_seq)
        wake = 1.0 if event.agent_id == "red" else 3.0
        sched.commit(event.agent_id, busy_until=event.tick, wake_after_beats=wake)
    assert seqs["red"] == list(range(1, len(seqs["red"]) + 1))
    assert seqs["blue"] == list(range(1, len(seqs["blue"]) + 1))


def test_a_fast_agent_acts_more_often_than_a_slow_one():
    sched = Scheduler()
    sched.admit("swift")
    sched.admit("slow")
    counts = {"swift": 0, "slow": 0}
    for _ in range(40):
        event = sched.pop()
        counts[event.agent_id] += 1
        sched.commit(
            event.agent_id,
            busy_until=event.tick,
            wake_after_beats=1.0 if event.agent_id == "swift" else 8.0,
        )
    assert counts["swift"] > counts["slow"] * 3


def test_being_robbed_wakes_you_early_if_you_asked_for_it():
    sched = Scheduler()
    sched.admit("blue")
    first = sched.pop()
    sched.commit(
        "blue", busy_until=first.tick, wake_after_beats=20.0, wake_if={"stolen_from"}
    )
    assert sched.pending_tick("blue") == beats(20)
    assert sched.fire("stolen_from", target="blue", at_tick=beats(2)) is True
    assert sched.pending_tick("blue") == beats(2)
    assert sched.pop().wake_reason == "interrupt:stolen_from"


def test_an_interrupt_you_did_not_ask_for_does_not_wake_you():
    sched = Scheduler()
    sched.admit("blue")
    first = sched.pop()
    sched.commit(
        "blue", busy_until=first.tick, wake_after_beats=20.0, wake_if={"extorted"}
    )
    assert sched.fire("stolen_from", target="blue", at_tick=beats(2)) is False
    assert sched.pending_tick("blue") == beats(20)


def test_an_unknown_trigger_is_rejected_rather_than_silently_kept():
    sched = Scheduler()
    sched.admit("blue")
    event = sched.pop()
    sched.commit(
        "blue",
        busy_until=event.tick,
        wake_after_beats=9.0,
        wake_if={"the_moon_is_full"},
    )
    assert sched.fire("the_moon_is_full", target="blue", at_tick=beats(1)) is False


def test_a_long_action_cannot_be_cancelled_by_asking_to_wake_immediately():
    sched = Scheduler()
    sched.admit("red")
    event = sched.pop()
    busy = event.tick + action_ticks("work")
    assert sched.commit("red", busy_until=busy, wake_after_beats=0.0) > busy


def test_sleep_requests_are_capped():
    sched = Scheduler()
    sched.admit("red")
    event = sched.pop()
    at = sched.commit("red", busy_until=event.tick, wake_after_beats=10_000.0)
    assert at == event.tick + beats(MAX_WAKE_BEATS)


def test_lockstep_policy_reproduces_a_round_robin_turn_loop():
    sched = Scheduler(policy="lockstep")
    for agent in ("red", "blue", "green"):
        sched.admit(agent)
    order = []
    for _ in range(9):
        event = sched.pop()
        order.append(event.agent_id)
        sched.commit(
            event.agent_id,
            busy_until=event.tick,
            wake_after_beats=17.0,
            wake_if={"stolen_from"},
        )
    assert order == ["blue", "green", "red"] * 3


def test_lockstep_ignores_interrupts():
    sched = Scheduler(policy="lockstep")
    sched.admit("blue")
    event = sched.pop()
    sched.commit(
        "blue", busy_until=event.tick, wake_after_beats=1.0, wake_if={"stolen_from"}
    )
    assert sched.fire("stolen_from", target="blue", at_tick=0) is False


def test_lockstep_wake_is_exactly_one_beat():
    sched = Scheduler(policy="lockstep")
    sched.admit("red")
    event = sched.pop()
    at = sched.commit("red", busy_until=event.tick, wake_after_beats=99.0)
    assert at == event.tick + beats(LOCKSTEP_WAKE_BEATS)


def test_a_retired_agent_stops_being_scheduled():
    sched = Scheduler()
    sched.admit("red")
    sched.admit("blue")
    event = sched.pop()
    sched.commit(event.agent_id, busy_until=event.tick, wake_after_beats=1.0)
    sched.retire("red")
    seen = set()
    for _ in range(8):
        nxt = sched.pop()
        if nxt is None:
            break
        seen.add(nxt.agent_id)
        sched.commit(nxt.agent_id, busy_until=nxt.tick, wake_after_beats=1.0)
    assert "red" not in seen


def test_the_queue_drains_when_nobody_reschedules():
    sched = Scheduler()
    sched.admit("red")
    assert sched.pop() is not None
    assert sched.pop() is None


def test_event_ids_are_a_dense_total_order():
    sched = Scheduler()
    for agent in ("red", "blue", "green"):
        sched.admit(agent)
    events = _drain(sched, limit=15)
    assert [e[0] for e in events] == list(range(1, 16))
    ticks = [e[1] for e in events]
    assert ticks == sorted(ticks)
