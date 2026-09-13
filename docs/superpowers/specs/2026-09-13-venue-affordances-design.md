# Venue affordances — one table for buildings, actions, and the sign on the door

Status: approved, not yet implemented.
Prerequisite for the four content packs listed under "Out of scope".

## Problem

The town has six buildings and they are decoration. `space.py::ACTION_VENUE`
maps an action to a venue so travel costs something and a witness list is
decidable, but nothing about a building tells an agent — or a viewer — what
that building is for. The agent receives one flat list of 25 actions and the
building receives a nameplate.

That is survivable at six buildings. It is not survivable at twenty. Growing
the world into a full social economy means roughly fifty actions across twenty
venues, and today an action id has to be declared in four places that can
silently disagree:

| Place | What it declares |
|---|---|
| `oracle/schemas.py` | `MAJOR_ACTIONS` / `FREE_ACTIONS`, arg model, tool description |
| `oracle/durations.py` | `ACTION_BEATS` |
| `oracle/space.py` | `ACTION_VENUE` |
| `frontend/lib/town.ts` | family, emoji, venue, intent |

A fifth, `agents/stub.py::DEFAULT_BIAS`, decides whether the offline stub can
even produce the action. An action missing from any one of them half-exists:
it runs but is drawn in the wrong place, or it is drawn but the stub never
emits it, so no replay test ever covers it.

## Decisions

Four questions were settled before this document:

1. **The venue's action list is the source of truth**, not signage over a flat
   list. One table feeds the prompt, the engine, and the building's sign.
2. **Location gates by distance only.** Calling `invest()` from the alley
   charges the walk to the bank and then resolves. No action is ever rejected
   for being in the wrong place.
3. **All four content packs are wanted**, so the mechanism ships first and the
   packs land on top of it independently.
4. **Prompt is venue-scoped prose over a full tool list.** Every tool stays
   callable — decision 2 requires it — but the prose describes the current
   building in full and every other building in one line.

## Single source of truth

A new top-level `shared/` directory holds the data both the engine and the
renderer must agree on. Logic only the engine evaluates stays in Python.

```
shared/
  venues.json     # id, label, district, status, x, y, actions[]
  actions.json    # id, tier, family, venue, beats, emoji, intent, summary
  goods.json      # id, base_price
  economy.json    # tax brackets, tax cycle beats, walk units per beat
```

Python reads them through a new `app/oracle/world_data.py`; TypeScript imports
them through `lib/worldData.ts` under a `@shared` path alias, registered in
`tsconfig.json`, `next.config.js` and `vitest.config.mts`.

The Pydantic models in `world_data.py` are the authoritative schema — a
malformed row raises at import, so the Oracle refuses to start rather than
serving a half-loaded world. TypeScript mirrors them as interfaces and a vitest
test asserts every row satisfies them. No JSON Schema files and no new
dependency on either side; Pydantic is already there and a second schema
language would be a third place for the truth to live.

### What moves

- `space.py::VENUE_POS` and `ACTION_VENUE` — positions come from
  `venues.json`; `ACTION_VENUE` becomes the derived inverse of each venue's
  `actions[]`, which makes it impossible for an action to belong to two
  buildings or to none. `space.py` keeps `travel_ticks`, `Placement`,
  `witnesses`, `observable_by`.
- `durations.py::ACTION_BEATS` — reads the `beats` column.
- `schemas.py::MAJOR_ACTIONS` / `FREE_ACTIONS` — derived from the `tier`
  column. `GOODS` and `GOOD_VALUES` read `goods.json`.
- `accrual.py::TAX_BRACKETS`, `TAX_CYCLE_BEATS` and
  `space.py::WALK_UNITS_PER_BEAT` — read `economy.json`.
- `town.ts::ACTIONS[].venue` and `VENUES[].x/y` — read from the JSON.

### What does not move

Pydantic arg models, `do_*` handlers, the tax and trust and steal formulas,
`capacity_beats_per_unit`, and every colour, emoji, intent verb and facade.
Cosmetics stay in `town.ts` and `architecture.ts`, keyed by venue id with a
default so an unstyled new venue renders plainly rather than crashing — the
same tolerance `actionDef` already gives an unmapped action.

### The `summary` column

One sentence per action, rendered in exactly two places: the prompt block for
the building the agent is standing at, and that building's sign in the 3-D
view. The human walking up to the Bank reads the string the model was given.
This is the point of the exercise; nothing else in the schema is allowed to
duplicate it.

### Invariants, as tests

- Every id in `actions.json` has an `ARG_MODELS` entry, an `ACTION_TABLE`
  handler, a `DEFAULT_BIAS` weight, and a venue that exists and is built.
- Every built venue's `actions[]` contains only ids present in
  `actions.json`, and every built action appears in exactly one venue.
- Every venue id in `venues.json` has cosmetics in `town.ts` or resolves to
  the default.
- Every row loads cleanly into its Pydantic model, and the mirrored vitest
  shape check passes over the same file.

Adding an action therefore becomes two steps — add the row, write the handler
— with CI proving the rest landed. The five-step checklist in `CLAUDE.md`
shrinks accordingly.

## The map

Twenty-one venue rows ship at once, each carrying `status: "built" |
"planned"`. Only `built` venues are rendered, prompted, and gated on. Packs
flip a status and add action rows; **no building ever moves**, so a trace
replayed after a pack lands still puts pawns where they stood.

| District | Ring | Venues |
|---|---|---|
| plaza | centre | plaza *(public — anything said here is heard town-wide)* |
| civic | inner | market, bank, lounge, **registry**, **courthouse**, **press**, **tavern** |
| industry | outer | work, **farm**, **mine**, **workshop**, **warehouse**, **academy**, **guild_hall** |
| vice | outer | alley, casino, **pawnshop**, **insurance**, **estate**, **temple** |

Bold rows ship as `planned` — reserving coordinates only. The seven built
venues carry their existing behaviour unchanged.

Two mergers are deferred to the packs that own them. Pack B retires `work`
into farm / mine / workshop; Pack D retires `lounge` into `tavern`. Each ships
an alias entry (`{"lounge": "tavern"}`) so a historical trace naming a retired
venue still resolves, rather than falling through `venueById` to whichever
venue happens to be first.

### Coordinates are generated

`scripts/layout_venues.py` places every row — planned included — on its
district ring in declared order and writes literal `x`/`y` back into
`venues.json`. Both readers consume plain numbers; nobody hand-tunes twenty
buildings, and adding a row cannot silently overlap an existing one.

Constants: footprint 78 stage px, gap 60 px, districts occupying contiguous
arcs so the town reads as neighbourhoods. With 7 inner and 13 outer that gives
roughly `Ri = 154`, `Ro = 285`, a 688 px square stage, and a longest crossing
near 570 px. The generator recomputes all of them; the numbers here are
illustrative.

Three invariants, as tests:

- no two footprints overlap
- plaza to any venue is at most 1.5 beats
- the longest crossing is 3.0 beats — `WALK_UNITS_PER_BEAT` is **derived** from
  the final layout to hold this, rather than left at 260 while the town
  changes size

`GROUND` becomes derived from stage width so a building stays 5.2 world units
as the stage grows. Camera auto-fit, fog distance and first-person walk speed
follow from it; a town twice as wide crossed at the old speed is a chore.

## Prompt

The flat action catalogue leaves `SYSTEM_PROMPT_TEMPLATE` and is replaced by a
venue block in `render_world_brief`, which is per-call state and therefore the
right home. The system prompt keeps objective, mechanics, time and scheduling,
and gets shorter.

```
YOU ARE AT: Bank (civic district)
  invest(amount)      Lock cash for 5 beats. 70% chance of 1.2-2x. Tax-exempt while locked.
  lend(target,amount) They get cash now, you get 1.1x back in 5 beats.
  audit(target)       Read an agent's exact balance. Requires the auditor office.
  will(target)        Set your heir.

ELSEWHERE (walk cost in beats from here):
  Market  0.8  trade sign_contract fulfil_contract charity gift bribe
  Lounge  1.1  socialize propose_deal rest vouch slander gaslight declare stand_for_office
  Casino  1.6  bet bluff
  Work    2.1  work strike
  Alley   2.4  steal sabotage extort
```

Walk costs are computed with `travel_ticks` from wherever the agent actually
stands, so the directory changes as it moves. Tool schemas stay complete and
unfiltered; their descriptions are trimmed to one line each now that the prose
carries the detail.

The agent's venue reaches `render_world_brief` as `state["_venue"]`, supplied
by `event_engine`'s `at_venue` map. That map is currently in-process only, so
a restart teleports everyone; a `venue` column on `Agent` (auto-migrated by
`db.py`) persists it, with the scheduler's map staying authoritative in-run.

## Frontend

- `lib/town.ts` reads `venues.json` / `actions.json` and keeps only cosmetics.
- `lib/world3d.ts` derives `GROUND` and the stage size from the venue data
  instead of hard-coding 780×560 and 26.
- `components/three/VenueBlock.tsx` renders the action ids on the facade board
  beneath the existing label.
- `components/three/ProximityFocus.tsx` extends from agents to venues, so
  standing at a building opens a HUD panel with the full `summary` lines and
  walk costs — the same text the agent received.
- `lib/architecture.ts::BY_VENUE` gains a facade per new venue, defaulting for
  any it does not know.

The renderer stays a pure viewer. Nothing on a building is clickable and no
action can be initiated from the frontend.

## Compatibility

- **`ENV_VERSION` bumps to `darwin-3.0`.** Venue-scoped prompts change every
  prompt, so every response-cache entry and every replay recorded against
  `darwin-2.0` is correctly invalidated.
- **Docker build contexts move to the repo root** (`context: .`,
  `dockerfile: backend/Dockerfile`, likewise for arena) so `shared/` is
  visible to both images. `.dockerignore` gains the exclusions each context
  previously got for free.
- v6 traces already carry an authoritative `venueId`, so replay is unaffected
  except for the retired-venue aliases described above.
- `policy="lockstep"` is untouched. Frozen-stimulus probes still run, and they
  now see the venue block, which is a prompt change the bumped `ENV_VERSION`
  accounts for.

## Testing

- Schema validation and the invariant set above, in pytest and vitest.
- Layout invariants: overlap, plaza reach, longest crossing.
- A prompt snapshot test pinning the venue block's shape for a known venue and
  agent position.
- `tests/test_coherence_scheduling_invariance.py` must still pass: nothing here
  touches `agent_seq`, and the gap measurement is unaffected.
- An end-to-end stub run over the seven built venues, asserting the trace's
  `venueId` matches what `ACTION_VENUE` derives.

## Out of scope

The four content packs, each its own spec, plan and branch:

- **Pack A — verification and enforcement.** Courthouse (`file_dispute`,
  `testify`, `rule`), Registry (`publish_ledger`, `contest_claim`), Press
  (publishing with reach, versus a whisper heard only by who is present).
  Sworn testimony is a claim the engine can score against ground truth, which
  is the highest-value pack for the deception measurement.
- **Pack B — supply chain.** Farm, Mine, Workshop, Warehouse. Specialty
  becomes geographic: the food producer stands somewhere others can watch, and
  an alibi about visiting becomes checkable.
- **Pack C — property, credit and risk.** Estate, Insurance, Pawnshop.
- **Pack D — status and information.** Tavern (gossip as a tradeable good,
  false gossip as a sellable product), Academy, Guild Hall, Temple.

Also out of scope: any human-driven action from the frontend, and any change
to the tax, trust or steal formulas.

## Risks

- **Prompt regression.** Replacing the flat catalogue changes behaviour in
  ways the venue block is meant to cause but could overshoot — an agent that
  never leaves the building it woke in. The stub run and a short live run
  should be compared on action diversity before packs land.
- **Docker context change** touches the build for both images at once. It is
  the only infrastructure change here and should be its own commit.
- **Twenty buildings on a 688 px stage is denser than six on 780×560.** If the
  first-person walker snags between buildings, the gap constant is the dial.
