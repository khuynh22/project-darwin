# CLAUDE.md -- Project Darwin

LLM economic survival simulation. 3-10 agents compete with 20 actions (work, trade, steal, deceive, socialize) in a goods economy with trust scores, progressive taxation, and information asymmetry. Users configure agents from the UI -- no hardcoded roster.

## Architecture

```
Next.js (React)  <-- WS/REST -->  FastAPI (Oracle)  --> Postgres
                                    turn loop + parallel decide()
                                    20 action handlers
                                    trust, goods, tax, deferred actions
                                  --> LLM providers (Anthropic, OpenAI, Google, Grok, Ollama, Stub)
```

The Oracle is authoritative. Frontend is a pure viewer. No game logic in the frontend.

## Repo layout

```
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
      schemas.py          # 20 tool schemas (Pydantic), MAJOR_ACTIONS/FREE_ACTIONS sets
      actions.py          # 20 do_* handlers + ACTION_TABLE
      engine.py           # run_turn (parallel decide, sequential apply), progressive tax, deferred settlement, extortion enforcement, inheritance
    agents/
      base.py             # BaseAgent, AgentDecision (major + free action), system prompt, info-asymmetric world brief
      stub.py             # StubAgent with DEFAULT_BIAS for all 20 actions
      anthropic_agent.py  # Extracts 1-2 tool calls
      openai_agent.py     # Extracts 1-2 tool calls (OpenAI, Grok, Ollama)
      google_agent.py     # Extracts 1-2 tool calls, schema sanitizer for anyOf/null
      factory.py          # build_agents(roster) with per-agent API keys

frontend/
  app/page.tsx            # Main layout: header, world map, public/private logs, sidebar
  components/
    WorldMap.tsx           # 6 venue cards (3x2 grid) with agent chips showing name/balance/action
    Sidebar.tsx            # Agent cards: balance, invested, trust bar, inventory, specialty, social, badges
    PublicLog.tsx           # Public feed (actions + public_message broadcasts)
    ThoughtLog.tsx          # Private reasoning (observer only)
    ConfigPanel.tsx         # Agent setup modal: provider, model, color, API keys (per-provider), personality
  lib/ws.ts               # Types (AgentSnap, ThoughtSnap, WorldSnapshot, PausedEvent) + WS connection
```

## Game mechanics

- **20 actions** in 2 tiers: 10 major (required, 1/turn) + 10 free (optional, 1/turn alongside major)
- **Goods economy**: 3 goods (ore $0.30, food $0.25, tech $0.50). Each agent has a random specialty (produces 2-3x). Food consumed every tax cycle or $1 penalty.
- **Progressive tax**: 0% on $0-2, 5% on $2-5, 10% on $5-10, 15% on $10-20, 20% on $20+. Invested capital exempt. 3+ agents striking waives tax.
- **Trust score** (0-100): affects trade acceptance. Modified by slander (-5 to -10), vouch (+5), steal (-3 to -5), trade (+1), loan default (-10).
- **Info asymmetry**: agents only see own balance + spouse/allies. Others show fuzzy range. Gaslight injects fake events.
- **Steal nerf**: success 60% - 8%/attempt (min 15%). Penalty $2 base + $0.50/attempt.
- **Marriage**: mutual consent (two proposals). Pools balances. +10% work. Divorce splits 50/50.
- **Bankruptcy**: any agent with `balance <= 0` is eliminated at end of turn -- every turn, not only on tax cycles. Invested capital and goods do not protect them.
- **Inheritance**: will target gets 50%, spouse gets 100%. No heir = assets + goods lost.
- **Deferred actions**: invest (5 turns, 70% success at 1.2-2x) and lend (5 turns, 1.1x repayment). Extortion auto-triggers next turn.
- **Parallel execution**: all agent decide() calls run concurrently (120s timeout). Decisions applied sequentially.

## Adding a new action

1. `oracle/schemas.py` -- Pydantic model inheriting `_BaseArgs` + add to `TOOL_DEFINITIONS` + `ARG_MODELS` + `FREE_ACTIONS` or `MAJOR_ACTIONS`
2. `oracle/actions.py` -- `do_<name>()` handler + add to `ACTION_TABLE`
3. `agents/stub.py` -- add to `DEFAULT_BIAS` + argument generation in `_pick_major()`
4. `agents/base.py` -- add to system prompt
5. `frontend/components/WorldMap.tsx::ACTION_VENUE` -- map to venue

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

- `POST /configure` -- set up 3-10 agents, resets DB
- `POST /run?turns=N` -- run N turns (parallel agent calls)
- `POST /reset` -- wipe everything
- `GET /state` -- full snapshot (includes invested capital for moderator)
- `GET /providers` -- provider list + color options
- `POST/GET/DELETE /api-keys` -- encrypted key CRUD
- `GET /export/thoughts` -- JSONL download
- `POST /agents/{id}/remove` -- eliminate failing agent
- `POST /simulation/resume` -- clear errors and continue

## Things NOT to do

- Don't bypass the Oracle. All mutations go through `actions.py` + `engine.py`.
- Don't hardcode agent IDs, sprite names, or model IDs.
- Don't add sync DB calls. Everything is async.
- Don't log or expose raw API keys.
- Don't import `agents/factory` at module level in `engine.py` (lazy import).
