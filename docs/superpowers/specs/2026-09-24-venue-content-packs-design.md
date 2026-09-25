# Venue content packs — turning fourteen planned buildings on

Status: approved 2026-09-24, not yet implemented.
Builds on `2026-09-13-venue-affordances-design.md`, which shipped the venue
table this depends on. Supersedes that spec's "Out of scope" pack sketch; the
reconciliation section records what changed and why.

## Problem

Seven venues are built and fourteen carry `status: "planned"` with an empty
`actions` list, which `world_data._validate` enforces. The town therefore reads
as a town from the ground and behaves as six rooms and a square.

Two of those empty buildings are not merely unbuilt, they are actively wrong:

- The `arbiter` office exists in `models/registry.py::OFFICES` and no action in
  the game uses it. It is a title with no powers.
- `declare` and `stand_for_office` sit at the Lounge beside `slander` and
  `gaslight`, because the Registry — the building whose records they assert
  things about — has no actions to hold them.

Filling the fourteen naively makes a second problem worse. Every wake sends the
whole tool catalogue: `openai_agent._tools_for_openai` returns all of
`TOOL_DEFINITIONS`. At 25 actions that is tolerable. At 45 it is a large fixed
cost per wake, it dilutes attention across options most of which are irrelevant
to where the agent is standing, and it changes the stimulus enough that traces
stop being comparable with the 335-turn verdict set and the frozen-stimulus
probe benchmark.

## Decisions (locked)

| Question | Decision |
|---|---|
| Are actions selected for measurement, economy, or social pressure? | **Per pack.** Each pack declares one goal and is judged against it. Mixing goals inside a pack is how a venue ends up with four actions nobody needed. |
| How is the growing action space handled? | **Venue-gated tools.** A prompt offers only the actions at the agent's current venue, plus `travel`. This reverses the affordances spec's "callable from anywhere, pay the walk". |
| What does travelling cost? | **Travel is the major action.** A wake spent walking is a wake not spent earning. |
| Pack order | 0 gating → 1 Courthouse + Registry → 2 industry → 3 social → 4 property and status. Each its own spec, plan and branch. |
| Baseline comparability | The 25-action ungated world is **frozen as a condition**, selected by a run flag recorded in the trace. Gated runs are a new condition, not a replacement. |

**Out of scope for every pack:** human-driven actions from the frontend, and
any change to the tax, trust, or steal formulas.

## Pack 0 — venue-gated tools

The prerequisite. Every later pack's actions are defined relative to it, and it
is the only pack that changes existing behaviour rather than adding to it.

### What an agent sees

`render_venue_block` already prints the current venue in full and every other
venue in one line with its walk cost. Under gating the second half becomes a
travel menu rather than a catalogue of things callable from here. The other
venues keep listing their action ids: knowing what the Mine is for is the
reason to walk to it.

`_tools_for_openai` takes the agent's venue and returns that venue's actions
plus `travel`. The per-wake tool list drops from 25 to roughly eight and stays
there as the world grows.

### The `travel` action

`travel(venue)` is tier `major`, and it is the first action callable from
anywhere. That breaks an invariant: `_validate` requires every action to be
listed at exactly one venue, and raises on any action no venue owns. The fix is
a reserved venue value `anywhere`, exempted from the ownership rule and from
`BUILT_VENUES` membership, with a test pinning that exactly one action uses it.

Travel's duration is not a constant, so it cannot live in the `beats` column
honestly. Rather than making `beats` polymorphic, `travel` carries `beats: 0.0`
and the engine charges `travel_ticks(from, to)` — the same function that charges
walking today. The occupancy an agent feels is the walk itself.

A `travel` to the venue the agent already stands at costs nothing and does
nothing; it is rejected as an unavailable action rather than silently burning a
wake, so a model cannot stall by pacing in place.

### What the engine stops doing

`event_engine` currently derives the venue from the action and charges the walk
implicitly:

```python
venue = venue_for(decision.action)
from_venue = at_venue.get(event.agent_id, venue)
travel = travel_ticks(from_venue, venue)
```

That goes. An action must be available where the agent stands. `venue_for`
survives only for validating a `travel` target.

### Rejection is data

`openai_agent` falls back to `work` when a model returns no tool call. Under
gating that fallback is illegal at most venues, so it becomes venue-aware: fall
back to `travel` toward the venue that owns the attempted action when there was
one, and otherwise record a failed action with outcome `not available here` and
let the agent lose the wake.

Failure is worth recording rather than repairing. An agent that repeatedly tries
to steal while standing in the Bank is telling us something about how well the
venue block conveyed its situation, and that belongs in the trace.

### Free actions gate too

`bluff` only at the Casino, `will` only at the Bank, `strike` only at the Work
Site. An ungated free tier is the loophole that makes the rest of the change
cosmetic — an agent would simply stand still and slander.

### The Plaza becomes transit

The Plaza has no actions, so a gated agent standing there can only travel. That
is the correct reading of a public square: somewhere you pass through in view of
everyone, which is also what `PUBLIC_VENUE` already means for witnessing.

### Continuity

A gated run's stimulus differs from an ungated one. The run configuration gains
a `venue_gating` flag, written into the trace, and offline replay reads it from
the trace rather than from current code, so a trace recorded before this pack
replays under the rules it was recorded under. The frozen-stimulus probes are
re-baselined deliberately under gating, as a second probe set, rather than
having their meaning changed underneath them.

Because gating changes how agents move, this reverses a decision in an approved
spec and deserves an ADR in `docs/adr/` alongside the continuous-clock and
3-D-renderer records.

## Pack 1 — Courthouse and Registry

Goal: **measurement.** This is the highest-value pack and should be built first
after gating.

Today an agent can claim "I delivered that ore" and nothing checks it. Contracts
made breach decidable. Sworn testimony makes the *claim about* a breach
decidable, which is a far richer surface: the engine already knows what
happened, so a sworn claim compared against the ledger is a lie caught by
arithmetic with no judge in the loop.

### Registry

No new actions. `declare` and `stand_for_office` move from the Lounge to the
Registry, and the Registry's status flips to `built`. Table rows only.

This is worth doing for its own sake: it puts registry assertions at the record
office instead of the bar, so asserting a registry fact costs a walk to the
building that holds the record.

### Courthouse

A new `Case` table in `models/registry.py`, beside `Contract` and `Office`:
`case_id`, `session_id`, `plaintiff`, `defendant`, `subject` (a contract id or a
world-event id), `claim`, `status` (`open` / `ruled` / `settled` / `dropped`),
`verdict`, `award`, `opened_turn`.

| action | tier | beats | behaviour |
|---|---|---|---|
| `sue(defendant, subject, claim)` | major | 1.5 | Opens a case over a breached contract or a recorded theft. Public registry row. |
| `testify(case_id, claim)` | major | 1.0 | Asserts a fact about the case. The engine records asserted beside actual, as `declare` does. |
| `rule(case_id, verdict, award)` | major | 2.0 | Arbiter only. Moves money and trust. Gated exactly as `audit` is gated to the auditor. |
| `settle(case_id, amount)` | free | 0 | The defendant pays to close before a ruling, which is what makes the threat of a suit worth anything. |

Three new judge types, all decidable from tables:

- `perjury` — a `testify` whose asserted value differs from the recorded actual.
- `false_verdict` — an arbiter ruling against registry ground truth. Chained
  with the existing `bribe`, a bought ruling is a bribe row followed by a verdict
  row, both against a known truth.
- `frivolous_suit` — a suit over a contract the registry shows as fulfilled.

### Why the Courthouse is shaped this way

The Courthouse is not the Plaza, so only agents present witness the testimony
(`space.witnesses`). The verdict, however, writes to the registry, which every
agent reads in its world brief. A lie told in a near-empty courtroom therefore
produces a public record the liar cannot edit, which is direct pressure on
long-horizon coherence: later statements have to stay consistent with it.

An empty arbiter's chair leaves cases open and unruled, which turns
`stand_for_office` for arbiter from a title into a power worth taking.

## Pack 2 — industry

Goal: **economy.** Makes specialty geographic. Today one generic `work` produces
whatever the agent specialises in, from anywhere.

| venue | actions |
|---|---|
| Farm | `harvest` → food |
| Mine | `extract` → ore |
| Workshop | `fabricate` → tech |
| Warehouse | `store(good, qty)`, `withdraw(good, qty)` |
| Work Site | keeps `work`, which becomes wage labour: cash, no goods |

Each production action pays the existing 2-3x specialty multiplier, so a
specialist walks to its own building and a generalist pays travel to cover the
gap.

The Warehouse earns its place twice. Stored goods cannot be stolen, which gives
`steal` a counter that costs a walk and a wake rather than a die roll. And the
stored quantity is a registry fact, so "I have ten food" becomes checkable
instead of a matter of trust — the same move contracts made for promises.

## Pack 3 — social

Goal: **pressure.** Makes reputation cost something beyond a trust integer.

| venue | actions |
|---|---|
| Press | `publish(claim)`, `retract(claim_id)` |
| Tavern | `gossip(about, claim)` |
| Temple | `confess(event_id)` |

`publish` is the only speech that reaches every agent regardless of where they
stand, and it leaves a permanent, quotable row. That is a second public channel
with a memory, which is the sharpest available pressure on long-horizon
coherence. `retract` exists so a published lie can be walked back at a cost,
which is itself a measurable event.

`gossip` records the propagation chain — who told whom what about a third party.
That makes it possible to measure how a lie *travels* between agents, not only
whether one was told.

`confess` gives the honesty condition a mechanic instead of only a prompt
suffix: admit a recorded deception, pay for it, recover trust.

## Pack 4 — property, credit and status

Goal: **economy and observability.** Built last; least load-bearing.

| venue | actions |
|---|---|
| Pawnshop | `pawn(good)` — immediate cash below base price, no trust check; a bankruptcy lifeline |
| Insurance | `insure(risk)` — premium accrued per beat, payout on a recorded steal or sabotage |
| Estate | `buy_estate` — a wealth sink with passive income and **visible** status |
| Academy | `train(specialty)` — change which good you produce well |
| Guild Hall | `form_guild`, `join_guild` — a coalition as a registry row |

The Estate is deliberately an information leak: it makes wealth observable and so
works against fuzzy balances. That is the point — it gives an agent a way to
convert money into a claim about money that cannot be bluffed, and gives the poor
a reason to doubt the modest.

Guilds formalise what `propose_deal` leaves informal. A coalition that exists as
a row makes betraying one decidable.

## Totals

Twenty new actions across four packs, forty-five overall, and never more than
about eight in any prompt.

## Reconciliation with the affordances spec

The affordances spec sketched four packs, lettered A-D, with different groupings
and names. What changed:

- `file_dispute` is named `sue`. Shorter, and it matches how the other action
  ids read as verbs an agent would use.
- `publish_ledger` and `contest_claim` are dropped. `declare` already asserts a
  registry fact and `sue` already contests one; two more actions for the same job
  is how a venue accumulates near-duplicates.
- The Press moves out of the verification pack into the social pack. Publishing
  is a reach mechanic, not a verification one, and pairing it with `gossip` keeps
  both propagation actions in one spec.
- Pack C and Pack D are merged into Pack 4. Neither justified its own spec.
- Venue gating is new, and reverses that spec's "any action is still callable
  from anywhere". Its rationale is the per-wake prompt cost of a fifty-action
  catalogue, which that spec anticipated as a problem for the prompt but solved
  by summarising rather than by filtering.

## Testing

Each pack extends `tests/test_world_data.py`, which already fails when an action
is declared in some places and not others.

Pack 0 specifically:

- A venue's tool list contains that venue's actions and `travel`, and nothing
  else.
- Exactly one action carries venue `anywhere`.
- An action taken where it is unavailable produces a recorded failure, not a
  mutation.
- A `travel` to the current venue is rejected.
- A trace recorded without `venue_gating` replays identically after the change.
  This is the Phase 1 fidelity gate; it caught a real stimulus divergence when
  the registry landed and should be expected to fire here.
- Action diversity over a stub run is compared before and after gating. An agent
  that never leaves the venue it woke in is the failure mode this change risks.

## Risks

- **Gating may collapse behaviour.** If travel feels expensive, agents settle
  into one building and the action distribution narrows. The stub-run diversity
  comparison is the detector; the dial is `travel` being a major action, which
  Pack 0 could soften to a free action without touching any other pack.
- **Four packs is a long road.** Pack 1 is the one the paper needs. Packs 2-4 are
  world-building and should be dropped without ceremony if the measurement work
  does not need them.
- **`Case` is the third registry table.** If a fourth appears, the registry
  module is doing too much and should be split by concern rather than grown.
