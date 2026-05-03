# CLAUDE.md — backend/

Python 3.12+ (tested on 3.13). FastAPI + async SQLAlchemy 2.0 + Pydantic v2. **Everything is async** — there are no sync DB calls anywhere.

## Run

```bash
# One-time
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env

# Dev server (needs Postgres)
docker compose up -d postgres
uvicorn app.main:app --reload

# Standalone simulation (sqlite, no server, no API keys)
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite STUB_MODE=true \
  python -m scripts.run_simulation --turns 100 --out thought_logs/run.jsonl --reset

# Tests
pytest                         # unit tests on action handlers
pytest -v tests/test_actions.py
```

`--reset` drops + recreates tables. Use it whenever the schema changes.

## Where things live

- **`config.py`** -- `Settings` (pydantic-settings, reads `.env`) + `AGENT_ROSTER` (default fallback roster). `get_settings()` is `@lru_cache`d, so env changes after import won't take effect until restart.
- **`db.py`** -- Module-level `engine` and `SessionLocal`. Tests build their own engine via `create_async_engine(":memory:")` -- they don't share the global one.
- **`oracle/`** -- All game logic. The engine never imports from `agents/` at module level (avoids cycles); it imports `factory` lazily inside functions.
- **`agents/`** -- One file per provider. They all return `AgentDecision(action, arguments, monologue)`. The engine validates `arguments` against `ARG_MODELS[action]` before dispatch.
- **`thought_export.py`** -- Streaming JSONL exporter. Activated on app lifespan; each `run_turn` appends rows if an exporter is active.
- **`models/api_key.py`** -- Fernet-encrypted API key storage. Keys stored/retrieved via `store_key()` / `get_key()`.
- **`models/deferred.py`** -- `DeferredAction` ORM for investments and loans that mature after N turns.

## Adding a new action

Wire it in these places, in order:

1. **`oracle/schemas.py`** -- Pydantic args model + entry in `TOOL_DEFINITIONS` + entry in `ARG_MODELS` dict
2. **`oracle/actions.py`** -- `async def do_<name>(session, *, turn, actor_id, **kwargs) -> ActionResult` + entry in `ACTION_TABLE`
3. **`agents/stub.py::PERSONALITY_BIAS`** -- give each personality a weight + add argument generation in `StubAgent.decide()`. Also update `DEFAULT_BIAS`.
4. **`agents/base.py::SYSTEM_PROMPT_TEMPLATE`** -- add a line in the TOOL SUMMARY section
5. **`frontend/lib/phaser/scene.ts::ACTION_VENUE`** -- map the action to a venue for animation

Current actions (10): work, trade, bet, socialize, sabotage, invest, steal, lend, charity, propose_deal.

Skip any of the first three and the action either won't validate, won't dispatch, or won't be reachable in stub mode.

## Adding a new provider

1. **`agents/<name>_agent.py`** -- subclass `BaseAgent`, implement `async def decide(self, state, agent) -> AgentDecision`. Accept optional `api_key` param for dynamic roster support.
2. **`config.py`** -- add `<name>_api_key` and `<name>_model` to `Settings` with sensible defaults
3. **`agents/factory.py`** -- add a branch in `_build_one` that returns the new client when the key is present (check both per-agent key and global settings key)
4. **`.env.example`** (both root and backend) -- document the new key
5. **`docker-compose.yml`** -- add passthrough for the new key/model env vars
6. **`main.py::PROVIDER_DEFAULTS`** -- add entry so the ConfigPanel UI shows it

The factory **must gracefully fall back to `StubAgent`** if the key is missing -- never raise. This keeps the simulation runnable without keys.

## Action handler contract

Every `do_*` function in `actions.py`:

- Takes `session: AsyncSession` as first positional + everything else as kwargs (`turn`, `actor_id`, plus action-specific args)
- Returns `ActionResult(success, note, delta=0.0, payload=None)`
- Always emits at least one `Transaction` row when it mutates balance (use the `_record` helper)
- Multi-party actions (trade, marriage) emit one row per affected party so the ledger reads cleanly per-agent
- Never commits the session itself — `engine.run_turn` commits once at end of turn

## Stub mode

- `STUB_MODE=true` (default in `.env.example`) routes every agent through `StubAgent` regardless of which keys are present
- When `STUB_MODE=false`, missing-key agents still individually fall back to stub -- so you can start with just `ANTHROPIC_API_KEY` and grow
- `StubAgent` is **deterministic per personality** via `PERSONALITY_BIAS` weights -- keep it that way so test runs are reproducible-ish
- Dynamic agents (from `/configure`) that don't match a known personality ID use `DEFAULT_BIAS`

## Error handling

- The engine tracks `consecutive_errors` and `last_error` per agent in the DB
- After `error_threshold` (default 3) consecutive `decide()` failures, or any permanent error (401/403/404), the simulation pauses
- A `simulation_paused` WS event is broadcast; the frontend shows an error modal
- `POST /agents/{id}/remove` force-eliminates a failing agent; `POST /simulation/resume` clears error counters
- `_is_permanent_error(exc)` classifies errors -- extend it when adding new providers

## Deferred actions

- `invest` and `lend` create `DeferredAction` rows (in `models/deferred.py`)
- `_process_deferred(session, turn)` runs at the start of each `run_turn()` to settle matured items
- Investments: 70% success at 1.2-2x return, 30% total loss
- Loans: debtor repays 1.3x at maturity, or defaults if bankrupt/insufficient balance

## Tests

- `tests/conftest.py` sets `DATABASE_URL=sqlite+aiosqlite:///./test_darwin.sqlite` + `STUB_MODE=true` **before any app import** (so `get_settings()` caches the test config)
- The `session` fixture in `test_actions.py` builds a fresh in-memory engine per test
- Action handlers are tested in isolation — they're pure over `(session, kwargs)`
- For new actions, mirror the existing test pattern: seed two agents, call the handler, assert balance + side effects

## Gotchas

- **Windows console = cp1252 by default.** `print()` with em dashes (`—`) or unicode arrows (`→`) crashes. Use `--` and `->` in CLI output. (The web/JSON layers handle unicode fine — only `print` is broken.)
- **`get_settings()` is cached.** If you set env vars after first call, restart Python. Tests set vars in `conftest.py` *before* import for this reason.
- **`AsyncSession.add()` doesn't INSERT immediately.** Mutations are flushed at commit. Within a single `run_turn`, all writes are visible after the engine's final `await session.commit()`.
- **Acceptance is probabilistic in `do_trade`.** Wealthy targets reject more often (`accept_prob = 1 - balance/100`). This is intentional — keep it if you tune it.
- **Marriage doesn't dissolve on death.** The surviving spouse stays married to the eliminated agent. This is intentional research signal; if you change it, document why.

## REST API surface

Key endpoints beyond `/health`, `/state`, `/turn`, `/run`:
- `POST /configure` -- set up dynamic roster (3-10 agents), resets DB
- `GET /providers` -- provider info + sprite options for the ConfigPanel
- `POST/GET/DELETE /api-keys` -- encrypted API key CRUD (never exposes raw keys)
- `GET /export/thoughts` -- download JSONL thought log
- `GET /export/thoughts/latest?lines=50` -- last N entries as JSON
- `POST /agents/{id}/remove` -- force-eliminate a failing agent
- `POST /simulation/resume` -- clear errors, resume paused simulation

## Things NOT to do

- **Don't add a sync SQLAlchemy session.** All DB code is `async`. If something feels easier sync, you're missing the right pattern.
- **Don't import `app.agents.factory` at the top of `oracle/engine.py`.** Lazy-import inside the function -- avoids the obvious cycle.
- **Don't catch + swallow validation errors in actions.** Let `arg_model.model_validate` raise; `engine._apply_decision` already maps it to a "rejected" outcome string.
- **Don't print PII or API keys in logs.** Logging is INFO level by default; assume logs land in CI artifacts. The `api_key.py` module encrypts keys at rest and never returns raw values via API.
