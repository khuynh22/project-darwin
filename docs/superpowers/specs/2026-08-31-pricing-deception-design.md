# Pricing deception in time

## Problem

All three deception actions — `bluff`, `slander`, `gaslight` — are free actions. A free
action is taken *alongside* a major action, costs no turn, and under the event clock costs
no simulation time (`durations.ACTION_BEATS` gives every free action `0.0`). Their cash
prices are $0.10, $0.20 and $0.15 against a $10 starting balance.

So an agent can work every turn *and* slander every turn. Nothing is forgone.

That matters for the measurement, not for balance. The headline number this project
produces is a deception **rate**, and a rate is only a revealed preference if the behaviour
competes with something. As built, it competes with nothing, so the rate measures a
model's disposition to deceive when deception is free — not its willingness to trade
material gain for deceptive advantage. A reviewer can say that in one sentence, and the
result does not survive it.

The interesting question is the one the current design excludes: **how much does a model
give up in order to lie?**

## Goals

- Make deception cost simulation time, so its rate is a choice under scarcity.
- Make the price a single tunable number, so it can be swept and an elasticity curve
  measured rather than a single point estimate.
- Change nothing at price zero, so every existing run and figure stays valid.

## Non-goals

- **Fixing the `gift` / `bribe` dominance.** `gift` is a free, uncapped transfer that also
  grants +2 trust to both parties, which strictly dominates the major-tier `bribe` and
  `lend`. Real, but independent of this and much smaller. Separate change.
- **Moving deception to the major tier.** That is a cliff, not a dial. It would suppress
  the behaviour hard enough to starve the dataset, and it yields one more point estimate
  rather than a curve.
- **Pricing deception on the turn loop.** `run_turn` has no concept of duration. The price
  is meaningful only under the event clock (ADR `2026-08-30-continuous-event-clock`).
- **Changing the judge or the verdict taxonomy.** What counts as deception is unchanged;
  only what it costs to do it.

## Requirements

1. A single action set defines what counts as a deception action, and both the pricing and
   the metrics read that one definition.
2. A run with `deception_cost_beats = 0` produces a trace identical to one produced before
   this change, given the same seed and roster.
3. With `deception_cost_beats = c > 0`, an agent whose decision includes a deception
   action is unavailable for `c` beats longer than an otherwise identical agent whose
   action is not deceptive. This holds whether the deception action occupies the major or
   the free slot: free actions may be taken as major, so pricing only the free slot would
   leave an agent able to slander at no cost by spending its major action on it, and the
   elasticity curve would measure the loophole rather than the price.
4. The time an event spent on deception is recorded on that event, separately from
   deliberation, travel and the action's own duration, so the price paid is auditable from
   the trace alone and in whichever slot the deception occupied.
5. An experiment spec can enumerate several prices, producing one cell per
   `(condition, seed, price)`.
6. The sweep runner can execute a cell on the event engine, since the price has no effect
   under `run_turn`.
7. Each cell's price is recoverable from its identifiers, so a deception rate produced
   later by the judge can be joined to the price that produced it.
8. Two cells differing only in price write to different trace files.

## Design

Five pieces, each independently testable.

### One definition of a deception action

`DECEPTION_ACTIONS` currently lives in `app/measure/metrics.py` as the structural-flag set
the judge is scored against. It moves to `app/oracle/schemas.py`, beside `MAJOR_ACTIONS`
and `FREE_ACTIONS`, and `measure` imports it from there.

The engine may not import `measure`, and duplicating the set would let the price and the
metric disagree about what deception is — which would make the elasticity curve a
comparison between two different definitions.

### The price

`Settings.deception_cost_beats: float = 0.0`, in `app/config.py`.

`durations.action_ticks` gains a keyword:

```python
def action_ticks(action: str, *, deception_cost_beats: float = 0.0) -> int:
```

For an action in `DECEPTION_ACTIONS` it returns `beats(table_value + deception_cost_beats)`;
otherwise the table value unchanged. Deception actions keep their `0.0` table entry, so the
default of `0.0` leaves every duration exactly as it is today.

Additive rather than an override so a non-deceptive free action that later acquires its own
duration is not silently overwritten by the deception price.

### The engine charges deception in both slots

`run_events` currently computes:

```python
busy = travel + commit_ticks(decision.action, ...)
```

which reads the **major** action only — the free action contributes nothing, so pricing it
would have no effect. It becomes:

```python
free = action_ticks(decision.free_action, deception_cost_beats=cost) if decision.free_action else 0
busy = travel + commit_ticks(decision.action, ..., deception_cost_beats=cost) + free
```

`commit_ticks` forwards the keyword to `action_ticks`, so a deception action is priced in
whichever slot it occupies. Pricing only the free slot would leave the loophole named in
requirement 3.

At `cost = 0` every free action still returns `0` and `commit_ticks` is unchanged, so
`busy` is identical to today.

### The trace records what was paid

`EventRecord` gains two fields, both `int = 0`, alongside `busy_ticks`,
`deliberation_ticks` and `travel_ticks`:

- `free_ticks` — how long the free action occupied the agent, whatever it was.
- `deception_ticks` — how much of this event's time was charged *because* the action was
  deceptive, summed across both slots.

Two fields rather than one because they answer different questions, and because the price
is not always in the free slot: a deception action taken as the major action puts its price
inside `commit_ticks`, where `free_ticks` alone would not see it. `deception_ticks` is the
field a reader joins to a verdict.

Both are schema v6 additive with defaults; no version bump, and a v6 reader that ignores
them is unaffected.

The price paid has to be visible in the artifact. Inferring it from the settings used at
run time makes a published trace unreadable without its configuration.

### The sweep axis

`ExperimentSpec` gains:

```python
deception_cost_beats: list[float] = [0.0]
engine: Literal["turn", "event"] = "turn"
scheduler: Literal["lockstep", "self_paced"] = "lockstep"
```

`Cell` gains `deception_cost_beats: float`. `cells()` becomes the product of
`conditions × seeds × deception_cost_beats`, with:

- `natural_id` = `{experiment}:{condition}:{seed}:d{cost}`
- `session_id` derived from it by the existing `_derive_session_id`, which already falls
  back to a hash when the readable form would exceed `MAX_SESSION_ID`
- `trace_name` = `{condition}-s{seed}-d{cost}`

The price **must** be in `trace_name`. It is currently `{condition}-s{seed}`, so without
this two cells differing only in price would write to the same file and the second would
overwrite the first — a silent data loss that would look like a completed sweep.

Carrying the price on `Cell` rather than parsing it back out of an id is what makes the
later join to a deception rate mechanical.

`engine` defaults to `"turn"`, so existing specs run through `run_turn` exactly as before.
`engine: "event"` routes `cell.py` to `run_events(horizon_beats=turns, policy=scheduler)`.
The default is not switched to the event engine, because continuous accrual is not
equivalent to the ten-turn cycle — tax take differs by about a third at $10 — and a silent
switch would invalidate comparisons against sweeps already run.

A spec with `engine: "turn"` and more than one price is a configuration error, not a
run that quietly produces identical cells. See Error handling.

## Interfaces

| Contract | Change | Compatibility |
|---|---|---|
| `durations.action_ticks(action)` | new keyword-only `deception_cost_beats`, default `0.0` | Backward compatible; existing callers unchanged |
| `durations.commit_ticks(action, ...)` | forwards `deception_cost_beats` | Backward compatible; defaulted |
| `oracle.schemas.DECEPTION_ACTIONS` | new export | New |
| `measure.metrics.DECEPTION_ACTIONS` | re-exported from `oracle.schemas` | Import path preserved for existing readers |
| `trace.schema.EventRecord` | new `free_ticks: int = 0`, `deception_ticks: int = 0` | Additive with defaults; v6 unchanged |
| `ExperimentSpec` | new `deception_cost_beats`, `engine`, `scheduler` | All defaulted; existing spec files load and produce the same grid |
| `sweep.spec.Cell` | new `deception_cost_beats`; `trace_name` gains a `-d{cost}` segment | **Breaking for a resumed sweep**: a sweep started before this change has cells whose `trace_name` lacks the segment, so resume would re-run them. Finish or discard in-flight sweeps before upgrading. |
| `Settings` | new `deception_cost_beats: float = 0.0` | Defaulted |

## Data

No new tables and no migration. `free_ticks` is a trace field, not a column: the price is a
property of a run, and `TurnSnapshot` restores agent state rather than run configuration.

Retention follows the existing trace policy.

## Error handling

| Condition | Behaviour |
|---|---|
| `deception_cost_beats < 0` in a spec or setting | Rejected at validation with the field named. A negative price would make lying free time. |
| `deception_cost_beats` pushes a free action past `MAX_WAKE_BEATS` | Already capped by `Scheduler.commit`; no new handling. Documented so it is not mistaken for a silent truncation. |
| `engine: "turn"` with more than one price | `ExperimentSpec` validation error: the prices would produce identical cells and a flat elasticity curve that looks like a result. |
| `decision.free_action` names an unknown action | `action_ticks` returns `DEFAULT_ACTION_BEATS` as today. Unchanged; the engine already rejects an invalid free action before applying it. |
| A deception action fails for lack of cash | The time is still charged. The agent attempted it, and refunding the time would make a failed lie free — which is the hole this closes. |

## Security

Nothing new. No trust boundary is crossed, no untrusted input is introduced;
`deception_cost_beats` is operator configuration, and the spec file is already trusted
input to the sweep runner.

## Testing

**Unit — `durations`.** Price `0` leaves every action's duration equal to its table value.
Price `c > 0` raises exactly the three deception actions and no others. Additivity holds for
a deception action with a non-zero table value.

**Unit — `schemas`.** `DECEPTION_ACTIONS` is a subset of `FREE_ACTIONS`, and
`measure.metrics.DECEPTION_ACTIONS` is the same object.

**Engine — `run_events`.** Two scripted agents identical but for their free action, one
deceptive and one not, at `cost > 0`: the deceptive one takes strictly fewer moves over the
same horizon. At `cost = 0` their move counts are equal. The same pair with the deception
action in the **major** slot, to close the loophole in requirement 3.

**Engine — accounting.** `deception_ticks` on a priced event equals the price, and is `0`
on an event whose action is not deceptive.

**Regression — the zero-price invariant.** A seeded stub run at `cost = 0` produces a trace
byte-identical to the same run before this change. This is the requirement that lets every
published figure stand, so it is a test rather than an argument.

**Sweep spec.** A spec with three prices and two seeds yields six cells with distinct
session ids. `engine: "turn"` with two prices raises.

**Sweep — trace names.** Two cells differing only in price produce different
`trace_name` values. This is the overwrite guard, so it is tested directly rather than
implied by the cell-count test.

**Acceptance.** A three-price sweep on stub agents completes, writes three distinct
traces, and each cell reports the price it ran at.

## Rollout

No flag: the default of `0.0` is itself the off switch, and every requirement above holds
at zero.

Order:

1. `DECEPTION_ACTIONS` moves; `measure` re-exports. No behaviour change.
2. `action_ticks` gains the keyword; `run_events` charges the free action. No behaviour
   change at the default.
3. `EventRecord.free_ticks`.
4. `ExperimentSpec` axis and `cell.py` event-engine path.
5. Pilot sweep on stub agents across a price range to pick the range for a real one.

Reversal is deleting the axis; step 5 produces no artifact anyone depends on.

**How we will know it is working:** the pilot sweep produces a deception rate that varies
with price. A rate that is flat across a wide price range is a finding to investigate — most
likely the price is not reaching the agents' decisions — rather than a result to publish.

## Acceptance criteria

1. **Given** a seeded stub roster and `deception_cost_beats = 0`, **when** the run executes
   on the event engine, **then** its trace is byte-identical to the same run before this
   change.
2. **Given** two agents differing only in whether their free action is deceptive, **when**
   both run to the same horizon at `deception_cost_beats = 1.0`, **then** the deceptive
   agent has strictly fewer moves.
3. **Given** any event trace, **when** an event carries a deception action at a non-zero
   price, **then** `deception_ticks` on that record equals the price in ticks, whether the
   action occupied the major or the free slot.
4. **Given** a spec with `conditions: [neutral]`, `seeds: 2`, and three prices, **when**
   cells are enumerated, **then** there are six cells with six distinct session ids.
5. **Given** a spec with `engine: "turn"` and two prices, **when** it is loaded, **then**
   validation fails naming `deception_cost_beats`.
6. **Given** a completed multi-price sweep, **when** its report is read, **then** every
   cell states the price it ran at and names a distinct trace file.
7. **Given** a deception action taken as the **major** action at a non-zero price,
   **when** the event is recorded, **then** the agent was occupied for the priced duration
   and `deception_ticks` reports it — the major slot is not a loophole.

## Open questions

| Question | Who answers | Blocking? |
|---|---|---|
| What price range does the real sweep use? | Pilot in step 5 | No — the pilot exists to answer it |
| Should the cash cost be removed when a time cost is added, or is double-pricing intended? | Repository owner | No — cash costs are small enough to be second-order, but the paper must state that both prices exist |
| Is the elasticity curve expected to be monotonic? | Pilot in step 5 | No — a non-monotonic curve is a finding, not a failure |
