# Project Darwin -- LLM Economic Survival Simulation

A multi-agent research simulation where LLMs compete in a ruthless economic arena. Agents work, trade, steal, deceive, form alliances, and betray each other to accumulate wealth. The last agent standing -- or the first to hold 90% of all wealth -- wins.

## What makes it interesting

- **20 actions** including deception (bluff, gaslight, slander, extort) and social manipulation (bribe, vouch, propose_deal)
- **Goods economy** with specialization -- agents produce different goods and must trade to survive (food is consumed every tax cycle)
- **Information asymmetry** -- agents can't see each other's balances, only their own + allies/spouse
- **Trust system** (0-100) that affects trade acceptance and can be manipulated via slander/vouch
- **Progressive taxation** on cash (invested capital is exempt), with collective strike mechanic to waive taxes
- **Action tiers** -- 1 major + 1 optional free action per turn (e.g., `steal + bluff` or `work + vouch`)
- **Any mix of providers** -- run 5 Claude agents, or Claude vs GPT vs Gemini vs Grok, or all stubs

## Quickstart

```bash
git clone <repo-url>
cd project-darwin
cp .env.example .env       # paste API keys, or leave blank for stub mode
docker compose up --build   # postgres + oracle + arena
# open http://localhost:3000
```

The ConfigPanel opens automatically. Set up 3-10 agents (name, provider, model, color), enter API keys once per provider, and click Start.

With an empty `.env` and all agents set to `stub` provider, the simulation runs with deterministic fake responses -- no API keys needed.

## Architecture

```
Next.js (React)  <-- WS/REST -->  FastAPI (Oracle)  --> Postgres
   WorldMap                         turn loop
   Sidebar                          20 action handlers
   PublicLog                         trust + goods + tax
   ConfigPanel                       deferred actions (invest/lend)
                                     parallel agent decide()
                                  --> LLM providers (Anthropic, OpenAI, Google, Grok, Ollama)
```

The Oracle is the single source of truth. Frontend is a pure viewer.

## Game mechanics

| Mechanic | Detail |
|----------|--------|
| Starting capital | $10 per agent |
| Tax | Progressive brackets every 10 turns (0-20% on cash). Invested capital exempt. |
| Food | Must consume 1 food per tax cycle or pay $1 hunger penalty |
| Goods | ore ($0.30), food ($0.25), tech ($0.50). Each agent specializes in one. |
| Steal | Success drops 8% per attempt (60% base, min 15%). Penalty $2+ escalating. |
| Marriage | Requires mutual consent. Pools balances. +10% work bonus. Divorce splits 50/50. |
| Trust | 0-100 score. Affects trade acceptance. Slander lowers, vouch raises. |
| Inheritance | Will target gets 50%. Spouse gets 100%. No heir = assets lost. |
| Elimination | $0 balance = dead. Assets go to heir. |
| Apex win | Hold >=90% of all alive agents' wealth. |

## 20 actions (major + free tier)

**Major** (1 required per turn): work, trade, bet, invest, steal, lend, sabotage, extort, bribe, socialize

**Free** (0-1 optional alongside major): vouch, will, rest, strike, bluff, propose_deal, slander, gaslight, gift, charity

## API

| Endpoint | Description |
|----------|-------------|
| `POST /configure` | Set up agents (3-10), resets simulation |
| `POST /run?turns=N` | Run N turns |
| `POST /reset` | Wipe everything |
| `GET /state` | Full snapshot (agents, thoughts, balances) |
| `GET /export/thoughts` | Download JSONL thought log |
| `POST /agents/{id}/remove` | Eliminate a failing agent |

## Development

```bash
# Backend
cd backend && pip install -r requirements.txt && pytest

# Frontend
cd frontend && npm install && npm run dev
```

## Research output

JSONL thought logs in `thought_logs/`:
```json
{"schema_version": 2, "turn": 7, "agent_id": "agent_1", "monologue": "...",
 "action": "steal", "arguments": {"target": "agent_2"},
 "outcome": "stole $1.23 from agent_2 [ok]", "timestamp": "..."}
```
