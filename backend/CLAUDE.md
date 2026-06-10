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
- **`oracle/schemas.py`** -- 20 Pydantic models (all inherit `_BaseArgs` with `reasoning` + `public_message`). `TOOL_DEFINITIONS`, `ARG_MODELS`, `FREE_ACTIONS`, `MAJOR_ACTIONS` sets.
- **`oracle/actions.py`** -- 20 `do_*` handlers + `ACTION_TABLE`. All return `ActionResult`.
- **`oracle/engine.py`** -- `run_turn()` (parallel decide, sequential apply), `_process_deferred()` (investments, loans, extortion), `_apply_survival_tax()` (progressive brackets, food consumption, strikes, inheritance).
- **`agents/base.py`** -- `AgentDecision` (major + free action fields), aggressive system prompt, `render_world_brief()` with info asymmetry (fuzzy balances, gaslight injection).
- **`agents/stub.py`** -- `StubAgent` with `DEFAULT_BIAS` for 20 actions. `_pick_major()` + 40% chance free action.
- **`agents/openai_agent.py`** -- OpenAI-compatible client; extracts 1-2 tool calls. Every real model is reached through **OpenRouter** (`base_url`). `stub.py` is internal-only (tests/CLI). Providers other than OpenRouter were removed.
- **`models/agent.py`** -- Agent ORM: balance, trust_score, steal_count, specialty, inventory, social state, will_target, extortion/bribe pending.
- **`models/deferred.py`** -- DeferredAction for investments/loans maturing over turns.
- **`models/api_key.py`** -- Fernet-encrypted API key storage.
- **`thought_export.py`** -- Streaming JSONL exporter (schema v2 with timestamp).
- **`judge/`** -- Phase 2 offline LLM judge: `runner.py::judge_session` batch-judges a
  session's triples into `deception_judgments` (keyed by session/turn/agent/judge_model/
  prompt_version/sample_idx). `stub_judge.py` = deterministic offline judge for tests.
  Never runs inside the turn loop. CLI: `python -m scripts.judge_deception`.
- **`metrics.py`** -- structural metrics + optional `judged_deception` block
  (`scripts/compute_metrics.py` CLI).

## Adding a new action

1. `schemas.py` -- Pydantic model (inherit `_BaseArgs`) + `TOOL_DEFINITIONS` + `ARG_MODELS` + add to `FREE_ACTIONS` or `MAJOR_ACTIONS`
2. `actions.py` -- `do_<name>()` handler + `ACTION_TABLE`
3. `stub.py` -- `DEFAULT_BIAS` weight + argument generation in `_pick_major()`
4. `base.py` -- system prompt (MAJOR or FREE section)
5. Frontend `WorldMap.tsx::ACTION_VENUE` -- map to venue

## Action tiers

- **Major** (1 required/turn): work, trade, bet, invest, steal, lend, sabotage, extort, bribe, socialize
- **Free** (0-1 optional/turn): vouch, will, rest, strike, bluff, propose_deal, slander, gaslight, gift, charity
- Free actions can be used as major. Major cannot be used as free.
- Engine validates `free_action in FREE_ACTIONS` before applying.

## Economy

- Goods: ore, food, tech. Each agent has a random specialty (2-3x production).
- Food consumed every 10 turns or $1 penalty. Pure trade commodity otherwise.
- Progressive tax: 0% ($0-2), 5% ($2-5), 10% ($5-10), 15% ($10-20), 20% ($20+). Invested capital exempt.
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
