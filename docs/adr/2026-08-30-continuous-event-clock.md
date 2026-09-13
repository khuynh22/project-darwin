# ADR 3: The turn is replaced by a continuous event clock

- **Status:** accepted
- **Date:** 2026-08-30
- **Deciders:** repository owner (product intent), principal-engineer (design)

## Context

Every agent acted exactly once per turn, and every turn cost every agent one prompt. That
made the simulation legible and the trace easy to key, but it could not express several
things the environment is supposed to be measuring:

- **No reaction.** An agent robbed on turn 12 could not answer until turn 13, and neither
  could an agent that was ignored. Being attacked and being idle produced identical
  latency, so responsiveness was not a strategy anyone could adopt or fail at.
- **No cost of deliberation.** A model that reasoned for four thousand tokens and one that
  answered in two hundred acted at the same cadence. Thinking was free, which is the one
  thing it never is.
- **No labour.** Actions were instantaneous, so `work` was a lottery ticket rather than a
  commitment. Nothing could be interrupted, witnessed in progress, or traded off against
  the time it consumed.
- **A cliff economy.** Tax and hunger fired every ten turns and did nothing in between.
- **A prompt bill proportional to turns, not to events.** An agent with nothing to decide
  paid the same as one in the middle of a negotiation.

The requirement given was to make the economy run continuously while keeping prompting
economical, and to preserve deterministic offline replay, which the measurement half of
the project depends on.

## Decision

Replace the turn with a **discrete-event simulation on a fixed-point logical clock**.

1. **Logical time, never wall-clock.** Ordering is `(tick, agent_id)`, ties broken by agent
   id, never by which HTTP response arrived first. Model latency does not enter. Time is an
   integer count of ticks (`BEAT = 1000` ticks) rather than a float, because a run is only
   reproducible if its clock arithmetic is exact.
2. **Agents schedule themselves.** Every decision carries `wake_after` (beats to sleep) and
   `wake_if` (events that wake it sooner). A prompt is sent only when an agent wakes, so
   cost tracks activity rather than wall-time.
3. **Actions occupy time,** and so does deliberation. Deliberation cost is derived from the
   tokens the model actually spent, not from measured latency: latency is mostly provider
   queueing and rate limiting, which is infrastructure noise that would make the trace
   unreplayable while adding nothing real.
4. **The economy accrues as a rate,** settled on whole-beat boundaries so the bill does not
   depend on how finely events happened to chop up time.
5. **Position is a constraint.** Actions happen at venues, travel costs time, and only
   agents present witness an event.
6. **Lockstep is a policy, not a second engine.** `policy="lockstep"` gives every agent a
   one-beat wake, ignores action duration, and disables interrupts, reproducing the old
   turn loop so the frozen-stimulus probes stay runnable.

## The measurement constraint, and how it was established

Deception coherence is measured in **gaps**: red lies to blue at move 3 and again at move
9, and the gap of five means red passed on five opportunities and deliberately returned.
Once agents sleep, a gap counted in global events mostly counts *other* agents acting and
this one sleeping — the same behaviour would score differently depending on how busy the
rest of the town was.

This was tested before any engine code was written, against the real 335-turn verdict set
in `research/leaderboard_335t_20260726/verdicts_335t.jsonl` (1600 rows, 313 deceptive, 247
targeted, 9 agents). Deceptive turns were re-indexed under four simulated wake patterns —
lockstep, uniform, sparse sleeper, bursty reactor — and the existing metrics re-run under
two competing gap definitions. Mean absolute drift from the published baseline:

| gap measured in | `repeat_target_share` | `max_return_gap` | `max_episode_len` |
|---|---|---|---|
| global event index | 0.000 | ~380 | ~3.4 |
| agent's own action index | 0.000 | 8.625 | 0.125 |

Three results, all load-bearing:

- **Global-event gaps are unusable.** Baseline `max_return_gap` values run 0–200; a drift
  of ~380 means the statistic would be measuring sleep rather than intent.
- **Own-index gaps are invariant to scheduling.** The 8.625 / 0.125 figures are *identical*
  across all four wake patterns. They are not scheduling noise but the fixed offset between
  turn index and own-action index in the source data, where agents die and skip turns.
- **`repeat_target_share` is untouched** by either choice, under every pattern. It reads no
  gaps at all, which is why the module already recommends it for headline claims.
- The permutation null's significance calls did not flip in any condition, because it holds
  each deceiver's observed indices fixed and permutes only the target.

Therefore the scheduler records **three non-interchangeable coordinates**, and the trace
carries all three: `event_id` (global total order, primary key), `tick` (simulation time,
drives accrual), and `agent_seq` (this agent's own move count, **the unit all coherence
gaps are measured in**). `measure/coherence.by_agent_seq` re-indexes rows onto it, and
`tests/test_coherence_scheduling_invariance.py` pins the invariance permanently, including
a negative control that fails if the fixture ever stops exercising ragged scheduling.

## Consequences

**Trace schema v6.** `EventRecord` joins `TurnRecord`; `SUPPORTED_SCHEMA_VERSIONS` becomes
`(4, 5, 6)` so archived runs still parse, but new runs are written as v6 and every figure
must be regenerated. This was chosen over a compatibility layer deliberately.

**Tax pressure falls by about a third at \$10.** A continuous drain compounds within the
cycle: the old loop took 15% of \$10.00 in one stroke (\$1.50), ten beats of per-beat drain
take \$1.00, because each beat is charged against an already-reduced balance that crosses
into a lower bracket partway through. This is the correct continuous reading of the same
schedule, but any comparison against a turn-loop run has to account for it. Pinned by
`test_ten_beat_tax_take_is_pinned`.

**Mortality is modestly higher.** Over an equivalent horizon with the same seed and roster,
the old loop left 3 of 5 agents alive at turn 100; the event engine under `lockstep` leaves
1 of 5 at beat 100. Disabling hunger and tax entirely still leaves only 2 of 5 alive, so
most of the difference is the agents' own betting and penalties rather than the new
accrual, which accounts for roughly one additional elimination. Recorded rather than tuned
away, because retuning constants to match a loop that is being deleted would be fitting to
the wrong target.

**Sleeping is now a real strategic error.** Under `self_paced` the stub roster took 98
actions across 123 beats against 355 under `lockstep`, because sleeping agents forgo income
while hunger and tax keep draining. That is the mechanic working, but it means a naive wake
policy is heavily punished, and per-agent action counts are no longer comparable without
conditioning on them.

**Exposure normalisation splits in two.** `turns_alive` assumed alive meant acting. Under
the event clock those diverge, and any cross-model comparison now needs to say whether it
normalises by time lived or by moves taken.

**A new fidelity field.** Continuous hunger needs fractional satiety (`food_buffer`) carried
on `Agent`, `TurnSnapshot` and `TurnState`, or a restored probe would starve on a different
schedule than the run it was mined from — the `steal_count` failure again.

## What would reopen this

- If ragged sampling turns out to break a metric not covered by the spike above — the
  segmentation sweep in `research/leaderboard_335t_20260726/coherence_report.md` is in
  turns and has not been re-run in beats.
- If the wall-clock cost of serial event processing becomes the binding constraint. The
  design anticipates speculative dispatch with invalidation (run agents concurrently on a
  read-only snapshot, discard and re-ask any decision invalidated by an interrupt that
  committed first), which preserves determinism because invalidation is a function of the
  event log. It is not implemented.
- If deliberation cost calibration (`DELIBERATION_BEATS_PER_KTOKEN = 0.3`) cannot be
  defended, it can be set to zero without touching anything else.
