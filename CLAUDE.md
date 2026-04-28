# CLAUDE.md — Project Darwin

A multi-agent simulation observing emergent economic and social behavior between SOTA LLMs from different providers. Each agent gets $10, must work / trade / bet / socialize / sabotage, and either survives 500 turns or becomes the "Apex Agent" by holding ≥90% of all wealth.

## Architecture (one screen)

```
┌─────────────────────────────────────┐         ┌─────────────────────────┐
│  Next.js + Phaser 3 — Pixel Arena   │ ◄─ WS ─ │  FastAPI — The Oracle    │
│  (sprites, monologue, ledger panel) │ ◄─REST─ │  + async SQLAlchemy DB   │
└─────────────────────────────────────┘         └────────────┬────────────┘
                                                              │ build_agents()
                                          ┌───────────────────┼─────────────────┐
                                          ▼                   ▼                 ▼
                                    Anthropic         OpenAI / Fireworks /     Google
                                    (ATLAS)           DeepSeek                 (SAGE)
                                                      (NOVA / HYDRA / CIPHER)
```

The **Oracle** is the single source of truth. It owns the ledger, the turn loop, survival tax, bankruptcy, and apex detection. **Agents talk to the Oracle through tool calls** — they never touch the database directly. The frontend mirrors Oracle state via WebSocket; it never computes game logic.

## Roster

Defined in `backend/app/config.py::AGENT_ROSTER`. **Model IDs are env-overridable** (`backend/.env`) so the roster swaps as new SOTA drops without code changes.

| agent_id | display | provider           | personality            |
|----------|---------|--------------------|------------------------|
| atlas    | ATLAS   | anthropic          | cooperative diplomat   |
| nova     | NOVA    | openai             | high-risk strategist   |
| hydra    | HYDRA   | fireworks_llama    | wildcard               |
| sage     | SAGE    | google             | survivalist            |
| cipher   | CIPHER  | deepseek           | minimalist defender    |

## Repo layout

```
backend/
  app/
    config.py             # Settings + AGENT_ROSTER (single source of truth)
    db.py                 # Async SQLAlchemy engine + Base + SessionLocal
    main.py               # FastAPI routes + lifespan
    ws.py                 # WebSocket broadcaster (singleton)
    models/               # ORM: agent, ledger (transactions, thoughts, world_events)
    oracle/               # ENGINE — turn loop, action handlers, tool schemas
      schemas.py          # TOOL_DEFINITIONS + ARG_MODELS (Pydantic)
      actions.py          # do_work / do_trade / do_bet / do_socialize / do_sabotage
      engine.py           # run_turn() + start_simulation()
    agents/               # Provider-agnostic clients
      base.py             # BaseAgent + AgentDecision + system prompt template
      stub.py             # Deterministic fallback when keys missing
      anthropic_agent.py, openai_agent.py, google_agent.py
      factory.py          # build_agents() — picks client per agent based on env
      memory.py           # Chroma vector memory wrapper
    graph/langgraph_state.py  # Optional LangGraph wrapper around the loop
  scripts/run_simulation.py   # CLI: runs N turns, exports JSONL thought logs
  tests/                  # pytest + pytest-asyncio (in-memory SQLite)

frontend/
  app/                    # Next.js App Router (page.tsx, layout.tsx)
  components/             # Arena (Phaser host), Sidebar, ThoughtLog
  lib/
    ws.ts                 # WebSocket + REST client + shared types
    phaser/scene.ts       # Phaser scene singleton (lives outside React)
```

## Project-wide conventions

- **Money is always `round(x, 2)`** before being written to the DB or returned to a client. Never let floats drift.
- **All action validation goes through `ARG_MODELS`** in `oracle/schemas.py`. If you add a new action, you wire it in **three places**: `TOOL_DEFINITIONS`, `ARG_MODELS`, and `ACTION_TABLE` (in `actions.py`).
- **Never hardcode a model ID in code.** New SOTA goes in `.env` + `config.py` defaults — never literals scattered through agent files.
- **Stub mode is always a valid fallback.** If you add a provider, the factory must gracefully degrade to `StubAgent` when its key is missing. The simulation must run end-to-end with zero API keys.
- **The Oracle is authoritative.** Frontend never computes balances, only displays them. Tests never mutate state outside session fixtures.

## Run the stack

```bash
# Backend (stub mode, no API keys needed)
cd backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite STUB_MODE=true \
  python -m scripts.run_simulation --turns 100 --reset

# Backend dev server (Postgres via docker)
docker compose up -d postgres && uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

Per-component conventions live in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## Things NOT to do

- **Don't bypass the Oracle.** No direct INSERT into `transactions` or `thoughts` from anywhere except `oracle/actions.py` and `oracle/engine.py`. The ledger must remain a single audit trail.
- **Don't put provider-specific quirks in `engine.py`.** Provider differences live in `agents/<provider>_agent.py`. The engine only knows about `BaseAgent.decide()`.
- **Don't add a 6th provider casually.** Adding one means updating: `config.py::AGENT_ROSTER`, `agents/factory.py`, `.env.example`, this file's roster table, and the README. If the user asks for a new provider, do all five.
- **Don't introduce a synchronous DB call.** Everything is `async` end-to-end. `select()` always goes through `await session.execute(...)`.
- **Don't expand the action set without research justification.** New actions change the emergent dynamics. Treat them as experiment changes, not features.

## Research output

`scripts/run_simulation.py` writes one JSONL row per agent per turn to `thought_logs/`:

```json
{"turn": 7, "agent_id": "atlas", "monologue": "…", "action": "trade",
 "arguments": {"target": "nova", "amount": 0.5, "item": "information"},
 "outcome": "trade accepted by nova [ok]"}
```

This is the primary research artifact — keep the schema stable. If you change it, add a `schema_version` field rather than silently breaking downstream notebooks.
