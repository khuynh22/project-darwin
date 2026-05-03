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
┌─────────────────────────────────────┐         ┌────────────────────┐
│  Next.js + Phaser 3 — Pixel Arena   │ ◄─ WS ─ │  FastAPI Oracle    │
│  (sprites, thought bubbles, ledger) │ ◄─REST─ │  + Postgres ledger │
└─────────────────────────────────────┘         └────────┬───────────┘
                                                         │
                                          ┌──────────────┼─────────────┐
                                          ▼              ▼             ▼
                                   Anthropic      OpenAI/Fireworks/   Google
                                   Claude Opus    DeepSeek            Gemini
```

Backend is FastAPI + async SQLAlchemy + Postgres. The Oracle owns turn order, survival tax, bankruptcy, and apex detection. A LangGraph wrapper is provided for instrumentation but the default loop is plain async — fewer moving parts.

## Quickstart — one command

```bash
git clone https://github.com/khuynh22/project-darwin.git
cd project-darwin
cp .env.example .env       # paste API keys (or leave blank for stub mode)
docker compose up --build  # postgres + oracle + arena
# open http://localhost:3000
```

That's it. With an empty `.env`, the simulation still runs end-to-end using deterministic stubs. As you add keys, those agents start using real models — the rest stay stubbed. So you can start with just `ANTHROPIC_API_KEY` and grow.

To drive the sim, click **STEP / RUN 10 / RUN 100** in the arena UI, or hit the Oracle directly:
```bash
curl -X POST 'http://localhost:8000/run?turns=100'
curl 'http://localhost:8000/state' | jq
```

## Going live with real models

Edit `.env` (root, not `backend/`):
```
STUB_MODE=false
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
FIREWORKS_API_KEY=...
DEEPSEEK_API_KEY=...
```
`docker compose up` again — no rebuild needed for env changes.

## Local development (without Docker)

```bash
# Backend
cd backend && python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite STUB_MODE=true \
  python -m scripts.run_simulation --turns 100 --reset

# Frontend
cd frontend && npm install && npm run dev
```

## Tests

```bash
cd backend && pytest
```

## Research output

`scripts/run_simulation.py` writes JSONL thought logs to `thought_logs/`. Each line:
```json
{"turn": 7, "agent_id": "atlas", "monologue": "…", "action": "trade", "arguments": {...}, "outcome": "..."}
```
Suitable for direct ingestion into pandas / DuckDB for behavioral analysis.
