# Contributing to Project Darwin

Thanks for considering a contribution. Project Darwin is a research-oriented LLM economic simulation. Issues, bug fixes, new actions, new providers, and UX improvements are all welcome.

## Ground rules

- The Oracle is authoritative. All game-state mutations go through `backend/app/oracle/actions.py` and `engine.py`. Don't add game logic to the frontend.
- All database access is async. No sync SQLAlchemy.
- Money is always `round(x, 2)`. Goods are integers. Trust is `0–100`.
- Don't hardcode rosters, agent IDs, sprite names, or model IDs.
- Never log or expose raw API keys.

## Development setup

```bash
git clone https://github.com/khuynh22/project-darwin
cd project-darwin
cp .env.example .env       # leave keys blank for stub mode
docker compose up --build  # http://localhost:3000
```

### Backend (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env

# CLI run with sqlite (no postgres needed) — uses offline stub agents:
DATABASE_URL=sqlite+aiosqlite:///./darwin.sqlite \
  python -m scripts.run_simulation --turns 50 --reset

# Dev server (needs postgres):
uvicorn app.main:app --reload
```

### Frontend (without Docker)

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

## Tests, lint, types

```bash
# Backend
cd backend
pytest
ruff check .

# Frontend
cd frontend
npm run lint
npm run typecheck
```

CI runs all of the above on every PR. See `.github/workflows/ci.yml`.

## Adding a new action

A new action touches five places. See [CLAUDE.md](./CLAUDE.md) for the canonical checklist; the short version:

1. `backend/app/oracle/schemas.py` — Pydantic model + `TOOL_DEFINITIONS` + `ARG_MODELS` + `MAJOR_ACTIONS`/`FREE_ACTIONS`
2. `backend/app/oracle/actions.py` — `do_<name>()` handler + `ACTION_TABLE` entry
3. `backend/app/agents/stub.py` — `DEFAULT_BIAS` weight + `_pick_major()` argument generation
4. `backend/app/agents/base.py` — system-prompt mention
5. `frontend/components/WorldMap.tsx` — `ACTION_VENUE` and `ACTION_LABELS`; `frontend/components/PublicLog.tsx` — `ACTION_COLORS`

Add a unit test in `backend/tests/test_actions.py` and exercise the new handler against the in-memory SQLite fixture.

## Adding a new LLM provider

1. Add a `*_agent.py` under `backend/app/agents/` that extracts 1–2 tool calls from the model's response.
2. Wire it into `backend/app/agents/factory.py::build_agents()` with a graceful fallback to `StubAgent` when the API key is missing — never raise.
3. Add the provider option to `frontend/components/ConfigPanel.tsx` and to the `/providers` REST response.
4. Add an entry under "Model IDs" in `.env.example`.

## Pull requests

- Branch from `main`. One logical change per PR.
- Include a short description of the gameplay or behavioral impact when relevant — this project is research code, and reviewers care about how mechanics shift.
- Make sure CI passes (tests, ruff, lint, typecheck).
- Keep diffs focused. Don't reformat unrelated files or rename modules in feature PRs.

## Commit style

Conventional, but pragmatic. Imperative mood:

```
Add <action> handler with X mechanic
Fix tax bracket off-by-one for invested capital
Refactor <area> for Y
```

## Reporting bugs

Open a GitHub issue with:
- Steps to reproduce
- Provider mix and turn count
- Relevant `thought_logs/*.jsonl` excerpt or stack trace

For security issues see [SECURITY.md](./SECURITY.md).

## Notes on `CLAUDE.md` files

Three `CLAUDE.md` files (root, `backend/`, `frontend/`) document architecture and conventions for AI coding assistants and humans alike. They are not authoritative specs — the code is — but they are kept in sync with the implementation and are a good first read.

## License

By contributing, you agree your contributions are licensed under the [Apache License 2.0](./LICENSE), the project's license.
