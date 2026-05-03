# CLAUDE.md — Project Darwin

A multi-agent simulation observing emergent economic and social behavior between SOTA LLMs. Users configure 3-10 agents from the UI (any mix of providers), each starting with $10. Agents work / trade / bet / invest / steal / lend / socialize / sabotage and either survive 500 turns or become the "Apex Agent" by holding >=90% of all wealth.

## Architecture (one screen)

```
┌──────────────────────────────────────┐         ┌───────────────────────────┐
│  Next.js + Phaser 3 -- Pixel Arena   │ <-- WS  │  FastAPI -- The Oracle    │
│  (venues, animated sprites, config)  │ <--REST │   + async SQLAlchemy DB   │
└──────────────────────────────────────┘         └───────────┬───────────────┘
                                                             │ build_agents(roster)
                                                  ┌──────────┼───────────┐
                                                  ▼          ▼           ▼
                                            Anthropic    OpenAI/Grok   Google
                                            (dynamic)    /Ollama       (dynamic)
                                                         (dynamic)
```

The **Oracle** is the single source of truth. It owns the ledger, the turn loop, survival tax, bankruptcy, and apex detection. **Agents talk to the Oracle through tool calls** -- they never touch the database directly. The frontend mirrors Oracle state via WebSocket; it never computes game logic.

## Roster

There are **no hardcoded agents**. Users must configure 3-10 agents from the UI before starting a simulation. The ConfigPanel opens automatically on first load. Each agent needs: display name, provider, model ID, and optionally a personality (auto-generated if blank). API keys are entered once per provider and stored encrypted in the DB (`models/api_key.py`).

## Repo layout

```
backend/
  app/
    config.py             # Settings (no hardcoded roster -- agents configured via UI)
    db.py                 # Async SQLAlchemy engine + Base + SessionLocal
    main.py               # FastAPI routes + lifespan + config/export endpoints
    ws.py                 # WebSocket broadcaster (singleton)
    thought_export.py     # Streaming JSONL exporter for thought logs
    models/
      agent.py            # Agent ORM (balance, errors, social state)
      ledger.py           # Transaction, ThoughtLog, WorldEvent
      deferred.py         # DeferredAction (investments, loans maturing over turns)
      api_key.py          # ApiKeyStore (Fernet-encrypted API key storage)
    oracle/               # ENGINE -- turn loop, action handlers, tool schemas
      schemas.py          # TOOL_DEFINITIONS + ARG_MODELS (10 actions)
      actions.py          # do_work/trade/bet/socialize/sabotage/invest/steal/lend/charity/propose_deal
      engine.py           # run_turn() + _process_deferred() + start_simulation()
    agents/               # Provider-agnostic clients
      base.py             # BaseAgent + AgentDecision + system prompt template
      stub.py             # Deterministic fallback when keys missing
      anthropic_agent.py, openai_agent.py, google_agent.py
      factory.py          # build_agents(roster?) -- per-agent keys, dynamic roster
      memory.py           # Chroma vector memory wrapper
    graph/langgraph_state.py  # Optional LangGraph wrapper around the loop
  scripts/run_simulation.py   # CLI: runs N turns, exports JSONL thought logs
  tests/                  # pytest + pytest-asyncio (in-memory SQLite)

frontend/
  app/                    # Next.js App Router (page.tsx, layout.tsx)
  components/
    Arena.tsx             # Phaser container
    Sidebar.tsx           # Agent cards + error badges
    ThoughtLog.tsx        # Color-coded action log
    ConfigPanel.tsx       # Dynamic agent configuration modal (3-10 agents)
  lib/
    ws.ts                 # WebSocket + REST client + shared types + PausedEvent
    phaser/scene.ts       # Phaser scene: 6 venues, composed sprites, tween animations
```

## Project-wide conventions

- **Money is always `round(x, 2)`** before being written to the DB or returned to a client. Never let floats drift.
- **All action validation goes through `ARG_MODELS`** in `oracle/schemas.py`. If you add a new action, you wire it in **four places**: `TOOL_DEFINITIONS`, `ARG_MODELS`, `ACTION_TABLE` (in `actions.py`), and `PERSONALITY_BIAS` (in `stub.py`). Also update `ACTION_VENUE` in `frontend/lib/phaser/scene.ts` and the system prompt in `base.py`.
- **Never hardcode a model ID in code.** New SOTA goes in `.env` + `config.py` defaults — never literals scattered through agent files.
- **Stub mode is always a valid fallback.** If you add a provider, the factory must gracefully degrade to `StubAgent` when its key is missing. The simulation must run end-to-end with zero API keys.
- **The Oracle is authoritative.** Frontend never computes balances, only displays them. Tests never mutate state outside session fixtures.

## Run the stack

**Recommended path** — one command from repo root:
```bash
cp .env.example .env       # paste API keys (or leave blank for stub mode)
docker compose up --build  # postgres + oracle + arena
```
Open http://localhost:3000. The root `docker-compose.yml` is the single source of truth for service wiring; the backend image lives at `backend/Dockerfile`, the frontend at `frontend/Dockerfile`.

**Local dev (no Docker)** — for fast iteration on either layer:
```bash
# Backend (stub mode, sqlite, no keys needed)
cd backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt && cp .env.example .env
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite STUB_MODE=true \
  python -m scripts.run_simulation --turns 100 --reset

# Frontend
cd frontend && npm install && npm run dev
```

Per-component conventions live in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

## Env config

There are two `.env` files by design:
- **`.env`** at the repo root — read by `docker-compose.yml`, passed into the `oracle` container
- **`backend/.env`** — read by `pydantic-settings` only when running the backend *outside* Docker

The compose `environment:` block takes precedence over `backend/.env` inside the container, so you only edit the root `.env` for the docker path.

## Error handling

When an agent's `decide()` call fails, the engine tracks `consecutive_errors` on the Agent model. After 3 consecutive failures (configurable via `ERROR_THRESHOLD`) or any permanent error (401/403/404), the simulation **pauses** and broadcasts a `simulation_paused` WS event. The frontend shows a modal with options to remove the agent or resume. Errors reset to 0 on a successful `decide()` call.

## Deferred actions

`invest` and `lend` create `DeferredAction` rows that mature after 5 turns. The engine calls `_process_deferred(session, turn)` at the start of each turn to settle them. Investments have a 70% success rate; loans default if the debtor is bankrupt.

## API key storage

Per-agent API keys are Fernet-encrypted and stored in the `api_keys` DB table (`models/api_key.py`). The encryption key comes from `Settings.encryption_key`; if blank, an ephemeral key is generated (keys won't survive restart). For production, set `ENCRYPTION_KEY` in `.env`.

## Thought log export

The `ThoughtExporter` (`thought_export.py`) streams JSONL rows to `thought_logs/` during web-served simulation. The CLI script also exports at the end of a run. Schema v2 adds a `timestamp` field. Download via `GET /export/thoughts`.

## Things NOT to do

- **Don't bypass the Oracle.** No direct INSERT into `transactions` or `thoughts` from anywhere except `oracle/actions.py` and `oracle/engine.py`. The ledger must remain a single audit trail.
- **Don't put provider-specific quirks in `engine.py`.** Provider differences live in `agents/<provider>_agent.py`. The engine only knows about `BaseAgent.decide()`.
- **Don't add a provider without updating the factory.** Adding a new provider means updating: `agents/factory.py`, `config.py::Settings`, `.env.example`, docker-compose environment block, and this file. The factory **must** fall back to `StubAgent` if the key is missing.
- **Don't introduce a synchronous DB call.** Everything is `async` end-to-end. `select()` always goes through `await session.execute(...)`.
- **Don't log or expose raw API keys.** Keys are encrypted at rest and never included in API responses, logs, or WS broadcasts.

## Research output

Thought logs are written to `thought_logs/` as JSONL -- both by the CLI script and by the web server (streaming via `ThoughtExporter`). Schema v2:

```json
{"schema_version": 2, "turn": 7, "agent_id": "atlas",
 "monologue": "...", "action": "trade",
 "arguments": {"target": "nova", "amount": 0.5, "item": "information"},
 "outcome": "trade accepted by nova [ok]",
 "timestamp": "2026-05-02T12:34:56+00:00"}
```

Download from the UI via EXPORT LOG button or `GET /export/thoughts`. Keep the schema stable -- bump `schema_version` for any structural changes.
