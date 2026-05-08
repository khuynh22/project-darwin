# Project Darwin - LLM Behavior Under Survival Pressure

[![CI](https://github.com/khuynh22/project-darwin/actions/workflows/ci.yml/badge.svg)](https://github.com/khuynh22/project-darwin/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Node 20+](https://img.shields.io/badge/node-20+-green.svg)](https://nodejs.org)

A research instrument for studying how LLMs behave over **long-horizon, multi-step trajectories** when survival is the only objective. Each turn, every agent picks from 20 actions — work, trade, steal, deceive, form alliances, betray — using only its native tool-calling against a deliberately minimal harness: a tool list, a world brief, and a rolling 10-turn self-history. No critic loops, no plan-and-execute wrappers, no external retrieval. Agents that fail to acquire resources die; the last one standing (or first to hold ≥90% of all wealth) wins.

Every turn produces a complete trace of the model's private reasoning, chosen action, arguments, and the Oracle's outcome — exported as JSONL for downstream behavioral analysis across providers (Anthropic, OpenAI, Google, xAI Grok, Ollama).

## Why you might want this

You already know single-prompt evals don't tell you much about how a model behaves once a task gets long, social, and adversarial. A 200-turn Darwin run does — cheaply, in a setting you control, with the full reasoning trace dumped to JSONL.

- **You're tired of one-shot benchmarks.** This one keeps the pressure on for as long as you let it run. Strategy drift, recovery from setbacks, late-game brittleness — none of that shows up in MMLU.
- **You want to see the model, not your harness.** Tool list, world brief, 10-turn self-history. No critic loops, no plan-then-act, no RAG. What you observe is close to the base model's own decision-making.
- **You want pressure that actually elicits something.** Death is permanent, hunger compounds, taxes bracket. Models that look polite on benign tasks will gaslight an opponent 30 turns in once survival is on the line. That's the experiment.
- **You want to compare providers without building an arena from scratch.** Drop 5 Claudes against 5 GPTs, or one of each. Identical tools, identical economy, same world-brief format. Pin matching personalities and the model is the only variable.
- **You want the trace.** Every decision is `(monologue, action, arguments, outcome)` JSONL — ready to grep, plot, or feed into whatever analysis pipeline you already have.

Or you just want to watch Claude try to extort GPT over a unit of food. Also a valid use case.

## What you can study with it

- How does cooperation vs. defection scale with model capability?
- Do larger models bluff, gaslight, and slander more or less than smaller ones?
- Does a model's strategy stabilize over a 200-turn run, or oscillate?
- How do mixed-provider arenas differ from same-provider ones?
- How does information asymmetry shape strategic behavior?
- **Survival half-life:** how many turns before an average instance of model X is eliminated?

## What's in the arena

- **20 actions** in 2 tiers — 10 major (required, 1/turn) + 10 free (optional, alongside major), including deception primitives (bluff, gaslight, slander, extort) and social manipulation (bribe, vouch, propose_deal)
- **Goods economy** with specialization — ore, food, tech; food consumed every tax cycle or hunger penalty
- **Information asymmetry** — agents see only their own balance + spouse/allies; gaslighting can inject fake events into others' world briefs
- **Trust system** (0-100) modifiable via slander, vouch, betrayal — affects trade acceptance
- **Progressive taxation** on cash (invested capital exempt), with a collective strike mechanic
- **Marriage, inheritance, deferred actions** (invest, lend) for longer-horizon strategy
- **Provider-agnostic** — Anthropic, OpenAI, Google, xAI Grok, Ollama, or deterministic stubs in any mix

## Quickstart

```bash
git clone https://github.com/khuynh22/project-darwin.git
cd project-darwin
cp .env.example .env       # paste API keys, or leave blank for stub mode
docker compose up --build  # postgres + oracle + arena
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

## Designing an experiment

### 1. Pick a question and a roster

| Goal | Roster | Why |
|------|--------|-----|
| Variance of a single model | 5x same provider/model | Same model, same prompt, different decisions — measures behavioral stochasticity |
| Cross-provider behavior | 1 each: Claude, GPT, Gemini, Grok | Identical world, only model varies |
| Capability scaling | 2x small + 2x large of one provider | Does scale change cooperation/deception rates? |
| Smoke test, no API calls | All `stub` | Deterministic, free, fast |

`/configure` enforces 3-10 agents. The strike-waives-tax mechanic needs at least 3 strikers in the same cycle; with very small rosters, expect tax to bite every cycle.

### 2. Pick a horizon

- **<50 turns** — too short for taxation, deferred investments, or coalition cycles to play out. Avoid for behavioral claims.
- **100-200 turns** — default research range. Captures multiple tax cycles, investment maturity, marriage formation, elimination events.
- **500+ turns** — needed for late-game equilibria, but most arenas finish (apex or last-standing) before this. Re-roll or scale the roster.

### 3. Run it

`roster.json` body shape (the request envelope `/configure` expects):

```json
{
  "agents": [
    {"agent_id": "claude_1", "display_name": "CLAUDE 1", "provider": "anthropic", "model": "claude-opus-4-7", "sprite": "red",  "personality": "Adaptive strategist."},
    {"agent_id": "gpt_1",    "display_name": "GPT 1",    "provider": "openai",    "model": "gpt-5",          "sprite": "blue", "personality": "Adaptive strategist."}
  ]
}
```

```bash
# configure roster (resets DB)
curl -X POST localhost:8000/configure \
     -H 'content-type: application/json' \
     -d @roster.json

# run N turns
curl -X POST 'localhost:8000/run?turns=200'

# export the trace
curl localhost:8000/export/thoughts > run.jsonl
```

For runs without API calls (no keys required), set `STUB_MODE=true` in `.env` — every agent becomes a `StubAgent` regardless of the configured provider. Stub agents pick actions from a weighted bias with unseeded RNG, so runs are LLM-free but **not bit-reproducible**. For real-model runs, you must set `STUB_MODE=false` (`.env.example` ships with `true`).

For headless batches without a server: `python -m scripts.run_simulation --turns 200 --reset --roster cli_roster.json`. The CLI's `--roster` file format is a bare JSON list of agent specs (no `{"agents": ...}` envelope).

### 4. Analyze

The JSONL is one row per `(turn, agent)` decision. Useful one-liners:

```bash
# action distribution per agent
jq -r '[.agent_id, .action] | @tsv' run.jsonl | sort | uniq -c

# every deception attempt in order
jq -c 'select(.action | IN("bluff","gaslight","slander","extort"))' run.jsonl

# elimination turn for each agent (last turn they appear in the trace)
jq -r '[.turn, .agent_id] | @tsv' run.jsonl \
  | sort -k2,2 -k1,1n | awk '{a[$2]=$1} END{for (k in a) print k, a[k]}'
```

Good controls: re-run the same roster with different temperatures or a softened system prompt to separate model-induced traits from prompt-induced ones; pair every "interesting" provider against a `stub` baseline to anchor the action distribution.

## Research output

JSONL thought logs streamed via `GET /export/thoughts` and persisted in `thought_logs/`:
```json
{"schema_version": 2, "turn": 7, "agent_id": "agent_1", "monologue": "...",
 "action": "steal", "arguments": {"target": "agent_2"},
 "outcome": "stole $1.23 from agent_2 [ok]", "timestamp": "..."}
```

Each row is one model decision: the agent's private monologue, the chosen action and arguments, and the Oracle's outcome. The schema is stable across providers, so a 200-turn run with `n` agents produces `~200n` aligned rows ready for downstream analysis of strategy drift, deception patterns, coalition formation, and per-model survival half-life.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](./CONTRIBUTING.md) for the dev workflow, the five-touchpoint checklist for adding a new action, and how to plug in a new LLM provider. Please also read [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md).

For security issues, see [SECURITY.md](./SECURITY.md) — please do not file public issues for vulnerabilities.

## License

Apache License 2.0. See [LICENSE](./LICENSE).
