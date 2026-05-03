# CLAUDE.md -- backend/

Python 3.12+. FastAPI + async SQLAlchemy 2.0 + Pydantic v2. **Everything is async.**

## Run

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt && cp .env.example .env
pytest                    # unit tests
uvicorn app.main:app --reload  # dev server (needs postgres)

# CLI simulation (sqlite, no server)
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite STUB_MODE=true \
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
- **`agents/{anthropic,openai,google}_agent.py`** -- Extract 1-2 tool calls from LLM response. OpenAI client used for Grok/Ollama too.
- **`models/agent.py`** -- Agent ORM: balance, trust_score, steal_count, specialty, inventory, social state, will_target, extortion/bribe pending.
- **`models/deferred.py`** -- DeferredAction for investments/loans maturing over turns.
- **`models/api_key.py`** -- Fernet-encrypted API key storage.
- **`thought_export.py`** -- Streaming JSONL exporter (schema v2 with timestamp).

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
- Inheritance: will = 50%, spouse = 100%. Goods also transfer. No heir = lost.

## REST API

`POST /configure`, `POST /run?turns=N`, `POST /reset`, `GET /state` (includes invested capital), `GET /providers`, `POST/GET/DELETE /api-keys`, `GET /export/thoughts`, `POST /agents/{id}/remove`, `POST /simulation/resume`

## Conventions

- Money: `round(x, 2)`. Goods: integers. Trust: 0-100 float.
- All decide() calls run in parallel (120s timeout). Decisions applied sequentially.
- Agent colors: red, blue, green, purple, orange, cyan, pink, yellow, teal, indigo. No legacy sprite names.
- Factory always falls back to StubAgent. Never raises.
- Don't import factory at module level in engine.py (lazy import to avoid cycles).
