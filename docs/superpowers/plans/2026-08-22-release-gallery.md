# Release Gallery and Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a reviewer or an engineer something to land on — a browsable gallery of released runs replayable turn by turn with the triple and the judge's verdict visible, plus a benchmark leaderboard.

**Architecture:** A `releases/` directory holds published artifacts: v4 traces, their verdicts, and scored probe results. The Oracle exposes them read-only over REST; the frontend renders them. No game logic moves to the frontend, per the project's standing convention that the Oracle is authoritative and the frontend is a pure viewer. Live BYOK sessions are untouched.

**Tech Stack:** FastAPI, Pydantic v2 (backend); Next 15 App Router, React 19, Tailwind 3 (frontend).

**Spec:** `docs/superpowers/specs/2026-08-22-darwin-benchmark-harness-design.md` §8

**Depends on:** harness-foundation, sweep-driver, probe-suite (all complete).

## Global Constraints

- Release endpoints are **read-only** and must not touch the sessions tables. A gallery request must never mutate simulation state.
- Traces are large — the 335-turn release is 2,009 turns. The turn endpoint **must paginate**; returning a whole trace in one response is a defect, not a convenience.
- A release whose files are missing or malformed is **skipped with a warning**, never served half-parsed.
- Held-out probes are never exposed. The leaderboard serves aggregate scores only.
- The gallery must show `state_fidelity` and, for probe scores, the excluded count and divergence — a viewer should be able to see the caveats without reading the paper.
- Money `round(x, 2)`; all DB calls async (no DB calls are needed here, which is the point).

---

### Task 1: Release registry

**Files:**
- Create: `backend/app/releases.py`
- Test: `backend/tests/test_releases.py`

**Interfaces:**
- Produces: `ReleaseSummary`, `Release`, `list_releases(root) -> list[ReleaseSummary]`, `load_release(root, run_id) -> Release | None`, `read_turns(root, run_id, offset, limit) -> tuple[list[TurnRecord], int]`, `read_verdicts(root, run_id) -> dict[tuple[int, str], dict]`.

**Layout on disk** — one directory per release:

```
releases/
  leaderboard_335t_20260726/
    trace.jsonl        (schema v4, required)
    verdicts.jsonl     (optional)
    scores.json        (optional, probe ModelScore rows)
    about.md           (optional, shown on the gallery card)
```

A directory without a readable `trace.jsonl` is skipped and logged. `ReleaseSummary` carries `run_id`, `condition`, `horizon`, `n_agents`, `n_turns`, `state_fidelity`, `models`, `has_verdicts`, `has_scores`, and `about`.

- [ ] **Step 1: Write the failing test** — cover: a well-formed release is listed with the right counts; a directory with no trace is skipped rather than raising; a malformed trace is skipped; `read_turns` paginates and reports the true total; an out-of-range offset returns empty rather than erroring; verdicts index by `(turn, agent_id)`; `state_fidelity` and model ids surface in the summary; a missing verdicts file yields an empty index rather than a failure.

- [ ] **Step 2: Run test to verify it fails** — `ModuleNotFoundError: No module named 'app.releases'`

- [ ] **Step 3: Write minimal implementation** — pure filesystem reads over `app.trace.io`. Cache parsed manifests in a module-level dict keyed by `(path, mtime)` so a gallery page load does not re-parse a 2,000-line file per request; the mtime key means a republished release is picked up without a restart.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit** — `feat(releases): read-only registry over published artifacts`

---

### Task 2: Release REST endpoints

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_web_releases.py`

**Endpoints:**

```
GET /releases                                  -> [ReleaseSummary]
GET /releases/{run_id}                         -> ReleaseSummary + agents
GET /releases/{run_id}/turns?offset=0&limit=50 -> {turns, total, offset, limit}
GET /releases/{run_id}/verdicts?turn=&agent=   -> [verdict]
GET /releases/{run_id}/scores                  -> [ModelScore]
```

`limit` is clamped to 200. An unknown `run_id` returns 404. The endpoints read from `settings.releases_dir`, defaulting to `releases/` relative to the repo root.

- [ ] **Step 1: Write the failing test** — using `TestClient`: listing returns the seeded release; a turns page respects `offset`/`limit` and reports `total`; `limit=10000` is clamped rather than honoured; unknown run id is 404; verdicts filter by turn and agent; scores 404 when absent. Add one test asserting a gallery request leaves the sessions tables untouched.

- [ ] **Step 2–5:** standard cycle; commit as `feat(api): read-only release endpoints for the gallery`.

---

### Task 3: Gallery pages

**Files:**
- Create: `frontend/lib/releases.ts`, `frontend/app/gallery/page.tsx`, `frontend/app/gallery/[runId]/page.tsx`
- Create: `frontend/components/TurnCard.tsx`

`frontend/lib/releases.ts` mirrors the backend types and wraps fetches against `ORACLE_HTTP` (already exported from `lib/ws.ts`).

The gallery index lists release cards: run id, condition, horizon, agent count, model ids, and a `state_fidelity` badge — `partial` must be visible, not buried.

The replay page paginates turns and renders each as a `TurnCard` showing the three channels stacked — **private reasoning, public message, applied action + outcome** — with the judge's verdict beside them when present: deceptive or not, type, confidence, sophistication, and the rationale. The triple side by side with the verdict *is* the paper's argument; this page is the argument made clickable.

Controls: filter by agent, jump to a turn, and a "deceptive only" toggle driven by the verdicts index.

- [ ] Steps: build the lib wrapper, then the index page, then the replay page; verify against a seeded local release with `npm run build` and a manual load.

---

### Task 4: Leaderboard page

**Files:**
- Create: `frontend/app/leaderboard/page.tsx`

One row per model: propensity with its interval, the per-tier curve, susceptibility, sophistication mean, pressure threshold, and — not optional — the excluded count and divergence mean. A leaderboard that hides how many probes it threw away is not reporting a benchmark.

Where `pressure_threshold` is null, render "none established" rather than a blank or a zero. Where scores come from untiered probes, say so on the row.

- [ ] Steps: types, page, empty state when no scores are published yet.

---

## What this plan does not cover

- **Publishing artifacts into `releases/`.** That is an operator step (copy or symlink the run directory); the registry only reads.
- **Live BYOK sessions**, which already work and are untouched.
- **Authoring the L1 control probes** and the curation pass — prerequisites for a leaderboard that means anything, tracked in the probe-suite plan.
