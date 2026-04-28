# Project Darwin — The LLM Social Economy Simulation

A research multi-agent simulation where SOTA LLMs from different providers compete and cooperate in a shared economy. Each agent is given $10, must work, trade, gamble, marry, ally, and sabotage to survive 500 turns or hold ≥90% of the world's wealth.

## Roster (April 2026 SOTA, one per provider)

| Agent  | Model                              | Provider   | Personality |
|--------|------------------------------------|------------|-------------|
| ATLAS  | claude-opus-4-7                    | Anthropic  | Cooperative diplomat |
| NOVA   | gpt-5                              | OpenAI     | High-risk strategist |
| HYDRA  | llama-v4-maverick (via Fireworks)  | Meta       | The Wildcard |
| SAGE   | gemini-2.5-pro                     | Google     | Long-term survivalist |
| CIPHER | deepseek-chat                      | DeepSeek   | Minimalist defender |

Model IDs are env-overridable (`backend/.env`) so the roster swaps as new SOTA drops.

## Architecture

```
┌─────────────────────────────────────┐         ┌───────────────────┐
│  Next.js + Phaser 3 — Pixel Arena   │ ◄─ WS ─ │  FastAPI Oracle    │
│  (sprites, thought bubbles, ledger) │ ◄─REST─ │  + Postgres ledger │
└─────────────────────────────────────┘         └────────┬──────────┘
                                                         │
                                          ┌──────────────┼─────────────┐
                                          ▼              ▼             ▼
                                   Anthropic      OpenAI/Fireworks/   Google
                                   Claude Opus    DeepSeek            Gemini
```

Backend is FastAPI + async SQLAlchemy + Postgres. The Oracle owns turn order, survival tax, bankruptcy, and apex detection. A LangGraph wrapper is provided for instrumentation but the default loop is plain async — fewer moving parts.

## Quickstart

### Backend (no API keys needed — runs in stub mode)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env

# Option A: Postgres via docker
docker compose up -d postgres
uvicorn app.main:app --reload

# Option B: skip Postgres, run the stub sim directly with SQLite
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite STUB_MODE=true \
  python -m scripts.run_simulation --turns 100 --out thought_logs/run-001.jsonl --reset
```

Then `POST /run?turns=100` to drive the sim, `GET /state` for live snapshot, `WS /ws` for live broadcast.

### Frontend

```bash
cd frontend
npm install
npm run dev
# open http://localhost:3000
```

The arena auto-connects to `http://localhost:8000`. Override via `frontend/.env.local`.

### Going live with real models

Set keys in `backend/.env` and flip `STUB_MODE=false`:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
FIREWORKS_API_KEY=...
DEEPSEEK_API_KEY=...
```
Per-agent fallback: if a provider's key is missing, that single agent runs as stub while the others use real models. So you can start with just Anthropic and grow.

## Tests

```bash
cd backend && pytest
```

## Roadmap status

- ✅ **Phase 1 — The Ledger:** FastAPI + Postgres + tool JSON schemas
- ✅ **Phase 2 — Agent Integration:** multi-provider clients + LangGraph wrapper + Chroma memory
- ✅ **Phase 3 — The Arena:** Next.js + Phaser 3 + WebSocket sync
- ✅ **Phase 4 — Emergent Behavior:** marriage / alliance / sabotage / 100-turn export

## Research output

`scripts/run_simulation.py` writes JSONL thought logs to `thought_logs/`. Each line:
```json
{"turn": 7, "agent_id": "atlas", "monologue": "…", "action": "trade", "arguments": {...}, "outcome": "..."}
```
Suitable for direct ingestion into pandas / DuckDB for behavioral analysis.
