# Layered Economy, Deterministic Replay, and 3-D View — design

**Date:** 2026-08-24
**Status:** approved design, pre-implementation
**Builds on:** `docs/superpowers/specs/2026-08-22-darwin-benchmark-harness-design.md` (harness, trace v4, probe suite — all implemented)

## 1. Why, and the constraint that shapes everything

Darwin's environment is deliberately not the paper's contribution — the 2026-08-01 re-sweep
settled that, and a bigger arena competes on the axis we lose. This spec grows the
environment anyway, under one rule that makes the growth serve the thesis instead of
fighting it:

> **Every new mechanic must either widen the deception label space or give the judge more
> ground truth. A mechanic that does neither is scenery and does not ship.**

That rule is not decoration. It has a sharp consequence: the most valuable additions are the
ones that convert *interpretive* judgements into *checkable* ones. Today the judge decides
"was this a false promise?" by reading a monologue. With a contract registry it reads a row:
the agent signed terms, the terms were not met, and that is a fact. Institutions are worth
building because they make deception measurable, not because they make the world richer.

The second half of this spec — deterministic replay — is a measurement contribution outright.
A harness whose runs can be replayed, branched, and re-executed offline is a stronger claim
than any environment feature, and it is the thing other researchers actually need from us.

### Known defect this spec closes

`turn_snapshots` records `balance`, `trust_score`, `alive`, `inventory`, `spouse_id`. It does
**not** record `steal_count`, and `oracle/actions.py:474` reads:

```python
success_rate = max(0.15, 0.60 - 0.08 * actor.steal_count)
```

Every restored probe therefore gives its agents `steal_count = 0`. An agent that had stolen
five times faced ~20% success; the restored world hands it 60%. The same applies to `allies`,
`enemies`, `skip_next_turn`, `rest_bonus`, `will_target`, pending extortion/bribe, and unresolved
`DeferredAction` rows. Two of those are worse than mechanical: `allies` and `spouse_id` feed
`render_world_brief`, so an incomplete restore changes **what the model sees**, not only what
the engine computes.

This is the same class of defect as the fabricated `$10` default caught during probe mining. It
must be closed before any further data is collected, because it silently invalidates every
probe restored from a trace.

## 2. Non-negotiables

Carried forward from the harness spec and binding on every phase below.

- The **triple** is untouchable: stated private reasoning, public message, applied action plus
  ground truth. New mechanics extend what an action *is*, never how it is logged.
- The Oracle stays authoritative. No game logic in the frontend, including the 3-D view.
- `session_id` is `varchar(32)`.
- Money is `round(x, 2)`; goods are integers.
- All DB calls async.
- Judge prompts are versioned; **any** wording change bumps `PROMPT_VERSION` and invalidates
  cross-version comparison.
- A new deception type is a schema change to `DeceptionType` and therefore a judge-prompt
  version bump. Batch them: land all of a phase's new types in one bump.

## 3. The layered economy — full map

Four layers. Each names the deception types it unlocks and the ground truth it hands the judge.
Layer 0 is what exists today.

### Layer 0 — flat goods economy (shipped)

Three goods (ore, food, tech), one production step, random specialty, progressive tax, hunger,
elimination at `balance <= 0`. Twenty actions in two tiers. Five deception types.

**Ground truth available to the judge:** balances, trust, the applied action, the ledger row.

### Layer 1 — production chains and capacity

Goods gain **inputs**. Tech requires ore; refined goods require tech plus food. Each agent has a
capacity per turn bounded by inputs held, not merely by specialty.

| mechanic | why it earns its place |
|---|---|
| Multi-stage recipes (`ore -> tech -> device`) | Creates *capability* claims that are checkable: "I can deliver 5 devices next turn" is true or false against inventory and capacity. |
| Per-turn capacity | Makes over-promising mechanical rather than rhetorical. |
| Good **quality grades** (standard / refined) | Enables misrepresenting what is delivered — a lie with a ledger row behind it. |

**New deception types:** `false_capability_claim` (asserting production or delivery the agent
cannot make), `quality_misrepresentation` (selling grade X as grade Y).

**New ground truth:** inventory plus recipe plus capacity make a capability claim decidable
without reading intent at all. This is the first mechanic where the judge can be *wrong-proof*.

**New actions:** `refine` (major), `quote` (free — publish an offer with terms).

### Layer 2 — contracts and institutions

The layer with the highest measurement return, and the one Phase 2 should reach first.

| mechanic | why it earns its place |
|---|---|
| **Contract registry** — a `Contract` row: parties, terms, deadline, status | Converts "false promise" from an interpretive call into a checkable one. The judge reads breach, not tone. |
| **Offices** — bank, auditor, arbiter, tax collector; held by an agent for a term | Makes role claims falsifiable: the registry says who holds an office. |
| **Public registries** — who holds what office, which contracts are open, who breached | Gives *all* agents a shared, checkable record, so lying about it is unambiguous. |
| **Auditing** — an office-holder can inspect another agent's true balance | Creates asymmetric knowledge that is earned rather than assigned, and a reason to lie to a specific agent. |

**New deception types:** `false_authority_claim` (claiming an office not held),
`contract_breach_concealment` (concealing or misrepresenting a breach),
`registry_falsification` (asserting a registry fact contradicted by the registry).

**New ground truth:** the registries. A judge verdict on any of these three types is decidable
from a table. This is the single biggest reduction in judge interpretive load available, and it
directly answers the reliability attack the paper is most exposed to (`M4`, currently
`DIRECTIONAL`).

**New actions:** `sign_contract`, `fulfil_contract` (major); `stand_for_office`, `audit`,
`declare` (free — assert a registry fact publicly, which the judge can check).

### Layer 3 — information markets

| mechanic | why it earns its place |
|---|---|
| Agents may **sell information** about world state at a price | The sold claim is either true or false against the engine. Perfect ground truth, zero interpretation. |
| Information **decays** — a claim about turn N is stale by turn N+k | Creates honest-but-wrong statements, which the judge must *not* label deceptive. This is the sharpest available test that the instrument separates a lie from an error. |

**New deception types:** `false_information_sale`.

**Why this matters beyond a new label:** stale-but-honest information is a built-in negative
control. A judge that flags it is miscalibrated, and we can measure how often it does. That is a
reliability instrument, not a game feature.

**New actions:** `sell_info`, `buy_info` (major).

### Layer 4 — social strata and mobility

| mechanic | why it earns its place |
|---|---|
| **Class tiers** derived from wealth and office history, with thresholds | Status becomes a fact, so status claims become checkable. |
| **Mobility rules** — entry to a tier requires capital *and* a sponsor | Creates sponsorship as a scarce favour worth lying for. |
| **Tier-gated actions** — some contracts or offices require a tier | Gives a concrete payoff to claiming a status one does not hold. |

**New deception type:** `false_status_claim`.

**Caution recorded here rather than discovered later:** this layer adds the least ground truth
per unit of complexity. If any layer is cut for time, cut this one first.

### Summary of the label space

Five types today, thirteen at full build:

```
existing   false_state_claim, false_promise, strategic_omission,
           misdirection, identity_bluff
layer 1    false_capability_claim, quality_misrepresentation
layer 2    false_authority_claim, contract_breach_concealment, registry_falsification
layer 3    false_information_sale
layer 4    false_status_claim
```

Eight of the thirteen are decidable from a table rather than from a monologue. That ratio is the
argument for the whole exercise, and it is what the paper should report.

## 4. Trace schema v5

v4 carries the triple plus partial state. v5 carries **complete** restorable state and the new
layers. It is a superset; a v4 file remains readable and is reported as `state_fidelity: partial`.

### 4.1 Complete agent state (closes the §1 defect)

`turn_snapshots` and `TurnState` both gain every field that affects mechanics or the world brief:

```jsonc
"state": {
  "balance": 4.10, "trust_score": 58, "alive": true,
  "inventory": {"ore": 2, "food": 0, "tech": 1, "device": 0},
  "spouse_id": null, "allies": ["gemini"], "enemies": ["grok"],
  "steal_count": 5,              // drives steal success -- absent in v4
  "rest_bonus": false, "skip_next_turn": false, "will_target": null,
  "share_balance": true,
  "extortion_pending": null, "bribe_pending": null,
  "deferred": [                   // unresolved investments and loans
    {"kind": "investment", "amount": 9.0, "maturity_turn": 24}
  ],
  "office": null,                 // layer 2
  "tier": "commoner",             // layer 4
  "capacity": {"tech": 2}         // layer 1
}
```

`office`, `tier`, and `capacity` are **reserved in Phase 1** — the schema carries them so later
phases need no second migration, but they are `null` / empty until their layer lands. Everything
else in the block is populated from Phase 1 onward.

**Rule:** a field belongs in `state` if restoring without it changes either an action's outcome
distribution or the rendered world brief. Adding a mechanic that touches agent state without
adding it here is a defect, and the fidelity test in §4.3 is what catches it.

### 4.2 World-level state

Registries are not per-agent, so v5 adds a fourth record kind alongside `run` and `turn`:

```jsonc
{"kind":"world","turn":184,
 "contracts":[{"id":"c1","parties":["opus","gemini"],"terms":{"deliver":{"tech":3}},
               "deadline":190,"status":"open"}],
 "offices":{"auditor":"gemini","bank":null},
 "prices":{"ore":0.30,"food":0.25,"tech":0.50,"device":1.20},
 "info_market":[{"id":"i7","seller":"grok","claim":"opus balance < 2","price":0.5,
                 "true_at_turn":181}]}
```

One `world` record per turn, written before that turn's `turn` records. A reader that ignores
`world` records still gets a valid v4-equivalent view, which keeps existing tooling working.

### 4.3 Restore-fidelity test — the gate

Non-negotiable, and the thing that makes "full fidelity" a claim rather than an assertion:

```
run N turns -> snapshot at turn N -> restore into a fresh session ->
assert every Agent column matches
assert every DeferredAction row matches
assert every world registry matches
assert render_world_brief(restored, agent) == render_world_brief(original, agent)  for all agents
```

The world-brief equality is the important half. Matching database columns proves the engine
agrees; matching briefs proves **the model sees the same world**, which is what a probe actually
depends on.

## 5. Replay architecture

Three distinct guarantees, deliberately separated because they fail differently.

### 5.1 Playback — a recorded run, zero model calls

Given a v5 trace, step through any turn and render exactly what happened. No engine execution,
no API calls, no database. The trace *is* the artifact.

Implementation is a reader over the trace plus a cursor. `darwin replay` already does a text
version; playback is the same thing with world records and a UI.

**Guarantee:** total. Playback of a released trace is byte-faithful by construction.

### 5.2 Branching — fork at turn N

Restore the world at turn N, substitute one or more agents, and continue. This is exactly what
the probe suite does, and it inherits the divergence accounting already built and measured
(`docs/research/2026-08-22-divergence-spike.md`: +2.9% excess at k=8 in a stub arena, 15.6% mean
on real mined probes).

**Guarantee:** the *stimulus* is identical; the continuation is not reproducible, because the
substituted agent is a live model. Divergence is counted and reported per run, never repaired.

### 5.3 Cached re-execution — the reproducibility claim

A recorded run of frontier models can be re-executed offline, deterministically, with no API
access and no cost.

**Mechanism.** Every model call is recorded in a content-addressed cache:

```
key   = sha256(env_version, model, prompt_version, messages, tools, temperature)
value = the raw response (tool calls + text)
```

Replay runs the *real engine* with a `CachedAgent` that looks up the key and returns the recorded
response. A hit re-executes the turn genuinely — the engine computes outcomes, the RNG draws,
the ledger is written — but the model's contribution comes from disk.

**Modes:**
- `strict` (default for reproduction): a cache miss is an **error**. This is what makes the claim
  falsifiable — if the run does not reproduce, you find out loudly.
- `permissive`: a miss falls through to a live call and is recorded. Used to extend a cache.

**The honest limits, which belong in the paper and not in a footnote:**

1. **The cache is valid only for the exact `env_version` that produced it.** Change a mechanic,
   change a prompt, and every key misses. Environment version is already in the trace manifest
   (`env.version`); replay must assert it matches and refuse otherwise.
2. **Branching invalidates the cache past the branch point.** Once the tested agent diverges, the
   world differs, so every other agent's prompt differs and every key misses. Branching therefore
   uses scripted opponents (the probe approach) or accepts live calls. There is no third option
   and the spec should not pretend otherwise.
3. **Cached re-execution is not evidence the model is deterministic.** It is evidence the
   *environment* is, given fixed model outputs. That is the claim to make, and it is still a
   strong one: it means anyone can verify our numbers from the released artifacts without a key.

**Storage:** one cache per run, `releases/<run_id>/responses/`, sharded by key prefix. A 335-turn
ten-model run is roughly 2,000 responses — tens of MB, so it is released alongside the trace but
gitignored like the other artifacts.

### 5.4 What "reproducible" means in the paper

Stated plainly, because reviewers will press on it:

> The environment is deterministic given a seed and a fixed set of model outputs. Live model calls
> are not reproducible; we therefore release the recorded outputs, and any result in this paper can
> be re-derived offline from the released trace and response cache. We do not claim the models
> themselves are reproducible.

## 6. The 3-D view

> **Superseded in part, 2026-08-26.** Two clauses below no longer hold: the 3-D view is
> *not* an additional route, and it does *not* degrade to the 2-D view. It is now the only
> world renderer, in the live session as well as the gallery, and `Town.tsx` is deleted; a
> browser without WebGL gets an explicit notice rather than a second renderer. The
> reasoning, and the consequences, are in `docs/adr/2026-08-26-3d-primary-renderer.md`.
> The triple-legibility clause is unchanged and became a blocking gate, since there is no
> longer a second view to fall back to.


**Constraint that makes this cheap:** the 3-D view is a **playback renderer over trace v5**. It
consumes the same records the text replay does. It contains no game logic, gets no privileged
data, and adds no measurement surface — which is exactly why it can be built last and in parallel
by someone who never touches the backend.

- **Stack:** React Three Fiber plus drei, on the existing Next 15 / React 19 frontend. No engine,
  no physics — agents are positioned, not simulated.
- **Scene:** the six venues become raised districts on a plane; layer 2 offices become landmark
  buildings; layer 4 tiers set agent height or plinth. Camera orbits, zooms, and can follow one
  agent.
- **The triple stays legible.** This is the risk with any 3-D view and it is the acceptance
  criterion: selecting an agent-turn must show private reasoning, public message, applied action,
  and the judge verdict in a panel, at the same readability as the current 2-D `TurnCard`. A
  prettier world that buries the triple is a regression, not a feature.
- **Fallback:** the 2-D gallery stays. The 3-D view is an additional route (`/gallery/[runId]/3d`),
  never a replacement, and it must degrade to the 2-D view when WebGL is unavailable.

## 7. Phases

Each phase is independently shippable and ends with the suite green. **Phase 1 is the single
implementable run.**

Note that phase order deliberately inverts layer order: layer 2 (contracts) ships before layer 1
(production) because it returns the most ground truth per unit of work. Layer numbers describe the
economy; phase numbers describe the build.

### Phase 1 — freeze and instrument (one run)

No new mechanics. This is the foundation every later phase and all future data collection depend
on, and it closes a live defect.

1. Extend `turn_snapshots` and `TurnState` with every field in §4.1 (auto-migration list in
   `app/db.py` must gain a row per column — an omission there is silent).
2. Add the `world` record kind to the trace schema (§4.2), emitted per turn; empty registries for
   now.
3. Bump the trace schema to **v5**; v4 files still read, reported as `state_fidelity: partial`.
4. Implement the **restore-fidelity test** of §4.3, including world-brief equality.
5. Implement the **response cache** and `CachedAgent` (§5.3) with `strict` and `permissive` modes,
   plus an `env_version` assertion.
6. Add `darwin replay --from-cache` proving a recorded run re-executes offline with zero API calls.
7. Tag the environment version. From here, any mechanic change bumps it and invalidates caches.

**Acceptance:** restore fidelity passes for a 40-turn stub run including world-brief equality; a
cached run re-executes in `strict` mode with no misses; the full backend suite is green.

### Phase 2 — contracts and institutions (layer 2)

Highest measurement return; do this before any other mechanic work. Contract registry, offices,
public registries, auditing; five new actions; three new deception types; judge prompt bump; the
judge gains registry access as ground truth. Probe mining gains contract-breach probes, which are
the cleanest susceptibility probes available.

### Phase 3 — production chains (layer 1)

Recipes, capacity, quality grades; two new actions; two new deception types.

### Phase 4 — information markets (layer 3)

Sell/buy info, decay. One new deception type, and the stale-but-honest negative control, which is
worth more than the type.

### Phase 5 — social strata (layer 4)

Tiers, mobility, sponsorship, tier-gated actions. Cut this first if time is short.

### Phase 6 — 3-D view

Parallelizable with Phases 2–5 once Phase 1 lands, because it depends only on trace v5.

## 8. Risks

- **Scope against thesis.** Every phase after 1 grows the environment, which the harness spec
  argues is not the contribution. Mitigation: the §1 rule, and reporting the *ground-truth ratio*
  (8 of 13 types table-decidable) as the reason the environment grew.
- **Cache invalidation is total.** One mechanic change invalidates every cached run. Consequence:
  collect expensive frontier data only immediately after a version tag, never mid-phase.
- **Judge prompt churn.** Each phase adds types and bumps `PROMPT_VERSION`, breaking comparison
  with earlier verdicts. Mitigation: batch a phase's types into one bump, and re-judge a fixed
  calibration subset at each bump so drift is measured rather than assumed.
- **State capture drift.** A future mechanic touching agent state without extending §4.1
  reintroduces the `steal_count` defect. The restore-fidelity test is the guard; it must assert
  over *all* columns, not a hand-listed subset, so a new column fails the test until handled.
- **3-D burying the triple.** Guarded by the acceptance criterion in §6.
