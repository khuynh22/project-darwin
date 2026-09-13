# CLAUDE.md -- backend/

Python 3.12+. FastAPI + async SQLAlchemy 2.0 + Pydantic v2. **Everything is async.**

## Run

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt && cp .env.example .env
pytest                    # unit tests
uvicorn app.main:app --reload  # dev server (needs postgres)

# CLI simulation (sqlite, no server) — runs offline with stub agents
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite \
  python -m scripts.run_simulation --turns 50 --reset
```

## Where things live

- **`config.py`** -- Settings (pydantic-settings). No hardcoded roster. `get_settings()` is `@lru_cache`d.
- **`db.py`** -- Engine + SessionLocal + `init_db()` with auto-migration backfill for new columns.
- **`oracle/world_data.py`** -- loads `shared/{venues,actions,goods,economy}.json`. Pydantic models are the schema; a bad row raises at import so the Oracle refuses to start. Exposes `VENUES`, `ACTIONS`, `BUILT_VENUES`, `ACTION_VENUE`, `VENUE_ACTIONS`, `MAJOR_ACTIONS`, `FREE_ACTIONS`, `ACTION_BEATS`, `VENUE_POS`, `ECONOMY`.
- **`oracle/schemas.py`** -- 25 Pydantic arg models (all inherit `_BaseArgs` with `reasoning` + `public_message`) + `ARG_MODELS`. `TOOL_DEFINITIONS`, `FREE_ACTIONS`, `MAJOR_ACTIONS` and the goods table are derived from `world_data`.
- **`oracle/actions.py`** -- 25 `do_*` handlers + `ACTION_TABLE`. All return `ActionResult`.
- **`oracle/engine.py`** -- `run_turn()` (legacy lockstep loop, parallel decide, sequential apply), `_process_deferred()` (investments, loans, extortion), `_apply_survival_tax()` (progressive brackets, food consumption, strikes, inheritance).
- **`oracle/event_engine.py`** -- `run_events()`, the continuous loop that replaced the turn. Pops the next scheduled agent, accrues the economy for the elapsed span, applies the decision, fires interrupts, sleeps the agent for as long as it asked.
- **`oracle/clock.py`** -- fixed-point time. `BEAT = 1000` ticks; integers, not floats, because replay needs exact arithmetic.
- **`oracle/scheduler.py`** -- the priority queue. Ordering is `(tick, agent_id)`, never arrival order. Owns `agent_seq`, `WAKE_TRIGGERS`, and the `self_paced` / `lockstep` policies.
- **`oracle/durations.py`** -- `ACTION_BEATS` per action, plus deliberation charged from tokens spent (never from measured latency).
- **`oracle/space.py`** -- travel time and co-location witnesses. Positions and the action-to-venue map come from `world_data`; `scripts/layout_venues.py` generates the coordinates and derives `WALK_UNITS_PER_BEAT` so the longest crossing stays 3 beats.
- **`oracle/accrual.py`** -- tax and hunger as rates, settled on whole-beat boundaries so the bill is independent of event granularity.
- **`agents/base.py`** -- `AgentDecision` (major + free action fields), aggressive system prompt, `render_world_brief()` with info asymmetry (fuzzy balances, gaslight injection), and `render_venue_block()` -- the building you are standing at in full plus every other building in one line with its walk cost. The flat action catalogue is gone from the system prompt.
- **`agents/stub.py`** -- `StubAgent` with `DEFAULT_BIAS` for 25 actions. `_pick_major()` + 40% chance free action. Settles a satisfiable contract before rolling, and sizes commitments to inventory -- otherwise every contract breaches and breach carries no information.
- **`agents/openai_agent.py`** -- OpenAI-compatible client; extracts 1-2 tool calls. Every real model is reached through **OpenRouter** (`base_url`). `stub.py` is internal-only (tests/CLI). Providers other than OpenRouter were removed.
- **`models/agent.py`** -- Agent ORM: balance, trust_score, steal_count, specialty, inventory, social state, will_target, extortion/bribe pending.
- **`models/deferred.py`** -- DeferredAction for investments/loans maturing over turns.
- **`models/api_key.py`** -- Fernet-encrypted API key storage.
- **`thought_export.py`** -- Streaming JSONL exporter (legacy; trace v5 is written by `trace/`).
- **`judge/`** -- Phase 2 offline LLM judge: `runner.py::judge_session` batch-judges a
  session's triples into `deception_judgments` (keyed by session/turn/agent/judge_model/
  prompt_version/sample_idx). `stub_judge.py` = deterministic offline judge for tests.
  Never runs inside the turn loop. CLI: `darwin judge <trace> --out <verdicts>`.
- **`measure/`** -- coherence, permutation null, BH-FDR, structural metrics, and
  `calibration.py` (judge accuracy against turns whose truth is known by arithmetic).
  Pure over plain dicts; imports with no DB driver.
- **`trace/`** -- schema v5 (run manifest + per-turn triple and full state + world
  records), reader/writer/validator, and adapters. The portable contract.
- **`probe/`** -- frozen-stimulus benchmark: schema, replay with divergence
  accounting, mining, scoring.
- **`replay/`** -- content-addressed response cache and `CachedAgent`, so a
  recorded run re-executes offline with no API key.
- **`sweep/`** -- experiment specs, cell runner, resume, budget guard.
- **`models/registry.py`** -- `Contract` and `Office`: the tables that let the
  judge decide a claim by lookup instead of interpretation.

## Adding a new action

1. `../shared/actions.json` -- one row: id, tier, family, venue, beats, emoji, intent, summary
2. `../shared/venues.json` -- add the id to that venue's `actions` list
3. `schemas.py` -- Pydantic model (inherit `_BaseArgs`) + `ARG_MODELS`
4. `actions.py` -- `do_<name>()` handler + `ACTION_TABLE`
5. `stub.py` -- `DEFAULT_BIAS` weight + argument generation in `_pick_major()`

`tests/test_world_data.py` fails if any of these are missing. `TOOL_DEFINITIONS`,
the tier sets, the duration, the venue and the prompt all derive from step 1.

## Action tiers

- **Major** (1 required/turn): work, trade, bet, invest, steal, lend, sabotage, extort, bribe, socialize, sign_contract, fulfil_contract, audit
- **Free** (0-1 optional/turn): vouch, will, rest, strike, bluff, propose_deal, slander, gaslight, gift, charity, stand_for_office, declare
- Free actions can be used as major. Major cannot be used as free.
- Engine validates `free_action in FREE_ACTIONS` before applying.

## Time

No turns. See `docs/adr/2026-08-30-continuous-event-clock.md` and the Time section of the
root `CLAUDE.md`. The three rules that bite most often:

- Coherence gaps are measured in `agent_seq`, never `event_id`. Use `measure/coherence.by_agent_seq`.
- `_apply_decision` must strip `wake_after` / `wake_if` before dispatching to a handler --
  they are on `_BaseArgs`, so every tool call carries them.
- A new `Agent` column that changes an outcome distribution must be added to `TurnSnapshot`
  **and** `TurnState` **and** `probe/replay.py`, or `test_restore_fidelity` fails. That
  guard is reflection-based, which is how `steal_count` was caught, and `food_buffer` after it.

## Economy

- Goods: ore, food, tech. Each agent has a random specialty (2-3x production).
- Food drains continuously: 1 unit per 10 beats, else $0.10/beat hunger. `food_buffer` carries the fractional part. Pure trade commodity otherwise.
- Progressive tax: 0% ($0-2), 5% ($2-5), 10% ($5-10), 15% ($10-20), 20% ($20+). Invested capital exempt. Charged per beat, so it compounds within the cycle and takes ~1/3 less than the old cliff at $10.
- Steal: success = max(15%, 60% - 8% * steal_count). Penalty = max($2, $1 + $0.50 * steal_count).
- Loans: 1.1x repayment in 5 turns. Default = -10 trust for debtor.
- Bankruptcy: `_check_bankruptcies` runs at the end of every turn; any alive agent with `balance <= 0` is eliminated (estate = $0, inventory still transfers). Tax-time deaths still flow through `_apply_survival_tax` with the pre-tax estate.
- Inheritance: will = 50%, spouse = 100%. Goods also transfer. No heir = lost.

## Multi-tenancy

- Everything is scoped by `session_id`. `Agent` PK is composite `(session_id, agent_id)`; the
  other tables carry a `session_id` column. **Every** `select(...)`/`session.add(...)` in
  `oracle/` and `main.py` must filter/set it — reads funnel through `actions._get_agent` /
  `engine._get_agent_by_id`, writes through `actions._record`.
- `models/session.py::SimSession` owns `current_turn` + `balance_visibility` (were globals).
- `runtime.py::SessionRegistry` caches per-session `asyncio.Lock` + decrypted roster in memory
  (single-process), reloaded lazily from the DB on first access after a restart.
- API keys are per-`(session_id, provider)`, encrypted (`models/api_key.py`). Set `ENCRYPTION_KEY`
  in production or stored keys won't survive a restart (agents silently fall back to stub).
- `configure`/`reset` do a **scoped DELETE** — never `drop_all` (that would nuke every session).
- CLI (`scripts/run_simulation.py`) uses the fixed `config.CLI_SESSION_ID`.

## REST API

Session-scoped: `POST /sessions`, `POST /sessions/{id}/configure`, `/run?turns=N`, `/turn`,
`/reset`, `GET /sessions/{id}/state` (includes invested capital), `/ledger`, `/events`,
`/export/thoughts`, `POST /sessions/{id}/agents/{aid}/remove`, `/simulation/resume`,
`WS /ws/{id}`. Global: `GET /providers`, `GET /health`.

## Conventions

- Money: `round(x, 2)`. Goods: integers. Trust: 0-100 float.
- All decide() calls run in parallel (120s timeout). Decisions applied sequentially.
- Agent colors: red, blue, green, purple, orange, cyan, pink, yellow, teal, indigo. No legacy sprite names.
- Factory always falls back to StubAgent. Never raises.
- Don't import factory at module level in engine.py (lazy import to avoid cycles).
- Sessions carry an experimental `condition` (neutral|honesty|deception) that selects a
  locked system-prompt suffix (`agents/base.py`). Wording changes invalidate comparisons.
- Judge prompts are versioned (`judge/prompts.py::PROMPT_VERSION`) — bump on ANY edit.
