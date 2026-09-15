# CLAUDE.md -- Project Darwin

LLM economic survival simulation **and deception-measurement harness**. 3-10 agents compete with 25 actions (work, trade, steal, deceive, socialize, contracts, offices) in a goods economy with trust scores, progressive taxation, information asymmetry, and public registries. Users configure agents from the UI -- no hardcoded roster.

The measurement half is the contribution: a portable trace schema, an intent-grounded judge, coherence metrics with a permutation null, a frozen-stimulus probe benchmark, and deterministic offline replay. See `docs/HOW-TO-RUN.md` to operate it and `docs/superpowers/specs/` for the design.

## Architecture

```
Next.js (React)  <-- WS/REST -->  FastAPI (Oracle)  --> Postgres
                                    turn loop + parallel decide()
                                    25 action handlers
                                    trust, goods, tax, deferred actions
                                  --> OpenRouter (one OpenAI-compatible gateway to every model)
```

The Oracle is authoritative. Frontend is a pure viewer. No game logic in the frontend.

**Multi-tenancy:** the server hosts many isolated **sessions** at once. Every row
(`agents`, `transactions`, `thoughts`, `world_events`, `deferred_actions`, `api_keys`) is
scoped by `session_id`; `Agent`'s PK is composite `(session_id, agent_id)`. Anonymous
shareable sessions live at `/session/{id}` in the UI. Per-session BYOK keys are encrypted at
rest and never shared. Live per-session state (turn lock + decrypted roster) lives in
`app/runtime.py::SessionRegistry` (single-process); the DB is the source of truth and sessions
reload lazily after a restart. See `docs/superpowers/specs/2026-06-01-multi-tenant-sessions-design.md`.

## Repo layout

```
shared/                   # SSOT read by BOTH the engine and the renderer
  venues.json             # 21 venues: district, status, generated x/y, actions[]
  actions.json            # every action: tier, family, venue, beats, summary
  goods.json              # goods and base prices
  economy.json            # tax brackets, tax cycle, walk speed, stage size

backend/
  app/
    config.py             # Settings (no hardcoded roster)
    db.py                 # Async SQLAlchemy + auto-migration for new columns
    main.py               # FastAPI routes, config/export/reset endpoints
    ws.py                 # WebSocket broadcaster
    thought_export.py     # Streaming JSONL exporter
    models/
      agent.py            # Agent ORM: balance, trust_score, steal_count, inventory, specialty, social state
      ledger.py           # Transaction, ThoughtLog (with public_message), WorldEvent
      deferred.py         # DeferredAction (investments, loans)
      api_key.py          # Fernet-encrypted API key storage
    oracle/
      schemas.py          # 25 tool schemas (Pydantic), MAJOR_ACTIONS/FREE_ACTIONS sets
      actions.py          # 25 do_* handlers + ACTION_TABLE
      engine.py           # run_turn (legacy lockstep loop), progressive tax, deferred settlement, extortion enforcement, inheritance
      clock.py            # Fixed-point simulation time. BEAT = 1000 ticks
      scheduler.py        # The event queue: wakes, interrupts, agent_seq, lockstep policy
      durations.py        # How long an action occupies you; deliberation charged from tokens
      world_data.py       # Loads shared/; the Pydantic models are the schema
      space.py            # Venues, travel time, who witnessed what
      accrual.py          # Tax and hunger as continuous rates, settled on beat boundaries
      event_engine.py     # run_events: the continuous loop that replaced the turn
    agents/
      base.py             # BaseAgent, AgentDecision (major + free action), system prompt, info-asymmetric world brief
      stub.py             # StubAgent with DEFAULT_BIAS for all 25 actions (internal: tests/CLI only)
      openai_agent.py     # OpenAI-compatible client; every real model runs through OpenRouter via base_url
      factory.py          # build_agents(roster): provider="stub" -> StubAgent, else OpenRouter; per-session key

frontend/
  app/session/[sessionId]/page.tsx  # Live view: header, 3-D world, roster, public/private logs
  app/gallery/[runId]/3d/page.tsx   # Replay view: 3-D world, turn scrubber, triple panel
  components/
    three/
      WorldScene.tsx        # Canvas, lights, ground, auto-fitting camera; renders a WorldFrame
      VenueBlock.tsx        # One venue as a building: door, windows, roof, sign
      AgentPawn.tsx         # One agent, walking to wherever this turn put it
      AgentBody.tsx         # The person: head, torso, arms and legs that swing
      FirstPersonControls.tsx # Pointer lock + WASD; you, standing in the town
      ProximityFocus.tsx    # Reports whoever you are standing in front of
      TriplePanel.tsx       # Selected agent-turn: reasoning, message, action, verdict
      TurnScrubber.tsx      # Replay transport (step / scrub / play)
    Triple.tsx              # Channel + VerdictRow, shared by TurnCard and TriplePanel
    Sidebar.tsx             # Agent cards: balance, invested, trust bar, inventory, specialty, social, badges
    PublicLog.tsx           # Public feed (actions + public_message broadcasts)
    ThoughtLog.tsx          # Private reasoning (observer only)
    ConfigPanel.tsx         # Agent setup modal: model, color, API key, personality
    Avatar.tsx              # The roster head shown beside an agent's name
  lib/worldData.ts        # Reads shared/ through the @shared alias; types + lookups
  lib/frame.ts            # WorldFrame: one view-model built from a live snapshot or a trace
  lib/firstPerson.ts      # Eye height, walk speed, collision against the venue blocks
  lib/motion.ts           # Walking an agent from last turn's venue to this one's
  lib/proximity.ts        # Who you are close enough to, and facing, to be reading
  lib/gait.ts             # Body proportions and the walk cycle, driven by ground covered
  lib/architecture.ts     # What each venue is built like, sized against the collision box
  lib/town.ts             # Venues, action->venue table, agent palette
  lib/ws.ts               # Types (AgentSnap, ThoughtSnap, WorldSnapshot, PausedEvent) + WS connection
```

**The world is 3-D and you stand in it.** Both views open on foot — pointer lock to look,
WASD to walk, an `overview` toggle for the orbiting camera — and you read an agent by
walking up to it rather than clicking it. Agents walk between venues as turns land. One
renderer, fed by `lib/frame.ts`, so the live session and a replayed run cannot disagree
about where an agent stood. There is no 2-D fallback: a browser without WebGL gets an
explicit notice and links to the run as data.
See `docs/adr/2026-08-26-3d-primary-renderer.md`.

## Time

**There are no turns.** The world runs on a discrete-event clock and agents wake at their
own pace. See `docs/adr/2026-08-30-continuous-event-clock.md`.

- **Three coordinates, not interchangeable.** `event_id` is the global total order and the
  trace's primary key. `tick` is simulation time (fixed-point, `BEAT = 1000` ticks) and
  drives economic accrual. `agent_seq` is how many times *that agent* has acted.
- **All deception-coherence gaps are measured in `agent_seq`.** Measured in `event_id` a
  gap mostly counts other agents acting and this one sleeping; tested against the 335-turn
  verdict set that inflates `max_return_gap` by ~380 on a 0-200 baseline. Run rows through
  `measure/coherence.by_agent_seq` first. `tests/test_coherence_scheduling_invariance.py`
  pins this.
- **Agents schedule themselves.** Every tool call carries `wake_after` (beats to sleep) and
  `wake_if` (triggers that wake it early, validated against `scheduler.WAKE_TRIGGERS`). A
  prompt is only sent when an agent wakes, so cost tracks activity.
- **Actions and thinking both cost time.** Action duration comes from `durations.ACTION_BEATS`;
  deliberation is charged from tokens spent, never from measured latency -- wall-clock never
  enters the simulation, so a slow model and a fast one produce identical traces.
- **Tax and hunger accrue continuously**, settled on whole-beat boundaries so the bill does
  not depend on how finely events chopped up time. Sleeping does not pause the drain.
- **`policy="lockstep"`** gives every agent a one-beat wake, ignores duration, and disables
  interrupts -- the old turn loop as a configuration, kept so frozen-stimulus probes run.

## Game mechanics

- **25 actions** in 2 tiers: major (required, 1/turn) + free (optional, 1/turn alongside major)
- **Buildings own actions**: every action belongs to a venue, and the prompt describes
  the building the agent is standing at in full plus every other building in one line
  with its walk cost. Any action is still callable from anywhere -- you pay the walk.
  `shared/venues.json` is the table; 7 venues are built and 14 more are placed but
  `planned`, awaiting their content pack.
- **Contracts and offices**: `sign_contract` binds on proposal; missing the deadline is recorded as a breach. Offices (bank/auditor/arbiter/collector) are takeable while vacant for 20 turns. `declare` asserts a registry fact and the engine records asserted beside actual.
- **Goods economy**: 3 goods (ore $0.30, food $0.25, tech $0.50). Each agent has a random specialty (produces 2-3x). Food consumed every tax cycle or $1 penalty.
- **Progressive tax**: 0% on $0-2, 5% on $2-5, 10% on $5-10, 15% on $10-20, 20% on $20+. Invested capital exempt. 3+ agents striking waives tax. Charged as a per-beat rate; a continuous drain compounds within the cycle, so effective take is ~1/3 below the old ten-turn cliff at $10.
- **Trust score** (0-100): affects trade acceptance. Modified by slander (-5 to -10), vouch (+5), steal (-3 to -5), trade (+1), loan default (-10).
- **Info asymmetry**: agents only see own balance + spouse/allies. Others show fuzzy range. Gaslight injects fake events.
- **Steal nerf**: success 60% - 8%/attempt (min 15%). Penalty $2 base + $0.50/attempt.
- **Marriage**: mutual consent (two proposals). Pools balances. +10% work. Divorce splits 50/50.
- **Bankruptcy**: any agent with `balance <= 0` is eliminated at end of turn -- every turn, not only on tax cycles. Invested capital and goods do not protect them.
- **Inheritance**: will target gets 50%, spouse gets 100%. No heir = assets + goods lost.
- **Deferred actions**: invest (5 turns, 70% success at 1.2-2x) and lend (5 turns, 1.1x repayment). Extortion auto-triggers next turn.
- **Parallel execution**: all agent decide() calls run concurrently (120s timeout). Decisions applied sequentially.

## Adding a new action

1. `shared/actions.json` -- one row: id, tier, family, venue, beats, emoji, intent, summary
2. `shared/venues.json` -- add the id to that venue's `actions` list
3. `oracle/schemas.py` -- Pydantic model inheriting `_BaseArgs`, registered in `ARG_MODELS`
4. `oracle/actions.py` -- `do_<name>()` handler + `ACTION_TABLE` entry
5. `agents/stub.py` -- `DEFAULT_BIAS` weight + argument generation in `_pick_major()`

`tests/test_world_data.py` fails if any of these are missing. The prompt, the tool
schema, the duration, the venue and the building's sign all follow from step 1 --
there is nothing to update in the frontend or the system prompt.

## Key conventions

- Money always `round(x, 2)`. Goods are integers.
- All DB calls async. No sync SQLAlchemy anywhere.
- Agent identity = color (red, blue, green, etc.), not sprite names.
- Agents call 1-2 tools: first = major action, second = optional free action. Engine validates free action is in `FREE_ACTIONS` set.
- Provider agents extract `reasoning` from tool args as monologue, `public_message` saved to ThoughtLog.
- Factory falls back to StubAgent if API key missing. Never raises.

## Run

```bash
cp .env.example .env
docker compose up --build     # http://localhost:3000
docker compose down -v        # fresh reset (drops DB volumes)
```

## REST API

All simulation endpoints are scoped to a session id. `GET /providers` and `GET /health` are global.

- `POST /sessions` -- create an empty session, returns `{session_id}`
- `POST /sessions/{id}/configure` -- set up 3-10 agents + per-provider BYOK `keys`; resets only this session
- `POST /sessions/{id}/run?turns=N` -- run N turns (parallel agent calls)
- `POST /sessions/{id}/turn` -- single turn (debug)
- `POST /sessions/{id}/reset` -- wipe only this session (keeps the id so links survive)
- `GET /sessions/{id}/state` -- full snapshot (includes invested capital for moderator)
- `GET /sessions/{id}/ledger` / `GET /sessions/{id}/events`
- `GET /sessions/{id}/export/thoughts` -- JSONL download (queried live from the DB)
- `POST /sessions/{id}/agents/{aid}/remove` -- eliminate failing agent
- `POST /sessions/{id}/simulation/resume` -- clear errors and continue
- `WS /ws/{id}` -- live per-session event room
- `GET /providers` -- provider list + color options (global)

## Things NOT to do

- Don't bypass the Oracle. All mutations go through `actions.py` + `engine.py`.
- Don't hardcode agent IDs, sprite names, or model IDs.
- Don't add sync DB calls. Everything is async.
- Don't log or expose raw API keys.
- Don't import `agents/factory` at module level in `engine.py` (lazy import).
